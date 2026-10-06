import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from pathlib import Path
from fastapi.testclient import TestClient

try:
    from server.main import create_app
except ImportError:
    create_app = None


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(create_app,'Authenticated card API must be implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name)/'test.db'
        self.app = create_app(self.db, start_worker=False)
        self.a = TestClient(self.app)
        self.b = TestClient(self.app)
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)
        for client,name in [(self.a,'Alice'),(self.b,'Bob')]:
            response = client.post('/api/auth/register',json={'name':name,'email':f'{name.lower()}@example.com','password':'safe-password-123'})
            self.assertEqual(response.status_code,201,response.text)

    def headers(self,client):
        return {'X-CSRF-Token':client.get('/api/auth/me').json()['csrfToken']}

    def card_payload(self):
        today = date.today().isoformat()
        return dict(name='My SIM',provider='Example',type='eSIM',country='US',phone='+1 202 555 0100',activatedAt='2026-01-01',notes='',plan='',rules=[dict(action='sms',interval=90,unit='days',anchor='completion',dueDate=today,instructions='发送短信')])

    def create_card(self,client=None):
        client = client or self.a
        response = client.post('/api/cards',headers=self.headers(client),json=self.card_payload())
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['workspace']['cards'][0]

    def test_login_cookie_csrf_logout(self):
        cookie = self.a.cookies.get('simkeep_session')
        self.assertTrue(cookie)
        self.assertEqual(self.a.post('/api/cards',json=self.card_payload()).status_code,403)
        self.assertEqual(self.a.post('/api/auth/logout',headers=self.headers(self.a)).status_code,200)
        self.assertEqual(self.a.get('/api/workspace').status_code,401)
        self.assertEqual(self.a.post('/api/auth/login',json={'email':'alice@example.com','password':'wrong-password'}).status_code,401)
        self.assertEqual(self.a.post('/api/auth/login',json={'email':'alice@example.com','password':'safe-password-123'}).status_code,200)
        self.assertEqual(self.a.get('/api/workspace').status_code,200)

    def test_card_rule_platform_and_history_are_private(self):
        card = self.create_card()
        self.assertEqual(self.b.get('/api/workspace').json()['workspace']['cards'],[])
        self.assertEqual(self.b.get(f"/api/cards/{card['id']}").status_code,404)
        self.assertEqual(self.b.post(f"/api/cards/{card['id']}/archive",headers=self.headers(self.b),json={'archived':True,'version':card['version']}).status_code,404)
        self.assertEqual(self.b.post(f"/api/cards/{card['id']}/platforms",headers=self.headers(self.b),json={'name':'Google','account':'a','purpose':'auth','version':card['version']}).status_code,404)
        rule = card['rules'][0]
        self.assertEqual(self.b.post(f"/api/rules/{rule['id']}/completions",headers=self.headers(self.b),json={'completedAt':date.today().isoformat(),'note':'','requestId':'other-user-attempt','version':rule['version']}).status_code,404)
        self.assertEqual(len(self.a.get('/api/workspace').json()['workspace']['cards']),1)

    def test_completion_is_server_calculated_and_idempotent(self):
        card = self.create_card()
        rule = card['rules'][0]
        payload = {'completedAt':date.today().isoformat(),'note':'done','requestId':'one-logical-operation','version':rule['version']}
        url=f"/api/rules/{rule['id']}/completions"
        first = self.a.post(url,headers=self.headers(self.a),json=payload)
        self.assertEqual(first.status_code,200,first.text)
        second = self.a.post(url,headers=self.headers(self.a),json=payload)
        self.assertEqual(second.status_code,200,second.text)
        workspace=second.json()['workspace']
        self.assertEqual(len(workspace['events']),1)
        self.assertEqual(workspace['cards'][0]['rules'][0]['dueDate'],(date.today()+timedelta(days=90)).isoformat())
        payload['requestId']='another-operation'
        self.assertEqual(self.a.post(url,headers=self.headers(self.a),json=payload).status_code,409)

    def test_persisted_card_survives_application_recreation(self):
        card=self.create_card()
        other=TestClient(create_app(self.db,start_worker=False))
        self.addCleanup(other.close)
        other.post('/api/auth/login',json={'email':'alice@example.com','password':'safe-password-123'})
        self.assertEqual(other.get('/api/workspace').json()['workspace']['cards'][0]['id'],card['id'])

    def test_settings_validation_and_credentials_not_exposed(self):
        payload={'timezone':'Asia/Shanghai','time':'09:00','offsets':[7,3,1],'overdue':True,'telegram':True,'email':True,'emailAddress':'alice@example.com'}
        response=self.a.put('/api/settings',headers=self.headers(self.a),json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['workspace']['settings']['emailVerified'])
        self.assertNotIn('smtpPassword',response.text)
        payload['timezone']='Invalid/Zone'
        self.assertEqual(self.a.put('/api/settings',headers=self.headers(self.a),json=payload).status_code,422)

    def test_card_update_rejects_old_version_and_history_conflict(self):
        card=self.create_card()
        payload=self.card_payload()
        payload.pop('rules')
        payload['version']=card['version']
        payload['name']='Renamed'
        first=self.a.put(f"/api/cards/{card['id']}",headers=self.headers(self.a),json=payload)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.a.put(f"/api/cards/{card['id']}",headers=self.headers(self.a),json=payload).status_code,409)

    def test_concurrent_completions_only_advance_once(self):
        card=self.create_card()
        rule=card['rules'][0]
        headers=self.headers(self.a)
        def submit(request_id):
            return self.a.post(f"/api/rules/{rule['id']}/completions",headers=headers,json={'completedAt':date.today().isoformat(),'note':'','requestId':request_id,'version':rule['version']}).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses=list(executor.map(submit,['concurrent-one','concurrent-two']))
        self.assertEqual(sorted(statuses),[200,409])
        self.assertEqual(len(self.a.get('/api/workspace').json()['workspace']['events']),1)

    def test_activation_edit_checks_older_history_after_later_completion(self):
        card=self.create_card()
        rule=card['rules'][0]
        for completed,request_id in [('2026-02-01','older-history'),('2026-09-01','later-history')]:
            response=self.a.post(f"/api/rules/{rule['id']}/completions",headers=self.headers(self.a),json={'completedAt':completed,'note':'','requestId':request_id,'version':rule['version']})
            self.assertEqual(response.status_code,200,response.text)
            card=response.json()['workspace']['cards'][0]
            rule=card['rules'][0]
        payload=self.card_payload()
        payload.pop('rules')
        payload.update(activatedAt='2026-05-01',version=card['version'])
        self.assertEqual(self.a.put(f"/api/cards/{card['id']}",headers=self.headers(self.a),json=payload).status_code,422)

    def test_bad_length_and_validation_never_echo_password(self):
        response=self.a.get('/api/health',headers={'Content-Length':'invalid'})
        self.assertEqual(response.status_code,400)
        response=self.a.post('/api/auth/register',json={'name':'Test','email':'test@example.com','password':'secret12'})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('secret12',response.text)

    def test_foreign_origin_cannot_create_a_card(self):
        headers={**self.headers(self.a),'Origin':'http://another-site.example'}
        self.assertEqual(self.a.post('/api/cards',headers=headers,json=self.card_payload()).status_code,403)
        self.assertEqual(self.a.get('/api/workspace').json()['workspace']['cards'],[])


if __name__=='__main__':
    unittest.main()
