from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ACTIONS = {'sms':'发送短信','call':'拨打电话','purchase':'购买套餐','reset':'重置有效期','topup':'账户充值','custom':'自定义操作'}


def parse_date(value: str) -> date:
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('请输入有效日期')
    try:
        result = date.fromisoformat(value)
        if result.year < 1900:
            raise ValueError()
        return result
    except ValueError:
        raise ValueError('请输入有效日期') from None


def add_cycle(value: str, interval: int, unit: str) -> str:
    start = parse_date(value)
    if type(interval) is not int or interval < 1:
        raise ValueError('周期必须为正整数')
    try:
        if unit == 'days':
            return (start + timedelta(days=interval)).isoformat()
        if unit != 'months':
            raise ValueError('请选择有效周期单位')
        year, month = divmod(start.year * 12 + start.month - 1 + interval,12)
        month += 1
        return date(year,month,min(start.day,calendar.monthrange(year,month)[1])).isoformat()
    except (OverflowError,ValueError):
        raise ValueError('周期或日期超出允许范围') from None


def next_due(rule: dict, completed: str) -> str:
    parse_date(completed)
    if rule['anchor'] != 'scheduled':
        return add_cycle(completed,rule['interval'],rule['unit'])
    origin = rule.get('anchorDate') or rule['dueDate']
    after = max(completed,rule['dueDate'])
    for cycle in range(1,50000):
        candidate = add_cycle(origin,rule['interval']*cycle,rule['unit'])
        if candidate > after:
            return candidate
    raise ValueError('周期跨度过大，请调整规则')


def business_today(zone: str, now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone)).date().isoformat()


def check_activation(card: dict | None, events: list[dict], activated: str, today: str):
    parse_date(activated)
    if activated > today:
        raise ValueError('开通日期不能是未来日期')
    if not card:
        return
    if any(r['dueDate'] < activated or (r.get('lastCompletedAt') and r['lastCompletedAt'] < activated) for r in card['rules']):
        raise ValueError('开通日期不能晚于已有的续期记录或计划日期')
    if any(ev['cardId'] == card['id'] and ev['completedAt'] < activated for ev in events):
        raise ValueError('开通日期不能晚于已有的续期记录或计划日期')


def check_completion(card: dict, rule: dict, completed: str, today: str):
    parse_date(completed)
    if card['archived']:
        raise ValueError('请先恢复卡片，再记录续期')
    if completed > today:
        raise ValueError('不能记录未来的完成日期')
    if completed < card['activatedAt']:
        raise ValueError('完成日期不能早于开通日期')
    if rule.get('lastCompletedAt') and completed <= rule['lastCompletedAt']:
        raise ValueError('完成日期须晚于上次完成日期，这一天可能已经记录过')
