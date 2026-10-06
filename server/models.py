import re
from typing import Literal
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from pydantic import BaseModel,ConfigDict,Field,StrictInt,field_validator,model_validator
from .domain import parse_date
from .money import CURRENCIES,normalize_amount


class Model(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


class Money(Model):
    currency:str=Field(min_length=3,max_length=3)
    amount:str=Field(min_length=1,max_length=30)

    @model_validator(mode='after')
    def valid_money(self):
        self.currency=self.currency.upper()
        self.amount=normalize_amount(self.amount,self.currency)
        return self


class Login(Model):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=False)
    email:str=Field(min_length=3,max_length=120)
    password:str=Field(min_length=1,max_length=128)

    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        value=value.strip()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
            raise ValueError('请输入有效邮箱')
        return value.lower()

class Register(Login):
    name:str=Field(min_length=1,max_length=45)
    password:str=Field(min_length=10,max_length=128)

    @field_validator('name')
    @classmethod
    def valid_name(cls,value):
        value=value.strip()
        if not value:
            raise ValueError('请填写名字')
        return value


class RuleInput(Model):
    action:Literal['sms','call','purchase','reset','topup','custom']
    interval:StrictInt=Field(ge=1,le=3650)
    unit:Literal['days','months']
    anchor:Literal['completion','scheduled']
    dueDate:str
    instructions:str=Field(default='',max_length=1000)
    version:StrictInt|None=Field(default=None,ge=1)
    cost:Money|None=None

    @field_validator('dueDate')
    @classmethod
    def valid_date(cls,value):
        parse_date(value)
        return value


class CardInput(Model):
    name:str=Field(min_length=1,max_length=45)
    provider:str=Field(min_length=1,max_length=45)
    type:Literal['SIM','eSIM']
    country:Literal['GB','US','HK','JP','CN','DE','SG','OTHER']
    phone:str=Field(default='',max_length=35)
    activatedAt:str
    notes:str=Field(default='',max_length=1000)
    plan:str=Field(default='',max_length=60)
    rules:list[RuleInput]=Field(default_factory=list,max_length=20)
    version:StrictInt|None=Field(default=None,ge=1)
    balances:list[Money]|None=Field(default=None,max_length=len(CURRENCIES))

    @field_validator('balances')
    @classmethod
    def unique_currencies(cls,value):
        if value is not None and len({item.currency for item in value})!=len(value):
            raise ValueError('同一张卡的每个币种只能记录一条余额')
        return value

    @field_validator('activatedAt')
    @classmethod
    def valid_date(cls,value):
        parse_date(value)
        return value


class ArchiveInput(Model):
    archived:bool
    version:StrictInt=Field(ge=1)


class Completion(Model):
    completedAt:str
    note:str=Field(default='',max_length=1000)
    requestId:str=Field(min_length=8,max_length=100)
    version:StrictInt=Field(ge=1)
    cost:Money|None=None
    balanceAction:Literal['none','deduct','credit']='none'
    cardVersion:StrictInt|None=Field(default=None,ge=1)


class PlatformInput(Model):
    name:str=Field(min_length=1,max_length=45)
    account:str=Field(default='',max_length=120)
    purpose:str=Field(default='',max_length=80)
    version:StrictInt=Field(ge=1)


class SettingsInput(Model):
    timezone:str
    time:str
    offsets:list[StrictInt]=Field(max_length=12)
    overdue:bool
    telegram:bool
    email:bool
    emailAddress:str=Field(default='',max_length=120)

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls,value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError):
            raise ValueError('请选择有效时区') from None
        return value

    @field_validator('time')
    @classmethod
    def valid_time(cls,value):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value):
            raise ValueError('请输入有效提醒时间')
        return value

    @field_validator('offsets')
    @classmethod
    def valid_offsets(cls,value):
        if any(v < 1 or v > 365 for v in value):
            raise ValueError('提前提醒天数须为 1–365')
        return sorted(set(value),reverse=True)

    @field_validator('emailAddress')
    @classmethod
    def valid_email(cls,value):
        if value:
            return Login.email_format(value)
        return value


class EmailCode(Model):
    code:str=Field(min_length=6,max_length=6)


class TelegramCode(Model):
    code:str=Field(min_length=20,max_length=100)
