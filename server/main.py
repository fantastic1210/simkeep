from __future__ import annotations

import asyncio
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends,FastAPI,HTTPException,Request,Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from .auth import DUMMY_HASH,RateLimit,digest,hash_password,verify_password
from .db import Database,decode,encode
from .domain import business_today,check_activation,check_completion,next_due
from .models import ArchiveInput,CardInput,Completion,PlatformInput,Register,Login,RuleInput,SettingsInput
from .money import apply_balance

ROOT=Path(__file__).resolve().parent.parent
COLORS={'giffgaff':'#242C40','MobiMatter':'#F38B4A','Ultra Mobile':'#8562CA','3HK':'#457DE7','Tello':'#30A593','Airalo':'#D65870'}


def create_app(db_path=None,start_worker=True,config=None):
    db=Database(db_path or os.getenv('SIMKEEP_DB',str(ROOT/'data'/'simkeep.db')))
    rate=RateLimit()
    from .notifications import Config,Notifier
    configuration=config or Config.from_env()
    notifier=Notifier(db,configuration)

    @asynccontextmanager
    async def lifespan(app):
        worker=asyncio.create_task(notifier.run()) if start_worker else None
        try:
            yield
        finally:
            if worker:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass

    app=FastAPI(title='续卡 SIMKEEP',lifespan=lifespan,docs_url=None,redoc_url=None)
    app.state.db=db
    app.state.notifier=notifier

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exception):
        errors=[{key:error[key] for key in ('loc','msg','type')} for error in exception.errors()]
        return JSONResponse({'detail':errors},status_code=422)

    @app.exception_handler(ValueError)
    async def invalid_value(request,exception):
        return JSONResponse({'detail':str(exception)},status_code=422)

    @app.middleware('http')
    async def protect_response(request,call_next):
        if request.url.path.startswith('/api/'):
            try:
                length=int(request.headers.get('content-length','0') or 0)
            except ValueError:
                return JSONResponse({'detail':'请求长度无效'},status_code=400)
            if length < 0:
                return JSONResponse({'detail':'请求长度无效'},status_code=400)
            if length > 1024*1024:
                return JSONResponse({'detail':'请求内容过大'},status_code=413)
            if request.method not in ('GET','HEAD','OPTIONS'):
                origin=request.headers.get('origin')
                allowed={str(request.base_url).rstrip('/')}
                if configuration.public_url:
                    allowed.add(configuration.public_url.rstrip('/'))
                if origin and origin.rstrip('/') not in allowed:
                    return JSONResponse({'detail':'请求来源不匹配'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['X-Frame-Options']='DENY'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    def session(request:Request):
        token=request.cookies.get('simkeep_session','')
        with db.connect() as conn:
            row=conn.execute('SELECT users.*,sessions.csrf,sessions.token_hash FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>?',(digest(token),time.time())).fetchone()
        if not row:
            raise HTTPException(401,'请先登录')
        if request.method not in ('GET','HEAD','OPTIONS'):
            supplied=request.headers.get('x-csrf-token','')
            if not hmac.compare_digest(supplied,row['csrf']):
                raise HTTPException(403,'请求校验失败，请刷新页面后重试')
        return dict(row)

    def public_user(row):
        return {'id':row['id'],'email':row['email'],'name':row['name'],'initial':row['name'][0]}

    def workspace(user_id):
        with db.connect() as conn:
            person=conn.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
            cards=[decode(row['document']) for row in conn.execute('SELECT document FROM cards WHERE user_id=? ORDER BY rowid',(user_id,))]
            events=[decode(row['document']) for row in conn.execute('SELECT document FROM events WHERE user_id=? ORDER BY rowid',(user_id,))]
            logs=[dict(row) for row in conn.execute('SELECT id,channel,status,attempts,created_at,sent_at,error FROM notification_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(user_id,))]
        return {'version':2,'cards':cards,'events':events,'settings':decode(person['settings']),'services':notifier.configs.status(user_id,notifier.config),'notifications':logs}

    def result(user_id,**extra):
        return {'workspace':workspace(user_id),**extra}

    def card_for(conn,user_id,card_id):
        row=conn.execute('SELECT document FROM cards WHERE id=? AND user_id=?',(card_id,user_id)).fetchone()
        if not row:
            raise HTTPException(404,'找不到这张卡片')
        return decode(row['document'])

    def rule_for(conn,user_id,rule_id):
        for row in conn.execute('SELECT document FROM cards WHERE user_id=?',(user_id,)):
            card=decode(row['document'])
            for rule in card['rules']:
                if rule['id']==rule_id:
                    return card,rule
        raise HTTPException(404,'找不到这条续期规则')

    def expected(actual,supplied):
        if actual != supplied:
            raise HTTPException(409,'资料已更新，请刷新后再操作')

    def save_card(conn,owner,card):
        card['version']+=1
        conn.execute('UPDATE cards SET document=? WHERE id=? AND user_id=?',(encode(card),card['id'],owner))

    def cancel_jobs(conn,owner,card_id,rule_id=None):
        query="UPDATE notification_jobs SET status='cancelled' WHERE user_id=? AND card_id=? AND status IN ('pending','processing')"
        args=[owner,card_id]
        if rule_id:
            query+=' AND rule_id=?'
            args.append(rule_id)
        conn.execute(query,args)

    def new_rule(payload,card,old=None):
        rule=payload.model_dump(exclude={'version'})
        if old and 'cost' not in payload.model_fields_set:
            rule['cost']=old.get('cost')
        if rule['unit']=='months' and rule['interval']>120:
            raise ValueError('月份周期须为 1–120')
        if rule['dueDate']<card['activatedAt']:
            raise ValueError('到期日期不能早于卡片开通日期')
        if old and old.get('lastCompletedAt') and rule['dueDate']<=old['lastCompletedAt']:
            raise ValueError('到期日期须晚于上次完成日期')
        changed=old and any(old[key]!=rule[key] for key in ('dueDate','interval','unit','anchor'))
        return {**(old or {}),**rule,'id':old['id'] if old else str(uuid4()),'anchorDate':old['anchorDate'] if old and not changed else rule['dueDate'],'version':old['version']+1 if old else 1}

    def new_session(conn,user_id,response):
        token=secrets.token_urlsafe(32)
        csrf=secrets.token_urlsafe(24)
        conn.execute('DELETE FROM sessions WHERE expires_at<?',(time.time(),))
        conn.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),user_id,csrf,time.time()+30*86400))
        response.set_cookie('simkeep_session',token,max_age=30*86400,httponly=True,samesite='lax',secure=configuration.secure_cookies)
        return csrf

    @app.get('/api/health')
    def health():
        return {'status':'ok','app':'simkeep'}

    @app.post('/api/auth/register',status_code=201)
    def register(payload:Register,request:Request,response:Response):
        rate.check(('register',request.client.host),10,3600)
        user_id=str(uuid4())
        settings={'timezone':'Asia/Shanghai','time':'09:00','offsets':[7,3,1],'overdue':True,'telegram':False,'email':False,'emailAddress':payload.email,'emailVerified':False,'chatId':'','telegramVerified':False}
        hashed=hash_password(payload.password)
        try:
            with db.connect(write=True) as conn:
                conn.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(user_id,payload.email,payload.name,hashed,encode(settings),time.time()))
                csrf=new_session(conn,user_id,response)
        except sqlite3.IntegrityError:
            raise HTTPException(409,'这个邮箱已经注册，请直接登录') from None
        return {'user':{'id':user_id,'email':payload.email,'name':payload.name,'initial':payload.name[0]},'csrfToken':csrf,'workspace':workspace(user_id)}

    @app.post('/api/auth/login')
    def login(payload:Login,request:Request,response:Response):
        rate.check(('login',request.client.host),20,60)
        with db.connect(write=True) as conn:
            row=conn.execute('SELECT * FROM users WHERE email=?',(payload.email,)).fetchone()
            if not verify_password(payload.password,row['password_hash'] if row else DUMMY_HASH) or not row:
                raise HTTPException(401,'邮箱或密码不正确')
            csrf=new_session(conn,row['id'],response)
        return {'user':public_user(row),'csrfToken':csrf,'workspace':workspace(row['id'])}

    @app.get('/api/auth/me')
    def me(person=Depends(session)):
        return {'user':public_user(person),'csrfToken':person['csrf']}

    @app.post('/api/auth/logout')
    def logout(response:Response,person=Depends(session)):
        with db.connect(write=True) as conn:
            conn.execute('DELETE FROM sessions WHERE token_hash=?',(person['token_hash'],))
        response.delete_cookie('simkeep_session')
        return {'ok':True}

    @app.get('/api/workspace')
    def get_workspace(person=Depends(session)):
        return result(person['id'])

    @app.get('/api/cards/{card_id}')
    def get_card(card_id:str,person=Depends(session)):
        with db.connect() as conn:
            return {'card':card_for(conn,person['id'],card_id)}

    @app.post('/api/cards',status_code=201)
    def add_card(payload:CardInput,person=Depends(session)):
        owner=person['id']
        check_activation(None,[],payload.activatedAt,business_today(decode(person['settings'])['timezone']))
        card=payload.model_dump(exclude={'rules','version','balances'})
        card['balances']=[item.model_dump() for item in payload.balances or []]
        card.update(id=str(uuid4()),version=1,archived=False,platforms=[],rules=[],color=COLORS.get(payload.provider,'#5360EA'),mark='3' if payload.provider=='3HK' else payload.provider[0])
        card['phone']=card['phone'] or '数据卡 · 无号码'
        card['rules']=[new_rule(r,card) for r in payload.rules]
        with db.connect(write=True) as conn:
            if conn.execute('SELECT count(*) FROM cards WHERE user_id=?',(owner,)).fetchone()[0]>=1000:
                raise HTTPException(422,'每个账号最多保存 1000 张卡片')
            conn.execute('INSERT INTO cards VALUES(?,?,?)',(card['id'],owner,encode(card)))
        return result(owner)

    @app.put('/api/cards/{card_id}')
    def update_card(card_id:str,payload:CardInput,person=Depends(session)):
        owner=person['id']
        with db.connect(write=True) as conn:
            card=card_for(conn,owner,card_id)
            expected(card['version'],payload.version)
            if payload.rules:
                raise HTTPException(422,'请通过续期规则入口修改规则')
            events=[decode(r['document']) for r in conn.execute('SELECT document FROM events WHERE user_id=? AND card_id=?',(owner,card_id))]
            check_activation(card,events,payload.activatedAt,business_today(decode(person['settings'])['timezone']))
            card.update(payload.model_dump(exclude={'rules','version','balances'}))
            if payload.balances is not None:
                card['balances']=[item.model_dump() for item in payload.balances]
            card.update(color=COLORS.get(payload.provider,'#5360EA'),mark='3' if payload.provider=='3HK' else payload.provider[0])
            save_card(conn,owner,card)
        return result(owner)

    @app.post('/api/cards/{card_id}/archive')
    def archive(card_id:str,payload:ArchiveInput,person=Depends(session)):
        owner=person['id']
        with db.connect(write=True) as conn:
            card=card_for(conn,owner,card_id)
            expected(card['version'],payload.version)
            card['archived']=payload.archived
            save_card(conn,owner,card)
            cancel_jobs(conn,owner,card_id)
        return result(owner)

    @app.post('/api/cards/{card_id}/rules',status_code=201)
    def add_rule(card_id:str,payload:RuleInput,person=Depends(session)):
        owner=person['id']
        with db.connect(write=True) as conn:
            card=card_for(conn,owner,card_id)
            if len(card['rules'])>=20:
                raise HTTPException(422,'每张卡片最多设置 20 条续期规则')
            card['rules'].append(new_rule(payload,card))
            save_card(conn,owner,card)
        return result(owner)

    @app.put('/api/rules/{rule_id}')
    def update_rule(rule_id:str,payload:RuleInput,person=Depends(session)):
        owner=person['id']
        with db.connect(write=True) as conn:
            card,rule=rule_for(conn,owner,rule_id)
            expected(rule['version'],payload.version)
            replacement=new_rule(payload,card,rule)
            card['rules']=[replacement if r['id']==rule_id else r for r in card['rules']]
            save_card(conn,owner,card)
            cancel_jobs(conn,owner,card['id'],rule_id)
        return result(owner)

    @app.post('/api/rules/{rule_id}/completions')
    def complete(rule_id:str,payload:Completion,person=Depends(session)):
        owner=person['id']
        with db.connect(write=True) as conn:
            card,rule=rule_for(conn,owner,rule_id)
            previous=conn.execute('SELECT rule_id,document FROM events WHERE user_id=? AND request_id=?',(owner,payload.requestId)).fetchone()
            if previous:
                if previous['rule_id']!=rule_id:
                    raise HTTPException(409,'这次提交已用于另一条规则')
                recorded=decode(previous['document'])
                requested_cost=payload.cost.model_dump() if payload.cost else None
                changed=(payload.completedAt!=recorded['completedAt'] or payload.note!=recorded.get('note','') or payload.balanceAction!=recorded.get('balanceAction','none'))
                if 'cost' in payload.model_fields_set:
                    changed=changed or requested_cost!=recorded.get('cost')
                if changed:
                    raise HTTPException(409,'本次续期已保存，但重试内容有变化。请刷新卡片查看已保存的记录')
            else:
                expected(rule['version'],payload.version)
                check_completion(card,rule,payload.completedAt,business_today(decode(person['settings'])['timezone']))
                due=next_due(rule,payload.completedAt)
                cost=payload.cost.model_dump() if payload.cost else None
                if 'cost' not in payload.model_fields_set:
                    cost=rule.get('cost')
                before=after=None
                if payload.balanceAction!='none':
                    if payload.cardVersion is None:
                        raise ValueError('更新余额时须提交当前卡片版本，请刷新后重试')
                    expected(card['version'],payload.cardVersion)
                    if payload.balanceAction=='credit' and rule['action']!='topup':
                        raise ValueError('只有账户充值操作可以将金额计入余额')
                    if payload.balanceAction=='deduct' and rule['action']=='topup':
                        raise ValueError('账户充值请使用计入余额，或只记录费用')
                    card['balances'],before,after=apply_balance(card.get('balances',[]),cost,payload.balanceAction)
                event={'id':str(uuid4()),'cardId':card['id'],'ruleId':rule_id,'action':rule['action'],'completedAt':payload.completedAt,'oldDueDate':rule['dueDate'],'newDueDate':due,'note':payload.note,'cost':cost,'balanceAction':payload.balanceAction,'balanceBefore':before,'balanceAfter':after}
                rule.update(dueDate=due,lastCompletedAt=payload.completedAt,version=rule['version']+1)
                save_card(conn,owner,card)
                conn.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(event['id'],owner,card['id'],rule_id,payload.requestId,encode(event)))
                cancel_jobs(conn,owner,card['id'],rule_id)
        return result(owner)

    @app.post('/api/cards/{card_id}/platforms',status_code=201)
    def add_platform(card_id:str,payload:PlatformInput,person=Depends(session)):
        owner=person['id']
        with db.connect(write=True) as conn:
            card=card_for(conn,owner,card_id)
            expected(card['version'],payload.version)
            if len(card['platforms'])>=200:
                raise HTTPException(422,'每张卡片最多保存 200 条平台关联')
            if any(p['name'].casefold()==payload.name.casefold() and p['account'].casefold()==payload.account.casefold() for p in card['platforms']):
                raise HTTPException(409,'这条平台与账号关联已经存在')
            card['platforms'].append({'id':str(uuid4()),**payload.model_dump(exclude={'version'})})
            save_card(conn,owner,card)
        return result(owner)

    @app.delete('/api/cards/{card_id}/platforms/{platform_id}')
    def delete_platform(card_id:str,platform_id:str,version:int,person=Depends(session)):
        owner=person['id']
        with db.connect(write=True) as conn:
            card=card_for(conn,owner,card_id)
            expected(card['version'],version)
            if not any(p['id']==platform_id for p in card['platforms']):
                raise HTTPException(404,'找不到这条平台关联')
            card['platforms']=[p for p in card['platforms'] if p['id']!=platform_id]
            save_card(conn,owner,card)
        return result(owner)

    @app.put('/api/settings')
    def settings(payload:SettingsInput,person=Depends(session)):
        if payload.email and not payload.emailAddress:
            raise HTTPException(422,'启用邮箱提醒时须填写接收邮箱')
        owner=person['id']
        with db.connect(write=True) as conn:
            old=decode(conn.execute('SELECT settings FROM users WHERE id=?',(owner,)).fetchone()['settings'])
            updated={**old,**payload.model_dump()}
            if old['emailAddress']!=payload.emailAddress:
                updated['emailVerified']=False
                conn.execute("DELETE FROM bindings WHERE user_id=? AND kind='email'",(owner,))
            conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(updated),owner))
            conn.execute("UPDATE notification_jobs SET status='cancelled' WHERE user_id=? AND status IN ('pending','processing')",(owner,))
        return result(owner)

    notifier.install_routes(app,session,result,rate)
    static_path=Path(os.getenv('SIMKEEP_STATIC_DIR',str(ROOT/'dist')))
    if static_path.exists():
        app.mount('/',StaticFiles(directory=static_path,html=True),name='frontend')
    return app
