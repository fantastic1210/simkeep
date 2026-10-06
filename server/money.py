"""Exact, nonnegative amounts in their original currency. No FX conversion."""
import re
from decimal import Decimal, InvalidOperation

CURRENCIES={
    'CNY':2,'USD':2,'HKD':2,'GBP':2,'EUR':2,'JPY':0,'TWD':2,'SGD':2,
    'AUD':2,'CAD':2,'CHF':2,'NZD':2,'KRW':0,'THB':2,'MYR':2,'AED':2,
    'SAR':2,'IDR':2,'INR':2,'PHP':2,'VND':0,'KWD':3,'BHD':3,
}
MAX_AMOUNT=Decimal('999999999')


def normalize_amount(value,currency):
    if currency not in CURRENCIES:
        raise ValueError('请选择支持的币种')
    if not isinstance(value,str) or len(value)>30 or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',value):
        raise ValueError('金额须为不小于 0 的数字')
    try:
        amount=Decimal(value)
        if amount>MAX_AMOUNT:
            raise ValueError('金额不能超过 999999999')
        places=CURRENCIES[currency]
        normalized=amount.quantize(Decimal(1).scaleb(-places))
        if normalized!=amount:
            raise ValueError(f'{currency} 金额最多保留 {places} 位小数')
        return format(normalized,f'.{places}f')
    except InvalidOperation:
        raise ValueError('请输入有效金额') from None


def format_money(money):
    if money is None:
        return '未填写'
    amount=normalize_amount(money['amount'],money['currency'])
    return f"{money['currency']} {Decimal(amount):,f}"


def apply_balance(balances,cost,operation):
    if operation not in ('deduct','credit') or not cost:
        raise ValueError('更新余额时须填写本次金额和币种')
    currency=cost['currency']
    amount=Decimal(normalize_amount(cost['amount'],currency))
    current=next((item for item in balances if item['currency']==currency),None)
    if operation=='deduct' and current is None:
        raise ValueError(f'尚未记录 {currency} 余额，请先在卡片资料中添加')
    before={'currency':currency,'amount':normalize_amount(current['amount'] if current else '0',currency)}
    remaining=Decimal(before['amount'])-amount if operation=='deduct' else Decimal(before['amount'])+amount
    if remaining<0:
        raise ValueError(f'{currency} 余额不足，可取消更新余额后单独记录费用')
    after={'currency':currency,'amount':normalize_amount(format(remaining,'f'),currency)}
    updated=[dict(item) for item in balances if item['currency']!=currency]
    if current:
        updated=[dict(after) if item['currency']==currency else dict(item) for item in balances]
    else:
        updated.append(dict(after))
    return updated,before,after
