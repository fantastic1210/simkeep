from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,password_hash TEXT NOT NULL,settings TEXT NOT NULL,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,csrf TEXT NOT NULL,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS cards(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,document TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS cards_user ON cards(user_id);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,card_id TEXT NOT NULL REFERENCES cards(id),rule_id TEXT NOT NULL,request_id TEXT NOT NULL,document TEXT NOT NULL,UNIQUE(user_id,request_id));
CREATE INDEX IF NOT EXISTS events_user ON events(user_id);
CREATE TABLE IF NOT EXISTS bindings(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL,destination TEXT,expires_at REAL NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS notification_jobs(id TEXT PRIMARY KEY,dedupe_key TEXT NOT NULL UNIQUE,user_id TEXT NOT NULL REFERENCES users(id),card_id TEXT NOT NULL REFERENCES cards(id),rule_id TEXT NOT NULL,rule_version INTEGER NOT NULL,channel TEXT NOT NULL,destination TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,ready_at REAL NOT NULL,created_at REAL NOT NULL,sent_at REAL,error TEXT);
CREATE INDEX IF NOT EXISTS notification_ready ON notification_jobs(status,ready_at);
CREATE TABLE IF NOT EXISTS system_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notification_configs(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,channel TEXT NOT NULL CHECK(channel IN ('telegram','email')),document TEXT NOT NULL,telegram_identity TEXT UNIQUE,PRIMARY KEY(user_id,channel));
'''


class Database:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self,write=False):
        conn=sqlite3.connect(str(self.path),timeout=15)
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=15000')
        try:
            if write:
                conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


def encode(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'))


def decode(value):
    return json.loads(value)
