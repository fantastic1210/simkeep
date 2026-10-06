import hashlib
import hmac
import secrets
import threading
import time
from fastapi import HTTPException


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password):
    salt=secrets.token_bytes(16)
    key=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return f'scrypt${salt.hex()}${key.hex()}'


def verify_password(password,encoded):
    try:
        algorithm,salt,key=encoded.split('$')
        if algorithm != 'scrypt':
            return False
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32)
        return hmac.compare_digest(actual,bytes.fromhex(key))
    except (ValueError,TypeError):
        return False


DUMMY_HASH=hash_password('never-a-real-account-password')


class RateLimit:
    def __init__(self):
        self.entries={}
        self.lock=threading.Lock()

    def check(self,key,limit=20,window=60):
        now=time.monotonic()
        with self.lock:
            self.entries={k:v for k,v in self.entries.items() if now < v[0]}
            expiry,count=self.entries.get(key,(now+window,0))
            if count >= limit:
                raise HTTPException(429,'操作过于频繁，请稍后重试')
            self.entries[key]=(expiry,count+1)
