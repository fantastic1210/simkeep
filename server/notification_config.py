"""Owned notification credentials. Only status and non-secret fields leave this module."""
import re
import sqlite3
from dataclasses import replace

from fastapi import HTTPException
from pydantic import ConfigDict, Field, StrictInt, field_validator
from typing import Literal

from .auth import digest
from .db import decode, encode
from .models import Login, Model


class TelegramConfigInput(Model):
    token: str = Field(default='', max_length=160)

    @field_validator('token')
    @classmethod
    def token_format(cls, value):
        if value and not re.fullmatch(r'[0-9]{1,20}:[A-Za-z0-9_-]{20,120}', value):
            raise ValueError('Bot Token 格式无效，请复制 BotFather 提供的完整 Token')
        if not value:
            return value
        bot_id, secret = value.split(':', 1)
        if int(bot_id) == 0:
            raise ValueError('Bot Token 格式无效，请复制 BotFather 提供的完整 Token')
        return f'{int(bot_id)}:{secret}'


class EmailConfigInput(Model):
    # SMTP passwords may intentionally start or end with spaces.
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    host: str = Field(min_length=1, max_length=253)
    port: StrictInt = Field(ge=1, le=65535)
    mode: Literal['starttls', 'ssl', 'plain']
    user: str = Field(default='', max_length=254)
    password: str = Field(default='', max_length=1024)
    sender: str = Field(alias='from', min_length=3, max_length=120)

    @field_validator('host')
    @classmethod
    def host_format(cls, value):
        value = value.strip()
        if not re.fullmatch(r'[A-Za-z0-9_.:\[\]-]+', value):
            raise ValueError('SMTP 服务器填写主机名或 IP，不包含网址、路径或端口')
        return value

    @field_validator('user')
    @classmethod
    def user_format(cls, value):
        value = value.strip()
        if '\r' in value or '\n' in value:
            raise ValueError('SMTP 用户名不能包含换行')
        return value

    @field_validator('sender')
    @classmethod
    def sender_format(cls, value):
        return Login.email_format(value)


class NotificationConfigs:
    def __init__(self, db):
        self.db = db

    def read(self, conn, owner):
        return {row['channel']: decode(row['document']) for row in conn.execute('SELECT channel,document FROM notification_configs WHERE user_id=?', (owner,))}

    def load(self, owner, defaults, conn=None):
        if conn is None:
            with self.db.connect() as connection:
                return self.load(owner, defaults, connection)
        personal = self.read(conn, owner)
        fields = {}
        if 'telegram' in personal:
            fields.update(telegram_token=personal['telegram']['token'], telegram_username='')
        if 'email' in personal:
            fields.update({f'smtp_{key}': value for key, value in personal['email'].items()})
        return replace(defaults, **fields)

    def status(self, owner, defaults):
        with self.db.connect() as conn:
            personal = self.read(conn, owner)
            config = self.load(owner, defaults, conn)
        result = config.status()
        for channel in ('telegram', 'email'):
            result[channel]['source'] = 'account' if channel in personal else 'server' if config.configured(channel) else 'none'
        result['telegram']['tokenSaved'] = bool(personal.get('telegram', {}).get('token'))
        email = personal.get('email', {})
        result['email'].update({key: email.get(key, default) for key, default in [('host',''),('port',587),('mode','starttls'),('user',''),('from','')]})
        result['email']['passwordSaved'] = bool(email.get('password'))
        return result

    def invalidate(self, conn, owner, channel, bot_changed=False):
        conn.execute("UPDATE notification_jobs SET status='cancelled' WHERE user_id=? AND channel=? AND status IN ('pending','processing','failed') AND sent_at IS NULL", (owner, channel))
        if bot_changed:
            settings = decode(conn.execute('SELECT settings FROM users WHERE id=?', (owner,)).fetchone()[0])
            settings.update(chatId='', telegramVerified=False, telegram=False)
            conn.execute('UPDATE users SET settings=? WHERE id=?', (encode(settings), owner))
            conn.execute("DELETE FROM bindings WHERE user_id=? AND kind='telegram'", (owner,))

    def save(self, owner, channel, payload, defaults):
        try:
            with self.db.connect(write=True) as conn:
                personal = self.read(conn, owner)
                old = personal.get(channel, {})
                before = self.load(owner, defaults, conn)
                document = payload.model_dump(by_alias=True)
                identity = None
                if channel == 'telegram':
                    document['token'] = document['token'] or old.get('token', '')
                    if not document['token']:
                        raise HTTPException(422, '请先填写 Bot Token')
                    # A guessed Bot ID with a fake secret must not reserve a real Bot.
                    identity = digest(document['token'])
                    if defaults.telegram_token and document['token'] == defaults.telegram_token:
                        raise HTTPException(409, '这个 Bot 已用于公共服务，请为本账号使用独立的 Bot')
                else:
                    document['password'] = (document['password'] or old.get('password', '')) if document['user'] else ''
                    if document['user'] and not document['password']:
                        raise HTTPException(422, '填写 SMTP 用户名后，请填写密码或授权码')
                if document == old:
                    return
                conn.execute('INSERT INTO notification_configs(user_id,channel,document,telegram_identity) VALUES(?,?,?,?) ON CONFLICT(user_id,channel) DO UPDATE SET document=excluded.document,telegram_identity=excluded.telegram_identity', (owner, channel, encode(document), identity))
                self.invalidate(conn, owner, channel, channel == 'telegram' and before.telegram_token != document['token'])
        except sqlite3.IntegrityError:
            raise HTTPException(409, '这个 Bot 已由其他账号使用，请使用自己的 Bot') from None

    def clear(self, owner, channel, defaults):
        with self.db.connect(write=True) as conn:
            before = self.load(owner, defaults, conn)
            conn.execute('DELETE FROM notification_configs WHERE user_id=? AND channel=?', (owner, channel))
            after = self.load(owner, defaults, conn)
            self.invalidate(conn, owner, channel, channel == 'telegram' and before.telegram_token != after.telegram_token)
