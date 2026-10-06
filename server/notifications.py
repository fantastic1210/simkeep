from __future__ import annotations

import asyncio
import hmac
import logging
import os
import re
import secrets
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from fastapi import Depends, HTTPException

from .auth import digest
from .db import decode, encode
from .domain import ACTIONS, parse_date
from .models import EmailCode, TelegramCode
from .money import format_money
from .notification_config import EmailConfigInput, NotificationConfigs, TelegramConfigInput

logger = logging.getLogger('simkeep.notifications')
SCHEDULE_FIELDS = ('timezone','time','offsets','overdue')


@dataclass(frozen=True)
class Config:
    public_url: str = ''
    secure_cookies: bool = False
    telegram_token: str = ''
    telegram_username: str = ''
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    smtp_mode: str = 'starttls'

    @classmethod
    def from_env(cls):
        mode = os.getenv('SIMKEEP_SMTP_MODE','starttls').lower()
        if mode not in ('starttls','ssl','plain'):
            raise ValueError('SIMKEEP_SMTP_MODE 须为 starttls、ssl 或 plain')
        return cls(
            public_url=os.getenv('SIMKEEP_PUBLIC_URL','').rstrip('/'),
            secure_cookies=os.getenv('SIMKEEP_SECURE_COOKIES','0')=='1',
            telegram_token=os.getenv('SIMKEEP_TELEGRAM_TOKEN',''),
            telegram_username=os.getenv('SIMKEEP_TELEGRAM_USERNAME','').lstrip('@'),
            smtp_host=os.getenv('SIMKEEP_SMTP_HOST',''),
            smtp_port=int(os.getenv('SIMKEEP_SMTP_PORT','465' if mode=='ssl' else '587')),
            smtp_user=os.getenv('SIMKEEP_SMTP_USER',''),
            smtp_password=os.getenv('SIMKEEP_SMTP_PASSWORD',''),
            smtp_from=os.getenv('SIMKEEP_SMTP_FROM',os.getenv('SIMKEEP_SMTP_USER','')),
            smtp_mode=mode,
        )

    def configured(self, channel):
        if channel == 'telegram':
            return bool(self.telegram_token)
        return bool(self.smtp_host and self.smtp_from and (not self.smtp_user or self.smtp_password))

    def status(self):
        # Only capability flags are public; destinations and secrets stay on the server.
        return {'telegram':{'configured':self.configured('telegram')},'email':{'configured':self.configured('email')}}


class Transport:
    def __init__(self, config):
        self.config = config
        self.username = config.telegram_username

    async def telegram(self, method, payload):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f'https://api.telegram.org/bot{self.config.telegram_token}/{method}',json=payload)
            if response.status_code != 200:
                raise RuntimeError('Telegram 暂时无法发送')
            result = response.json()
            if not result.get('ok'):
                raise RuntimeError('Telegram 暂时无法发送')
            return result['result']

    async def bot_username(self):
        if not self.username:
            self.username = (await self.telegram('getMe',{}))['username']
        if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', self.username):
            raise RuntimeError('Bot 用户名无效')
        return self.username

    async def updates(self, offset):
        return await self.telegram('getUpdates',{'offset':offset,'timeout':0,'allowed_updates':['message']})

    def smtp(self, destination=None, text=''):
        context = ssl.create_default_context()
        if self.config.smtp_mode == 'ssl':
            connection = smtplib.SMTP_SSL(self.config.smtp_host,self.config.smtp_port,timeout=20,context=context)
        else:
            connection = smtplib.SMTP(self.config.smtp_host,self.config.smtp_port,timeout=20)
        with connection:
            connection.ehlo_or_helo_if_needed()
            if self.config.smtp_mode == 'starttls':
                connection.starttls(context=context)
                connection.ehlo()
            if self.config.smtp_user:
                connection.login(self.config.smtp_user,self.config.smtp_password)
            if destination is None:
                return
            message = EmailMessage()
            message['Subject'] = '续卡 SIMKEEP · 续期提醒' if '验证码' not in text else '续卡 SIMKEEP · 验证邮箱'
            message['From'] = self.config.smtp_from
            message['To'] = destination
            message.set_content(text)
            refused = connection.send_message(message)
            if refused:
                raise RuntimeError('邮箱服务暂时无法发送')

    async def send(self, channel, destination, text):
        if channel == 'telegram':
            await self.telegram('sendMessage',{'chat_id':destination,'text':text[:4000],'disable_web_page_preview':True})
        else:
            await asyncio.to_thread(self.smtp,destination,text)


def destination(settings, channel):
    if channel == 'telegram':
        return settings.get('chatId','') if settings.get('telegramVerified') else ''
    return settings.get('emailAddress','') if settings.get('emailVerified') else ''


class Notifier:
    def __init__(self, db, config, transport=None):
        self.db = db
        self.config = config
        self.transport = transport or Transport(config)
        self.configs = NotificationConfigs(db)

    def transport_for(self, owner, config=None):
        config = config or self.configs.load(owner, self.config)
        return self.transport if config == self.config else Transport(config)

    def recover(self):
        with self.db.connect(write=True) as conn:
            conn.execute("UPDATE notification_jobs SET status='pending',error='发送中断，等待重试' WHERE status='processing'")

    def enqueue(self, now=None):
        now = now or datetime.now(timezone.utc)
        timestamp = now.timestamp()
        with self.db.connect(write=True) as conn:
            for person in conn.execute('SELECT id,settings FROM users').fetchall():
                config = self.configs.load(person['id'], self.config, conn)
                settings = decode(person['settings'])
                local = now.astimezone(ZoneInfo(settings['timezone']))
                if local.strftime('%H:%M') < settings['time']:
                    continue
                day = local.date()
                for row in conn.execute('SELECT document FROM cards WHERE user_id=?',(person['id'],)).fetchall():
                    card = decode(row['document'])
                    if card['archived']:
                        continue
                    for rule in card['rules']:
                        remaining = (parse_date(rule['dueDate'])-day).days
                        if remaining not in [0,*settings['offsets']] and not (remaining < 0 and settings['overdue']):
                            continue
                        payload = {'dueDate':rule['dueDate'],'day':day.isoformat(),'remaining':remaining,'schedule':{k:settings[k] for k in SCHEDULE_FIELDS}}
                        for channel in ('telegram','email'):
                            target = destination(settings,channel)
                            if not settings[channel] or not target or not config.configured(channel):
                                continue
                            key = ':'.join((person['id'],card['id'],rule['id'],str(rule['version']),channel,day.isoformat()))
                            values = (str(uuid4()),key,person['id'],card['id'],rule['id'],rule['version'],channel,target,encode(payload),timestamp,timestamp)
                            conn.execute('INSERT OR IGNORE INTO notification_jobs(id,dedupe_key,user_id,card_id,rule_id,rule_version,channel,destination,payload,ready_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',values)
                            # Restore only unsent, cancelled jobs. Sent keys remain final even after settings change.
                            conn.execute("UPDATE notification_jobs SET status='pending',attempts=0,error=NULL,destination=?,payload=?,ready_at=? WHERE dedupe_key=? AND status='cancelled' AND sent_at IS NULL",(target,encode(payload),timestamp,key))

    def valid(self, conn, job, now):
        person = conn.execute('SELECT settings FROM users WHERE id=?',(job['user_id'],)).fetchone()
        row = conn.execute('SELECT document FROM cards WHERE id=? AND user_id=?',(job['card_id'],job['user_id'])).fetchone()
        if not person or not row:
            return None
        settings, card, payload = decode(person[0]), decode(row[0]), decode(job['payload'])
        rule = next((r for r in card['rules'] if r['id']==job['rule_id']),None)
        if card['archived'] or not rule or rule['version']!=job['rule_version'] or rule['dueDate']!=payload['dueDate']:
            return None
        if not settings[job['channel']] or destination(settings,job['channel'])!=job['destination']:
            return None
        if {k:settings[k] for k in SCHEDULE_FIELDS}!=payload['schedule']:
            return None
        if now.astimezone(ZoneInfo(settings['timezone'])).date().isoformat()!=payload['day']:
            return None
        return card, rule, payload

    def message(self, card, rule, payload):
        remaining = payload['remaining']
        timing = f'还有 {remaining} 天' if remaining > 0 else '今天到期' if remaining == 0 else f'已逾期 {-remaining} 天'
        action = ACTIONS[rule['action']]
        phone = f"号码尾号 {re.sub(r'\s','',card['phone'])[-4:]}" if card['phone'].startswith('+') else '数据卡 / 未填写号码'
        cost = rule.get('cost')
        balance = next((item for item in card.get('balances',[]) if cost and item['currency']==cost['currency']),None)
        money = f"续期金额：{format_money(cost)}\n"
        if balance is not None:
            money += f"同币种余额：{format_money(balance)}\n"
        return f"续卡 SIMKEEP · 续期提醒\n\n{card['name']} · {card['provider']}\n{phone}\n{action} · {timing}\n到期日期：{rule['dueDate']}\n{money}操作说明：{rule['instructions'] or '请按运营商的要求完成续期'}\n\n完成操作后，请在续卡记录完成，更新下次续期日期。\n{self.config.public_url}/#renewals"

    async def deliver(self, now=None):
        now = now or datetime.now(timezone.utc)
        timestamp = now.timestamp()
        with self.db.connect(write=True) as conn:
            # Expire stale dates even when their channel is currently unavailable.
            for person in conn.execute('SELECT id,settings FROM users').fetchall():
                local_day = now.astimezone(ZoneInfo(decode(person['settings'])['timezone'])).date().isoformat()
                conn.execute("UPDATE notification_jobs SET status='cancelled' WHERE user_id=? AND status='pending' AND json_extract(payload,'$.day')<>?",(person['id'],local_day))
            configurations = {}
            pending = []
            # Apply availability before the batch limit, including per-account services.
            for row in conn.execute("SELECT * FROM notification_jobs WHERE status='pending' AND ready_at<=? ORDER BY ready_at", (timestamp,)):
                owner = row['user_id']
                if owner not in configurations:
                    configurations[owner] = self.configs.load(owner, self.config, conn)
                if configurations[owner].configured(row['channel']):
                    pending.append(dict(row))
                    if len(pending) == 50:
                        break
        for job in pending:
            with self.db.connect(write=True) as conn:
                config = self.configs.load(job['user_id'], self.config, conn)
                if not config.configured(job['channel']):
                    continue
                current = conn.execute("SELECT * FROM notification_jobs WHERE id=? AND status='pending'",(job['id'],)).fetchone()
                if not current:
                    continue
                valid = self.valid(conn,current,now)
                if not valid:
                    conn.execute("UPDATE notification_jobs SET status='cancelled' WHERE id=?",(job['id'],))
                    continue
                attempts = current['attempts']+1
                conn.execute("UPDATE notification_jobs SET status='processing',attempts=? WHERE id=?",(attempts,job['id']))
            try:
                await self.transport_for(job['user_id'],config).send(job['channel'],job['destination'],self.message(*valid))
            except Exception:
                # Raw transport exceptions can contain credentials. Persist only a safe, actionable message.
                error = '发送失败，请检查服务配置或接收地址' if attempts>=5 else '发送失败，稍后自动重试'
                with self.db.connect(write=True) as conn:
                    conn.execute("UPDATE notification_jobs SET status=?,error=?,ready_at=? WHERE id=? AND status='processing'",('failed' if attempts>=5 else 'pending',error,timestamp+60*2**(attempts-1),job['id']))
            else:
                with self.db.connect(write=True) as conn:
                    # An edit during the network call cannot recall an accepted message; record the actual outcome.
                    conn.execute("UPDATE notification_jobs SET status='sent',sent_at=?,error=NULL WHERE id=?",(timestamp,job['id']))

    def process_update(self, update, user_id=None, token=None):
        message = update.get('message',{})
        chat = message.get('chat',{})
        match = re.fullmatch(r'/start(?:@[A-Za-z0-9_]+)?\s+([A-Za-z0-9_-]+)',message.get('text','').strip())
        if chat.get('type')!='private' or not isinstance(chat.get('id'),int) or not match:
            return False
        chat_id = str(chat['id'])
        with self.db.connect(write=True) as conn:
            binding = conn.execute("SELECT * FROM bindings WHERE token_hash=? AND kind='telegram' AND destination IS NULL AND expires_at>?",(digest(match[1]),time.time())).fetchone()
            if not binding:
                return False
            expected = token if token is not None else self.configs.load(user_id, self.config, conn).telegram_token if user_id else self.config.telegram_token
            current = self.configs.load(binding['user_id'], self.config, conn)
            if (user_id is not None and binding['user_id'] != user_id) or current.telegram_token != expected:
                return False
            for row in conn.execute('SELECT id,settings FROM users'):
                existing = decode(row['settings'])
                same_bot = self.configs.load(row['id'],self.config,conn).telegram_token == current.telegram_token
                if same_bot and row['id']!=binding['user_id'] and existing.get('telegramVerified') and existing.get('chatId')==chat_id:
                    return False
            row = conn.execute('SELECT settings FROM users WHERE id=?',(binding['user_id'],)).fetchone()
            settings = decode(row[0])
            settings.update(chatId=chat_id,telegramVerified=True)
            conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(settings),binding['user_id']))
            conn.execute('UPDATE bindings SET destination=? WHERE token_hash=?',(chat_id,binding['token_hash']))
            conn.execute("UPDATE notification_jobs SET status='cancelled' WHERE user_id=? AND channel='telegram' AND status IN ('pending','processing')",(binding['user_id'],))
            return True

    async def poll(self):
        with self.db.connect() as conn:
            people = [row['id'] for row in conn.execute('SELECT id FROM users')]
            personal = [(owner,self.configs.load(owner,self.config,conn)) for owner in people]
        targets = [(owner,config) for owner,config in personal if config.telegram_token and config.telegram_token != self.config.telegram_token]
        if self.config.configured('telegram'):
            targets.append((None,self.config))
        semaphore = asyncio.Semaphore(4)

        async def guarded(owner, config):
            async with semaphore:
                try:
                    await self.poll_bot(owner, config)
                except Exception:
                    logger.warning('Telegram 绑定暂时不可用，请检查本账号的 Bot 配置与网络')
        await asyncio.gather(*(guarded(owner,config) for owner,config in targets))

    async def poll_bot(self, owner, config):
        key = f'telegram_offset:{owner}:{digest(config.telegram_token)}' if owner else 'telegram_offset'
        with self.db.connect() as conn:
            row = conn.execute('SELECT value FROM system_state WHERE key=?', (key,)).fetchone()
        offset = int(row[0]) if row else 0
        updates = await self.transport_for(owner,config).updates(offset)
        for update in updates:
            self.process_update(update,user_id=owner,token=config.telegram_token)
            with self.db.connect(write=True) as conn:
                conn.execute('INSERT OR REPLACE INTO system_state VALUES(?,?)',(key,str(update['update_id']+1)))

    async def run(self):
        self.recover()
        while True:
            try:
                await self.poll()
            except Exception:
                logger.warning('Telegram 绑定暂时不可用，请检查 Bot 配置与网络')
            try:
                self.enqueue()
                await self.deliver()
                with self.db.connect(write=True) as conn:
                    conn.execute('DELETE FROM bindings WHERE expires_at<?',(time.time(),))
            except Exception:
                logger.warning('续期调度暂时失败，将在下一轮重试')
            await asyncio.sleep(5)

    def install_routes(self, app, session, result, rate):
        def require_config(channel, owner):
            config = self.configs.load(owner,self.config)
            if not config.configured(channel):
                raise HTTPException(503,'请先配置本账号的 Telegram Bot' if channel=='telegram' else '请先配置本账号的邮件服务')
            return self.transport_for(owner,config)

        @app.get('/api/notifications/config')
        def read_config(person=Depends(session)):
            return {'services':self.configs.status(person['id'],self.config)}

        @app.put('/api/notifications/config/telegram')
        def save_telegram_config(payload:TelegramConfigInput,person=Depends(session)):
            self.configs.save(person['id'],'telegram',payload,self.config)
            return result(person['id'])

        @app.put('/api/notifications/config/email')
        def save_email_config(payload:EmailConfigInput,person=Depends(session)):
            self.configs.save(person['id'],'email',payload,self.config)
            return result(person['id'])

        @app.delete('/api/notifications/config/{channel}')
        def clear_config(channel:Literal['email','telegram'],person=Depends(session)):
            self.configs.clear(person['id'],channel,self.config)
            return result(person['id'])

        @app.post('/api/notifications/config/{channel}/check')
        async def check_config(channel:Literal['email','telegram'],person=Depends(session)):
            transport = require_config(channel,person['id'])
            rate.check(('config_check',channel,person['id']),5,600)
            try:
                if channel == 'telegram':
                    username = await transport.bot_username()
                    return {'checked':True,'botUsername':username}
                await asyncio.to_thread(transport.smtp)
            except Exception:
                message = '无法连接 Telegram Bot，请检查 Token 和服务器网络' if channel=='telegram' else 'SMTP 连接或认证失败，请检查服务器、端口、安全方式及密码 / 授权码'
                raise HTTPException(503,message) from None
            return {'checked':True}

        @app.post('/api/notifications/telegram/binding')
        async def telegram_binding(person=Depends(session)):
            transport = require_config('telegram',person['id'])
            token = getattr(transport,'config',self.config).telegram_token
            rate.check(('telegram_binding',person['id']),3,60)
            try:
                username = await transport.bot_username()
            except Exception:
                raise HTTPException(503,'无法连接 Telegram Bot，请检查本账号的配置') from None
            code = secrets.token_urlsafe(24)
            with self.db.connect(write=True) as conn:
                if self.configs.load(person['id'],self.config,conn).telegram_token != token:
                    raise HTTPException(409,'Bot 配置已更改，请重新开始绑定')
                conn.execute("DELETE FROM bindings WHERE user_id=? AND kind='telegram'",(person['id'],))
                conn.execute('INSERT INTO bindings(token_hash,user_id,kind,expires_at,created_at) VALUES(?,?,?,?,?)',(digest(code),person['id'],'telegram',time.time()+600,time.time()))
            return {'code':code,'url':f'https://t.me/{username}?start={code}','expiresIn':600}

        @app.post('/api/notifications/telegram/binding/check')
        def check_telegram_binding(payload:TelegramCode,person=Depends(session)):
            with self.db.connect() as conn:
                binding = conn.execute("SELECT destination FROM bindings WHERE token_hash=? AND user_id=? AND kind='telegram' AND expires_at>?",(digest(payload.code),person['id'],time.time())).fetchone()
            status = 'expired' if not binding else 'bound' if binding['destination'] else 'waiting'
            return result(person['id'],bindingStatus=status)

        @app.delete('/api/notifications/telegram/binding')
        def unbind_telegram(person=Depends(session)):
            with self.db.connect(write=True) as conn:
                settings = decode(conn.execute('SELECT settings FROM users WHERE id=?',(person['id'],)).fetchone()[0])
                settings.update(chatId='',telegramVerified=False,telegram=False)
                conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(settings),person['id']))
                conn.execute("DELETE FROM bindings WHERE user_id=? AND kind='telegram'",(person['id'],))
                conn.execute("UPDATE notification_jobs SET status='cancelled' WHERE user_id=? AND channel='telegram' AND status IN ('pending','processing')",(person['id'],))
            return result(person['id'])

        @app.post('/api/notifications/email/verify')
        async def verify_email(person=Depends(session)):
            transport = require_config('email',person['id'])
            rate.check(('email_verify',person['id']),3,600)
            code = f'{secrets.randbelow(1000000):06d}'
            nonce = secrets.token_urlsafe(24)
            token_hash = digest(nonce+code)
            with self.db.connect(write=True) as conn:
                settings = decode(conn.execute('SELECT settings FROM users WHERE id=?',(person['id'],)).fetchone()[0])
                address = settings['emailAddress']
                if not address:
                    raise HTTPException(422,'请先保存接收邮箱')
                conn.execute("DELETE FROM bindings WHERE user_id=? AND kind='email'",(person['id'],))
                conn.execute('INSERT INTO bindings(token_hash,user_id,kind,destination,expires_at,created_at) VALUES(?,?,?,?,?,?)',(token_hash,person['id'],'email',encode({'address':address,'nonce':nonce}),time.time()+600,time.time()))
            try:
                await transport.send('email',address,f'续卡 SIMKEEP · 验证邮箱\n\n验证码：{code}\n10 分钟内有效。请在通知设置输入验证码，确认这是你的接收邮箱。')
            except Exception:
                with self.db.connect(write=True) as conn:
                    conn.execute('DELETE FROM bindings WHERE token_hash=?',(token_hash,))
                raise HTTPException(503,'验证码发送失败，请检查邮件服务配置') from None
            return {'sent':True,'expiresIn':600}

        @app.post('/api/notifications/email/confirm')
        def confirm_email(payload:EmailCode,person=Depends(session)):
            rate.check(('email_confirm',person['id']),20,600)
            valid = False
            with self.db.connect(write=True) as conn:
                binding = conn.execute("SELECT * FROM bindings WHERE user_id=? AND kind='email' ORDER BY created_at DESC LIMIT 1",(person['id'],)).fetchone()
                settings = decode(conn.execute('SELECT settings FROM users WHERE id=?',(person['id'],)).fetchone()[0])
                if binding and binding['expires_at']>time.time() and binding['attempts']<5:
                    stored = decode(binding['destination'])
                    valid = stored['address']==settings['emailAddress'] and hmac.compare_digest(binding['token_hash'],digest(stored['nonce']+payload.code))
                    if valid:
                        settings['emailVerified'] = True
                        conn.execute('UPDATE users SET settings=? WHERE id=?',(encode(settings),person['id']))
                        conn.execute('DELETE FROM bindings WHERE token_hash=?',(binding['token_hash'],))
                    else:
                        conn.execute('UPDATE bindings SET attempts=attempts+1 WHERE token_hash=?',(binding['token_hash'],))
            if not valid:
                raise HTTPException(422,'验证码不正确或已失效，请重新发送')
            return result(person['id'])

        @app.post('/api/notifications/test/{channel}')
        async def test_notification(channel:Literal['email','telegram'],person=Depends(session)):
            transport = require_config(channel,person['id'])
            rate.check(('notification_test',person['id']),5,600)
            with self.db.connect() as conn:
                settings = decode(conn.execute('SELECT settings FROM users WHERE id=?',(person['id'],)).fetchone()[0])
            target = destination(settings,channel)
            if not target:
                raise HTTPException(422,'请先验证邮箱或绑定 Telegram')
            try:
                await transport.send(channel,target,'续卡 SIMKEEP · 测试提醒\n\n通知渠道已连接。开启提醒并保存设置后，续期提醒将按你选择的时间发送。')
            except Exception:
                raise HTTPException(503,'测试提醒发送失败，请检查服务配置或接收地址') from None
            return {'sent':True}
