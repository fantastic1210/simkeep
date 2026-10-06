import asyncio
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from server.db import decode, encode
from server.main import create_app

try:
    from server.notifications import Config, Notifier
except ImportError:
    Config = Notifier = None


class RecordingTransport:
    """Only the external delivery boundary is replaced; queue and DB stay real."""
    def __init__(self):
        self.messages = []
        self.failures = {}

    async def send(self, channel, destination, text):
        if self.failures.get(channel, 0):
            self.failures[channel] -= 1
            raise RuntimeError('secret-token-must-never-reach-browser')
        self.messages.append((channel, destination, text))

    async def bot_username(self):
        return 'SimkeepTestBot'

    async def updates(self, offset):
        return []


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Notifier, 'Real notification service must be implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'test.db'
        self.config = Config(telegram_token='server-secret-token', smtp_host='smtp.example.com', smtp_from='bot@example.com', public_url='http://example.com')
        self.app = create_app(self.path, start_worker=False, config=self.config)
        self.a = TestClient(self.app)
        self.b = TestClient(self.app)
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)
        for client, name in [(self.a, 'Alice'), (self.b, 'Bob')]:
            response = client.post('/api/auth/register', json={'name':name,'email':f'{name.lower()}@example.com','password':'long-password-123'})
            self.assertEqual(response.status_code, 201, response.text)
        self.db = self.app.state.db
        self.notifier = self.app.state.notifier
        self.transport = RecordingTransport()
        self.notifier.transport = self.transport
        self.owner = self.a.get('/api/auth/me').json()['user']['id']
        self.headers = {'X-CSRF-Token': self.a.get('/api/auth/me').json()['csrfToken']}
        self.now = datetime(2026, 10, 4, 1, 0, tzinfo=timezone.utc)
        self.card = self.a.post('/api/cards', headers=self.headers, json={'name':'Private SIM','provider':'Example','type':'SIM','country':'US','activatedAt':'2026-01-01','rules':[{'action':'sms','interval':90,'unit':'days','anchor':'completion','dueDate':'2026-10-07','instructions':'发送一条短信'}]}).json()['workspace']['cards'][0]

    def enable(self, verified=True):
        with self.db.connect(write=True) as conn:
            settings = decode(conn.execute('SELECT settings FROM users WHERE id=?', (self.owner,)).fetchone()[0])
            settings.update(telegram=True, email=True, chatId='123456', telegramVerified=verified, emailVerified=verified)
            conn.execute('UPDATE users SET settings=? WHERE id=?', (encode(settings), self.owner))

    def tick(self, now=None):
        self.notifier.enqueue(now or self.now)
        asyncio.run(self.notifier.deliver(now or self.now))

    def test_local_time_deduplication_and_sent_jobs_survive_restart(self):
        self.enable()
        self.tick(datetime(2026, 10, 4, 0, 59, tzinfo=timezone.utc))
        self.assertEqual(self.transport.messages, [])
        self.tick()
        self.assertEqual(len(self.transport.messages), 2)
        self.assertIn('Private SIM', self.transport.messages[0][2])
        self.assertIn('2026-10-07', self.transport.messages[0][2])
        self.tick()
        restarted = Notifier(self.db, self.config, self.transport)
        restarted.recover()
        restarted.enqueue(self.now)
        asyncio.run(restarted.deliver(self.now))
        self.assertEqual(len(self.transport.messages), 2)
        self.assertNotIn('server-secret-token', self.a.get('/api/workspace').text)

    def test_unverified_and_archived_cards_never_send(self):
        self.enable(verified=False)
        self.tick()
        self.assertEqual(self.transport.messages, [])
        self.enable()
        self.notifier.enqueue(self.now)
        self.a.post(f"/api/cards/{self.card['id']}/archive", headers=self.headers, json={'archived':True,'version':self.card['version']})
        asyncio.run(self.notifier.deliver(self.now))
        self.assertEqual(self.transport.messages, [])

    def test_old_rule_jobs_cancel_after_completion(self):
        self.enable()
        self.notifier.enqueue(self.now)
        rule = self.card['rules'][0]
        response = self.a.post(f"/api/rules/{rule['id']}/completions", headers=self.headers, json={'completedAt':'2026-10-04','note':'','requestId':'record-once-only','version':rule['version']})
        self.assertEqual(response.status_code, 200, response.text)
        asyncio.run(self.notifier.deliver(self.now))
        self.assertEqual(self.transport.messages, [])
        self.assertTrue(all(x['status']=='cancelled' for x in self.a.get('/api/workspace').json()['workspace']['notifications']))

    def test_unconfigured_channel_does_not_starve_email_and_stale_jobs_cancel(self):
        self.enable()
        with self.db.connect(write=True) as conn:
            original=decode(conn.execute('SELECT document FROM cards WHERE id=?',(self.card['id'],)).fetchone()[0])
            settings=decode(conn.execute('SELECT settings FROM users WHERE id=?',(self.owner,)).fetchone()[0])
            settings['email']=False
            conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(settings),self.owner))
            # Arrange 50 real active rules so the previous batch was fully occupied.
            for index in range(49):
                card={**original,'id':f'card-{index}','rules':[{**original['rules'][0],'id':f'rule-{index}'}]}
                conn.execute('INSERT INTO cards VALUES(?,?,?)',(card['id'],self.owner,encode(card)))
        self.notifier.enqueue(self.now)
        self.notifier.config=Config(smtp_host='smtp.example.com',smtp_from='bot@example.com')
        with self.db.connect(write=True) as conn:
            settings['email']=True
            conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(settings),self.owner))
        self.tick()
        self.assertEqual(len(self.transport.messages),50)
        self.assertTrue(all(channel=='email' for channel,_,_ in self.transport.messages))
        with self.db.connect(write=True) as conn:
            conn.execute("UPDATE notification_jobs SET ready_at=ready_at-86400 WHERE channel='telegram'")
        self.tick(datetime(2026,10,5,1,0,tzinfo=timezone.utc))
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM notification_jobs WHERE channel='telegram' AND status='cancelled'").fetchone()[0],50)

    def test_rebind_check_waits_for_this_binding(self):
        self.enable()
        code=self.a.post('/api/notifications/telegram/binding',headers=self.headers).json()['code']
        check=lambda:self.a.post('/api/notifications/telegram/binding/check',headers=self.headers,json={'code':code})
        response=check()
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['bindingStatus'],'waiting')
        self.assertTrue(self.notifier.process_update({'message':{'chat':{'id':654321,'type':'private'},'text':f'/start {code}'}}))
        self.assertEqual(check().json()['bindingStatus'],'bound')
        bheaders={'X-CSRF-Token':self.b.get('/api/auth/me').json()['csrfToken']}
        other=self.b.post('/api/notifications/telegram/binding/check',headers=bheaders,json={'code':code})
        self.assertEqual(other.json()['bindingStatus'],'expired')

    def test_real_message_matches_suffix_preview(self):
        self.enable()
        with self.db.connect(write=True) as conn:
            card=decode(conn.execute('SELECT document FROM cards WHERE id=?',(self.card['id'],)).fetchone()[0])
            card['phone']='+44 7700 900123'
            conn.execute('UPDATE cards SET document=? WHERE id=?',(encode(card),card['id']))
        self.tick()
        for _,_,text in self.transport.messages:
            self.assertIn('尾号 0123',text)
            self.assertNotIn('+44 7700 900123',text)

    def test_reminder_includes_estimated_cost_and_matching_balance(self):
        self.enable()
        with self.db.connect(write=True) as conn:
            card=decode(conn.execute('SELECT document FROM cards WHERE id=?',(self.card['id'],)).fetchone()[0])
            card['balances']=[{'currency':'USD','amount':'10.50'}]
            card['rules'][0]['cost']={'currency':'USD','amount':'2.50'}
            conn.execute('UPDATE cards SET document=? WHERE id=?',(encode(card),card['id']))
        self.tick()
        for _,_,text in self.transport.messages:
            self.assertIn('续期金额：USD 2.50',text)
            self.assertIn('同币种余额：USD 10.50',text)

    def test_transport_failures_retry_without_blocking_other_channel(self):
        self.enable()
        self.transport.failures['telegram'] = 1
        self.tick()
        self.assertEqual([x[0] for x in self.transport.messages], ['email'])
        self.assertNotIn('secret-token-must', self.a.get('/api/workspace').text)
        self.tick(datetime(2026, 10, 4, 1, 3, tzinfo=timezone.utc))
        self.assertEqual(sorted(x[0] for x in self.transport.messages), ['email','telegram'])
        self.tick(datetime(2026, 10, 4, 1, 6, tzinfo=timezone.utc))
        self.assertEqual(len(self.transport.messages), 2)

    def test_cancelled_pending_job_can_resume_without_resending_sent_job(self):
        self.enable()
        self.notifier.enqueue(self.now)
        settings = self.a.get('/api/workspace').json()['workspace']['settings']
        fields = ['timezone','time','offsets','overdue','telegram','email','emailAddress']
        payload = {k:settings[k] for k in fields}
        payload['telegram'] = payload['email'] = False
        self.a.put('/api/settings', headers=self.headers, json=payload)
        payload['telegram'] = payload['email'] = True
        self.a.put('/api/settings', headers=self.headers, json=payload)
        self.tick()
        self.assertEqual(len(self.transport.messages), 2)
        self.a.put('/api/settings', headers=self.headers, json=payload)
        self.tick()
        self.assertEqual(len(self.transport.messages), 2)

    def test_telegram_binding_is_private_expiring_and_single_use(self):
        response = self.a.post('/api/notifications/telegram/binding', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        code = response.json()['code']
        group = {'message':{'chat':{'id':-123,'type':'group'},'text':f'/start {code}'}}
        self.assertFalse(self.notifier.process_update(group))
        private = {'message':{'chat':{'id':123456,'type':'private'},'text':f'/start {code}'}}
        self.assertTrue(self.notifier.process_update(private))
        self.assertFalse(self.notifier.process_update(private))
        settings = self.a.get('/api/workspace').json()['workspace']['settings']
        self.assertTrue(settings['telegramVerified'])
        self.assertEqual(settings['chatId'], '123456')
        bheaders = {'X-CSRF-Token':self.b.get('/api/auth/me').json()['csrfToken']}
        other = self.b.post('/api/notifications/telegram/binding', headers=bheaders).json()['code']
        private['message']['text'] = f'/start {other}'
        self.assertFalse(self.notifier.process_update(private))
        self.assertFalse(self.b.get('/api/workspace').json()['workspace']['settings']['telegramVerified'])
        expired = self.a.post('/api/notifications/telegram/binding', headers=self.headers).json()['code']
        with self.db.connect(write=True) as conn:
            conn.execute("UPDATE bindings SET expires_at=0 WHERE kind='telegram'")
        private['message']['text'] = f'/start {expired}'
        self.assertFalse(self.notifier.process_update(private))

    def test_email_confirmation_is_owner_scoped_and_destination_bound(self):
        response = self.a.post('/api/notifications/email/verify', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        code = re.search(r'\b\d{6}\b', self.transport.messages[-1][2]).group()
        bheaders = {'X-CSRF-Token':self.b.get('/api/auth/me').json()['csrfToken']}
        self.assertEqual(self.b.post('/api/notifications/email/confirm', headers=bheaders, json={'code':code}).status_code, 422)
        self.assertEqual(self.a.post('/api/notifications/email/confirm', headers=self.headers, json={'code':code}).status_code, 200)
        self.assertTrue(self.a.get('/api/workspace').json()['workspace']['settings']['emailVerified'])
        self.assertEqual(self.a.post('/api/notifications/test/email', headers=self.headers).status_code, 200)
        self.assertEqual(self.b.post('/api/notifications/test/email', headers=bheaders).status_code, 422)
        self.a.post('/api/notifications/email/verify', headers=self.headers)
        code = re.search(r'\b\d{6}\b', self.transport.messages[-1][2]).group()
        self.a.put('/api/settings', headers=self.headers, json={'timezone':'Asia/Shanghai','time':'09:00','offsets':[3],'overdue':True,'telegram':False,'email':True,'emailAddress':'new@example.com'})
        self.assertEqual(self.a.post('/api/notifications/email/confirm', headers=self.headers, json={'code':code}).status_code, 422)

    def test_email_attempt_limit_and_unconfigured_service(self):
        self.a.post('/api/notifications/email/verify', headers=self.headers)
        code = re.search(r'\b\d{6}\b', self.transport.messages[-1][2]).group()
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.a.post('/api/notifications/email/confirm', headers=self.headers, json={'code':wrong}).status_code, 422)
        self.assertEqual(self.a.post('/api/notifications/email/confirm', headers=self.headers, json={'code':code}).status_code, 422)
        app = create_app(Path(self.temp.name)/'no-config.db', start_worker=False, config=Config())
        with TestClient(app) as client:
            client.post('/api/auth/register', json={'name':'Test','email':'test@example.com','password':'long-password-123'})
            headers = {'X-CSRF-Token':client.get('/api/auth/me').json()['csrfToken']}
            self.assertEqual(client.post('/api/notifications/email/verify', headers=headers).status_code, 503)
            self.assertEqual(client.post('/api/notifications/telegram/binding', headers=headers).status_code, 503)

    def test_overdue_notification_is_once_per_local_day(self):
        self.enable()
        with self.db.connect(write=True) as conn:
            card = decode(conn.execute('SELECT document FROM cards WHERE id=?',(self.card['id'],)).fetchone()[0])
            card['rules'][0]['dueDate']='2026-10-03'
            conn.execute('UPDATE cards SET document=? WHERE id=?',(encode(card),card['id']))
        self.tick()
        self.tick()
        self.assertEqual(len(self.transport.messages),2)
        self.tick(datetime(2026,10,5,1,0,tzinfo=timezone.utc))
        self.assertEqual(len(self.transport.messages),4)


if __name__ == '__main__':
    unittest.main()
