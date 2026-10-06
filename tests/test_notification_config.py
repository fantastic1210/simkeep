import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.db import decode, encode
from server.main import create_app
from server.notifications import Config, Transport
from server.notification_config import TelegramConfigInput


TOKEN_A = '123456789:' + 'A' * 35
TOKEN_B = '987654321:' + 'B' * 35
SMTP_A = {'host':'smtp.example.com','port':587,'mode':'starttls','user':'alice@example.com','password':' password $ with spaces ','from':'alice@example.com'}


class NotificationConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'test.db'
        self.app = create_app(self.path, start_worker=False, config=Config())
        self.db = self.app.state.db
        self.notifier = self.app.state.notifier
        self.a, self.b = TestClient(self.app), TestClient(self.app)
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)
        self.people, self.headers = [], []
        for client, name in [(self.a, 'Alice'), (self.b, 'Bob')]:
            reply = client.post('/api/auth/register', json={'name':name,'email':f'{name.lower()}@example.com','password':'long-password-123'})
            self.assertEqual(reply.status_code, 201, reply.text)
            self.people.append(reply.json()['user']['id'])
            self.headers.append({'X-CSRF-Token':reply.json()['csrfToken']})

    def save(self, channel, payload, client=None, headers=None):
        reply = (client or self.a).put(f'/api/notifications/config/{channel}', headers=headers or self.headers[0], json=payload)
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply

    def services(self, client=None):
        return (client or self.a).get('/api/workspace').json()['workspace']['services']

    def test_saved_configuration_is_owned_persistent_and_never_returns_secrets(self):
        for channel, payload in [('telegram',{'token':TOKEN_A}), ('email',SMTP_A)]:
            reply = self.save(channel, payload)
            self.assertNotIn(TOKEN_A, reply.text)
            self.assertNotIn(SMTP_A['password'], reply.text)
            self.assertTrue(self.services()[channel]['configured'])
            self.assertFalse(self.services(self.b)[channel]['configured'])
        response = self.a.get('/api/notifications/config')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(TOKEN_A, response.text)
        self.assertNotIn(SMTP_A['password'], response.text)
        self.assertEqual(response.json()['services']['email']['host'], 'smtp.example.com')
        self.assertTrue(response.json()['services']['telegram']['tokenSaved'])
        restarted = create_app(self.path, start_worker=False, config=Config())
        with TestClient(restarted) as client:
            client.cookies.update(self.a.cookies)
            self.assertTrue(self.services(client)['email']['configured'])
            self.assertTrue(self.services(client)['telegram']['configured'])

    def test_blank_secret_preserves_saved_credentials_and_password_whitespace(self):
        self.save('telegram', {'token':TOKEN_A})
        self.save('telegram', {'token':''})
        self.save('email', SMTP_A)
        self.save('email', {**SMTP_A, 'password':'', 'port':465, 'mode':'ssl'})
        received = []

        class SMTP:
            def __init__(self, host, port, **kwargs):
                received.append((host, port))
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def ehlo_or_helo_if_needed(self): pass
            def ehlo(self): return 250, b'ok'
            def login(self, user, password): received.append((user, password))
            def send_message(self, message):
                received.append((message['From'], message['To']))
                return {}

        with patch('server.notifications.smtplib.SMTP_SSL', SMTP):
            reply = self.a.post('/api/notifications/email/verify', headers=self.headers[0])
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(received[:2], [('smtp.example.com',465), ('alice@example.com',' password $ with spaces ')])
        self.assertEqual(received[2], ('alice@example.com','alice@example.com'))

    def test_save_requires_session_csrf_and_does_not_accept_another_owner(self):
        route = '/api/notifications/config/telegram'
        with TestClient(self.app) as visitor:
            self.assertEqual(visitor.put(route,json={'token':TOKEN_A}).status_code,401)
        self.assertEqual(self.a.put(route,json={'token':TOKEN_A}).status_code,403)
        reply = self.a.put(route,headers=self.headers[0],json={'token':TOKEN_A,'userId':self.people[1]})
        self.assertEqual(reply.status_code,422)
        self.assertFalse(self.services(self.b)['telegram']['configured'])

    def test_invalid_configuration_never_echoes_credentials_and_keeps_previous_value(self):
        self.save('telegram', {'token':TOKEN_A})
        for secret in ['https://secret.example/token','1234:secret/malicious','secret\npassword']:
            reply = self.a.put('/api/notifications/config/telegram',headers=self.headers[0],json={'token':secret})
            self.assertEqual(reply.status_code,422,reply.text)
            self.assertNotIn(secret,reply.text)
        for change in [{'port':0},{'mode':'unsafe'},{'host':'https://smtp.example.com'},{'from':'alice@example.com\r\nBcc:secret@example.com'}]:
            reply = self.a.put('/api/notifications/config/email',headers=self.headers[0],json={**SMTP_A,**change})
            self.assertEqual(reply.status_code,422,reply.text)
            self.assertNotIn(SMTP_A['password'],reply.text)
        self.assertTrue(self.services()['telegram']['configured'])
        self.assertFalse(self.services()['email']['configured'])

    def test_telegram_bot_cannot_be_claimed_by_two_accounts(self):
        self.save('telegram', {'token':TOKEN_A})
        reply = self.b.put('/api/notifications/config/telegram',headers=self.headers[1],json={'token':TOKEN_A})
        self.assertEqual(reply.status_code,409,reply.text)
        self.assertNotIn(TOKEN_A,reply.text)
        self.assertFalse(self.services(self.b)['telegram']['configured'])

    def test_changing_bot_invalidates_old_binding_and_requires_rebinding(self):
        self.save('telegram', {'token':TOKEN_A})
        async def telegram(transport, method, payload):
            return {'id':123456789,'is_bot':True,'first_name':'Test','username':'AliceTestBot'}
        with patch.object(Transport,'telegram',telegram):
            code = self.a.post('/api/notifications/telegram/binding',headers=self.headers[0]).json()['code']
        message = {'message':{'chat':{'id':12345,'type':'private'},'text':f'/start {code}'}}
        self.assertTrue(self.notifier.process_update(message,user_id=self.people[0]))
        self.save('telegram', {'token':TOKEN_B})
        settings = self.a.get('/api/workspace').json()['workspace']['settings']
        self.assertFalse(settings['telegramVerified'])
        self.assertFalse(settings['telegram'])
        self.assertEqual(settings['chatId'],'')
        self.assertFalse(self.notifier.process_update(message,user_id=self.people[0]))

    def test_personal_bot_cannot_consume_another_accounts_binding_code(self):
        self.save('telegram', {'token':TOKEN_A})
        self.save('telegram', {'token':TOKEN_B},self.b,self.headers[1])
        async def telegram(transport, method, payload):
            return {'id':123456789,'is_bot':True,'first_name':'Test','username':'AliceTestBot'}
        with patch.object(Transport,'telegram',telegram):
            code = self.a.post('/api/notifications/telegram/binding',headers=self.headers[0]).json()['code']
        message = {'message':{'chat':{'id':12345,'type':'private'},'text':f'/start {code}'}}
        self.assertFalse(self.notifier.process_update(message,user_id=self.people[1]))
        self.assertFalse(self.notifier.process_update(message))
        self.assertTrue(self.notifier.process_update(message,user_id=self.people[0]))

    def test_background_reminders_use_each_accounts_saved_token_immediately(self):
        messages = []
        for client, headers, token, chat in [(self.a,self.headers[0],TOKEN_A,'100'),(self.b,self.headers[1],TOKEN_B,'200')]:
            self.save('telegram',{'token':token},client,headers)
            reply = client.post('/api/cards',headers=headers,json={'name':'Personal SIM','provider':'Example','type':'SIM','country':'US','activatedAt':'2026-01-01','rules':[{'action':'sms','interval':90,'unit':'days','anchor':'completion','dueDate':'2026-10-07'}]})
            self.assertEqual(reply.status_code,201,reply.text)
            owner = client.get('/api/auth/me').json()['user']['id']
            with self.db.connect(write=True) as conn:
                settings = decode(conn.execute('SELECT settings FROM users WHERE id=?',(owner,)).fetchone()[0])
                settings.update(telegram=True,telegramVerified=True,chatId=chat)
                conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(settings),owner))
        async def telegram(transport, method, payload):
            messages.append((transport.config.telegram_token,method,payload['chat_id']))
            return {'message_id':1}
        now = datetime(2026,10,4,1,0,tzinfo=timezone.utc)
        self.notifier.enqueue(now)
        with patch.object(Transport,'telegram',telegram):
            asyncio.run(self.notifier.deliver(now))
        self.assertCountEqual(messages,[(TOKEN_A,'sendMessage','100'),(TOKEN_B,'sendMessage','200')])
        self.assertEqual(self.a.get('/api/workspace').json()['workspace']['notifications'][0]['status'],'sent')

    def test_connection_check_never_sends_a_message_and_redacts_network_errors(self):
        self.save('telegram', {'token':TOKEN_A})
        methods = []
        async def telegram(transport, method, payload):
            methods.append(method)
            return {'id':123456789,'is_bot':True,'first_name':'Test','username':'AliceTestBot'}
        with patch.object(Transport,'telegram',telegram):
            reply = self.a.post('/api/notifications/config/telegram/check',headers=self.headers[0])
        self.assertEqual(reply.status_code,200,reply.text)
        self.assertTrue(reply.json()['checked'])
        self.assertEqual(reply.json()['botUsername'],'AliceTestBot')
        self.assertEqual(methods,['getMe'])
        async def fail(transport, method, payload): raise RuntimeError(TOKEN_A)
        with patch.object(Transport,'telegram',fail):
            reply = self.a.post('/api/notifications/config/telegram/check',headers=self.headers[0])
        self.assertEqual(reply.status_code,503,reply.text)
        self.assertNotIn(TOKEN_A,reply.text)
        self.assertTrue(self.services()['telegram']['configured'])

    def test_clearing_configuration_only_affects_its_owner(self):
        self.save('email',SMTP_A)
        self.save('email',{**SMTP_A,'user':'bob@example.com','from':'bob@example.com'},self.b,self.headers[1])
        reply = self.a.delete('/api/notifications/config/email',headers=self.headers[0])
        self.assertEqual(reply.status_code,200,reply.text)
        self.assertFalse(self.services()['email']['configured'])
        self.assertTrue(self.services(self.b)['email']['configured'])

    def test_bot_change_during_connection_cannot_create_a_stale_binding(self):
        self.save('telegram', {'token':TOKEN_A})
        async def telegram(transport, method, payload):
            self.notifier.configs.save(self.people[0],'telegram',TelegramConfigInput(token=TOKEN_B),Config())
            return {'id':123456789,'is_bot':True,'first_name':'Test','username':'AliceTestBot'}
        with patch.object(Transport,'telegram',telegram):
            reply = self.a.post('/api/notifications/telegram/binding',headers=self.headers[0])
        self.assertEqual(reply.status_code,409,reply.text)
        with self.db.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM bindings WHERE user_id=?',(self.people[0],)).fetchone()[0],0)

    def test_personal_polling_keeps_separate_offsets_and_failed_bot_does_not_block_others(self):
        self.save('telegram', {'token':TOKEN_A})
        self.save('telegram', {'token':TOKEN_B},self.b,self.headers[1])
        async def get_me(transport, method, payload):
            return {'id':123456789,'is_bot':True,'first_name':'Test','username':'AliceTestBot'}
        with patch.object(Transport,'telegram',get_me):
            code = self.a.post('/api/notifications/telegram/binding',headers=self.headers[0]).json()['code']
        calls = []
        async def updates(transport, method, payload):
            calls.append((transport.config.telegram_token,payload['offset']))
            if transport.config.telegram_token == TOKEN_B:
                raise RuntimeError(TOKEN_B)
            return [] if payload['offset'] else [{'update_id':21,'message':{'chat':{'id':12345,'type':'private'},'text':f'/start {code}'}}]
        with patch.object(Transport,'telegram',updates), self.assertLogs('simkeep.notifications',level='WARNING') as logs:
            asyncio.run(self.notifier.poll())
            asyncio.run(self.notifier.poll())
        self.assertCountEqual(calls,[(TOKEN_A,0),(TOKEN_B,0),(TOKEN_A,22),(TOKEN_B,0)])
        self.assertTrue(self.a.get('/api/workspace').json()['workspace']['settings']['telegramVerified'])
        self.assertNotIn(TOKEN_B,' '.join(logs.output))

    def test_smtp_connection_check_authenticates_without_sending_email(self):
        self.save('email',SMTP_A)
        commands = []
        class SMTP:
            def __init__(self, host, port, **kwargs): commands.append(('connect',host,port))
            def __enter__(self): return self
            def __exit__(self, *args): commands.append(('quit',))
            def ehlo_or_helo_if_needed(self): commands.append(('hello',))
            def starttls(self, **kwargs): commands.append(('starttls',))
            def ehlo(self): commands.append(('hello-tls',))
            def login(self, user, password): commands.append(('login',user,password))
            def send_message(self, message): raise AssertionError('Connection checking must not send email')
        with patch('server.notifications.smtplib.SMTP',SMTP):
            reply = self.a.post('/api/notifications/config/email/check',headers=self.headers[0])
        self.assertEqual(reply.status_code,200,reply.text)
        self.assertTrue(reply.json()['checked'])
        self.assertEqual(commands,[('connect','smtp.example.com',587),('hello',),('starttls',),('hello-tls',),('login','alice@example.com',' password $ with spaces '),('quit',)])

    def test_fake_token_with_same_bot_prefix_cannot_reserve_another_persons_credentials(self):
        self.save('telegram',{'token':'123456789:'+'X'*35})
        self.save('telegram',{'token':TOKEN_A},self.b,self.headers[1])
        self.assertTrue(self.services(self.b)['telegram']['configured'])
        # The actual full credential remains exclusive, including canonical ID spelling.
        reply = self.a.put('/api/notifications/config/telegram',headers=self.headers[0],json={'token':'000'+TOKEN_A})
        self.assertEqual(reply.status_code,409,reply.text)

    def test_repaired_smtp_retries_failed_reminder_without_resending_a_sent_job(self):
        self.save('email',SMTP_A)
        reply = self.a.post('/api/cards',headers=self.headers[0],json={'name':'Personal SIM','provider':'Example','type':'SIM','country':'US','activatedAt':'2026-01-01','rules':[{'action':'sms','interval':90,'unit':'days','anchor':'completion','dueDate':'2026-10-07'}]})
        self.assertEqual(reply.status_code,201,reply.text)
        with self.db.connect(write=True) as conn:
            settings = decode(conn.execute('SELECT settings FROM users WHERE id=?',(self.people[0],)).fetchone()[0])
            settings.update(email=True,emailVerified=True)
            conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(settings),self.people[0]))
        now = datetime(2026,10,4,1,0,tzinfo=timezone.utc)
        self.notifier.enqueue(now)
        with patch.object(Transport,'smtp',side_effect=RuntimeError('old-password')):
            for attempt in range(5):
                asyncio.run(self.notifier.deliver(now+timedelta(minutes=10*attempt)))
        self.assertEqual(self.a.get('/api/workspace').json()['workspace']['notifications'][0]['status'],'failed')
        self.save('email',{**SMTP_A,'password':'corrected-password'})
        delivered = []
        def smtp(transport, destination, text): delivered.append(destination)
        with patch.object(Transport,'smtp',smtp):
            self.notifier.enqueue(now+timedelta(minutes=50))
            asyncio.run(self.notifier.deliver(now+timedelta(minutes=50)))
            self.save('email',{**SMTP_A,'password':'another-password'})
            self.notifier.enqueue(now+timedelta(minutes=60))
            asyncio.run(self.notifier.deliver(now+timedelta(minutes=60)))
        self.assertEqual(delivered,['alice@example.com'])
        jobs = self.a.get('/api/workspace').json()['workspace']['notifications']
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['status'],'sent')


if __name__ == '__main__':
    unittest.main()
