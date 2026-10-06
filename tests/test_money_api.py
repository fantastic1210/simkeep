import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from fastapi.testclient import TestClient
from server.main import create_app


class MoneyApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.db'
        self.app=create_app(self.path,start_worker=False)
        self.client=TestClient(self.app)
        self.addCleanup(self.client.close)
        response=self.client.post('/api/auth/register',json={'name':'Money Test','email':'money@example.com','password':'long-password-123'})
        self.headers={'X-CSRF-Token':response.json()['csrfToken']}

    def payload(self):
        return {'name':'Money SIM','provider':'Example','type':'SIM','country':'US','activatedAt':'2026-01-01','balances':[{'currency':'USD','amount':'0.30'},{'currency':'JPY','amount':'1000'}],'rules':[{'action':'sms','interval':90,'unit':'days','anchor':'completion','dueDate':date.today().isoformat(),'cost':{'currency':'USD','amount':'0.10'}}]}

    def create_card(self):
        response=self.client.post('/api/cards',headers=self.headers,json=self.payload())
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['workspace']['cards'][0]

    def complete(self,card,request_id='money-operation',**extra):
        rule=card['rules'][0]
        payload={'completedAt':date.today().isoformat(),'note':'','requestId':request_id,'version':rule['version'],**extra}
        return self.client.post(f"/api/rules/{rule['id']}/completions",headers=self.headers,json=payload)

    def test_multiple_balances_and_rule_cost_persist_after_restart(self):
        card=self.create_card()
        with TestClient(create_app(self.path,start_worker=False)) as client:
            client.post('/api/auth/login',json={'email':'money@example.com','password':'long-password-123'})
            persisted=client.get('/api/workspace').json()['workspace']['cards'][0]
        self.assertEqual(persisted['balances'],card['balances'])
        self.assertEqual(persisted['rules'][0]['cost'],{'currency':'USD','amount':'0.10'})

    def test_explicit_deduction_and_duplicate_submit_are_atomic(self):
        card=self.create_card()
        payload={'balanceAction':'deduct','cardVersion':card['version']}
        first=self.complete(card,**payload)
        self.assertEqual(first.status_code,200,first.text)
        retry=self.complete(card,**payload)
        self.assertEqual(retry.status_code,200,retry.text)
        workspace=retry.json()['workspace']
        self.assertEqual(workspace['cards'][0]['balances'],[{'currency':'USD','amount':'0.20'},{'currency':'JPY','amount':'1000'}])
        self.assertEqual(len(workspace['events']),1)
        event=workspace['events'][0]
        self.assertEqual(event['cost'],{'currency':'USD','amount':'0.10'})
        self.assertEqual(event['balanceBefore']['amount'],'0.30')
        self.assertEqual(event['balanceAfter']['amount'],'0.20')

    def test_record_only_keeps_balance_and_historical_actual_cost(self):
        card=self.create_card()
        response=self.complete(card,cost={'currency':'GBP','amount':'2.5'})
        self.assertEqual(response.status_code,200,response.text)
        workspace=response.json()['workspace']
        self.assertEqual(workspace['cards'][0]['balances'],card['balances'])
        self.assertEqual(workspace['events'][0]['cost'],{'currency':'GBP','amount':'2.50'})
        rule=workspace['cards'][0]['rules'][0]
        edited={k:rule[k] for k in ['action','interval','unit','anchor','dueDate','instructions','version']}
        edited['cost']={'currency':'USD','amount':'5.00'}
        updated=self.client.put(f"/api/rules/{rule['id']}",headers=self.headers,json=edited)
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()['workspace']['events'][0]['cost'],{'currency':'GBP','amount':'2.50'})

    def test_changed_retry_cannot_silently_discard_cost_or_balance_action(self):
        card=self.create_card()
        first=self.complete(card,cost={'currency':'USD','amount':'0.10'})
        self.assertEqual(first.status_code,200,first.text)
        for changed in [
            {'cost':{'currency':'USD','amount':'0.20'}},
            {'cost':{'currency':'USD','amount':'0.10'},'balanceAction':'deduct','cardVersion':card['version']},
            {'cost':None},
            {'note':'changed after a lost response'},
        ]:
            with self.subTest(changed=changed):
                retry=self.complete(card,**changed)
                self.assertEqual(retry.status_code,409,retry.text)
        retry=self.complete(card,cost={'currency':'USD','amount':'0.100'})
        self.assertEqual(retry.status_code,200,retry.text)
        workspace=retry.json()['workspace']
        self.assertEqual(workspace['cards'][0]['balances'],card['balances'])
        self.assertEqual(len(workspace['events']),1)
        self.assertEqual(workspace['events'][0]['cost'],{'currency':'USD','amount':'0.10'})

    def test_insufficient_balance_rejects_entire_completion(self):
        card=self.create_card()
        response=self.complete(card,cost={'currency':'USD','amount':'0.31'},balanceAction='deduct',cardVersion=card['version'])
        self.assertEqual(response.status_code,422,response.text)
        workspace=self.client.get('/api/workspace').json()['workspace']
        self.assertEqual(workspace['cards'][0],card)
        self.assertEqual(workspace['events'],[])

    def test_stale_card_balance_version_rejects_deduction(self):
        card=self.create_card()
        changed={**self.payload(),'rules':[],'version':card['version'],'balances':[{'currency':'USD','amount':'8.00'}]}
        response=self.client.put(f"/api/cards/{card['id']}",headers=self.headers,json=changed)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.complete(card,balanceAction='deduct',cardVersion=card['version']).status_code,409)

    def test_duplicate_currency_and_invalid_precision_are_rejected(self):
        payload=self.payload()
        payload['balances'].append({'currency':'USD','amount':'9.00'})
        self.assertEqual(self.client.post('/api/cards',headers=self.headers,json=payload).status_code,422)
        payload=self.payload()
        payload['rules'][0]['cost']['amount']='0.001'
        self.assertEqual(self.client.post('/api/cards',headers=self.headers,json=payload).status_code,422)

    def test_legacy_card_edits_preserve_existing_money(self):
        card=self.create_card()
        changed={k:v for k,v in self.payload().items() if k not in ('balances','rules')}
        changed.update(name='Renamed',version=card['version'])
        response=self.client.put(f"/api/cards/{card['id']}",headers=self.headers,json=changed)
        self.assertEqual(response.status_code,200,response.text)
        updated=response.json()['workspace']['cards'][0]
        self.assertEqual(updated['balances'],card['balances'])
        rule=updated['rules'][0]
        fields={k:rule[k] for k in ['action','interval','unit','anchor','dueDate','instructions','version']}
        response=self.client.put(f"/api/rules/{rule['id']}",headers=self.headers,json=fields)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['workspace']['cards'][0]['rules'][0]['cost'],card['rules'][0]['cost'])

    def test_topup_creates_new_currency_and_saves_balance_snapshot(self):
        payload=self.payload()
        payload['rules'][0].update(action='topup',cost={'currency':'HKD','amount':'10.50'})
        response=self.client.post('/api/cards',headers=self.headers,json=payload)
        self.assertEqual(response.status_code,201,response.text)
        card=response.json()['workspace']['cards'][0]
        response=self.complete(card,balanceAction='credit',cardVersion=card['version'])
        self.assertEqual(response.status_code,200,response.text)
        workspace=response.json()['workspace']
        self.assertEqual(workspace['cards'][0]['balances'][-1],{'currency':'HKD','amount':'10.50'})
        self.assertEqual(workspace['events'][0]['balanceBefore'],{'currency':'HKD','amount':'0.00'})

    def test_concurrent_requests_cannot_deduct_twice(self):
        card=self.create_card()
        def submit(request_id):
            return self.complete(card,request_id,balanceAction='deduct',cardVersion=card['version']).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(submit,['money-concurrent-one','money-concurrent-two']))
        self.assertEqual(sorted(statuses),[200,409])
        workspace=self.client.get('/api/workspace').json()['workspace']
        self.assertEqual(workspace['cards'][0]['balances'][0]['amount'],'0.20')
        self.assertEqual(len(workspace['events']),1)

    def test_other_account_cannot_change_or_deduct_balance(self):
        card=self.create_card()
        with TestClient(self.app) as other:
            response=other.post('/api/auth/register',json={'name':'Other','email':'other-money@example.com','password':'long-password-123'})
            headers={'X-CSRF-Token':response.json()['csrfToken']}
            payload={**self.payload(),'rules':[],'version':card['version']}
            self.assertEqual(other.put(f"/api/cards/{card['id']}",headers=headers,json=payload).status_code,404)
            rule=card['rules'][0]
            response=other.post(f"/api/rules/{rule['id']}/completions",headers=headers,json={'completedAt':date.today().isoformat(),'requestId':'foreign-deduction','version':rule['version'],'balanceAction':'deduct','cardVersion':card['version']})
            self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.get('/api/workspace').json()['workspace']['cards'][0],card)
