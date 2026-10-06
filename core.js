const DAY = 86_400_000;

export function createId(cryptoSource = globalThis.crypto) {
  if (typeof cryptoSource?.randomUUID === 'function') return cryptoSource.randomUUID();
  const bytes = cryptoSource.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2,'0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

export function parseDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) throw new Error('请输入有效日期');
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(0, 0, 0, 0);
  if (year < 1900 || year > 9999 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new Error('请输入有效日期');
  return date;
}

const isoDate = date => date.toISOString().slice(0, 10);

export function todayString(timeZone = 'Asia/Shanghai', now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {timeZone, year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(now);
  const get = type => parts.find(part => part.type === type).value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}

export function addDays(value, count) {
  if (!Number.isInteger(count)) throw new Error('周期必须为整数');
  const date = parseDate(value);
  date.setUTCDate(date.getUTCDate() + count);
  const result = isoDate(date);
  parseDate(result);
  return result;
}

export function addCycle(value, interval, unit) {
  if (!Number.isInteger(interval) || interval < 1) throw new Error('周期必须为正整数');
  if (unit === 'days') return addDays(value, interval);
  if (unit !== 'months') throw new Error('请选择有效周期单位');
  const date = parseDate(value);
  const day = date.getUTCDate();
  date.setUTCDate(1);
  date.setUTCMonth(date.getUTCMonth() + interval);
  const end = new Date(date);
  end.setUTCMonth(end.getUTCMonth() + 1, 0);
  date.setUTCDate(Math.min(day, end.getUTCDate()));
  const result = isoDate(date);
  parseDate(result);
  return result;
}

export function daysUntil(value, today = todayString()) {
  return Math.round((parseDate(value) - parseDate(today)) / DAY);
}

export function nextAfterCompletion(rule, completedAt) {
  parseDate(completedAt);
  parseDate(rule.dueDate);
  if (rule.anchor !== 'scheduled') return addCycle(completedAt, rule.interval, rule.unit);
  const origin = rule.anchorDate || rule.dueDate;
  const after = completedAt > rule.dueDate ? completedAt : rule.dueDate;
  // Calculate every occurrence from the original anchor, preserving month-end intent.
  for (let cycle = 1; cycle < 50_000; cycle++) {
    const candidate = addCycle(origin, rule.interval * cycle, rule.unit);
    if (candidate > after) return candidate;
  }
  throw new Error('周期跨度过大，请调整规则');
}

export function completeRenewal(card, ruleId, completedAt, today, note = '') {
  parseDate(completedAt);
  parseDate(today);
  const rule = card.rules.find(item => item.id === ruleId);
  if (!rule) throw new Error('找不到这条续期规则');
  if (card.archived) throw new Error('请先恢复这张卡片，再记录续期');
  if (completedAt > today) throw new Error('不能记录未来的完成日期');
  if (completedAt < card.activatedAt) throw new Error('完成日期不能早于开通日期');
  if (rule.lastCompletedAt && completedAt < rule.lastCompletedAt) throw new Error('完成日期不能早于上次完成日期');
  if (rule.lastCompletedAt === completedAt) throw new Error('这一天已经记录过该操作');
  const nextDueDate = nextAfterCompletion(rule, completedAt);
  const updated = {...card, rules:card.rules.map(item => item.id === ruleId ? {...item, dueDate:nextDueDate, lastCompletedAt:completedAt} : {...item})};
  const event = {
    id:createId(),
    cardId:card.id, ruleId, action:rule.action, completedAt,
    oldDueDate:rule.dueDate, newDueDate:nextDueDate, note,
  };
  return {card:updated, event};
}

export function getTasks(cards) {
  return cards.filter(card => !card.archived)
    .flatMap(card => card.rules.map(rule => ({card, rule})))
    .sort((a, b) => a.rule.dueDate.localeCompare(b.rule.dueDate) || a.card.name.localeCompare(b.card.name));
}

export function validateActivationChange(card, events, activatedAt, today) {
  parseDate(activatedAt);
  parseDate(today);
  if (activatedAt > today) throw new Error('开通日期不能是未来的日期');
  if (!card) return;
  const conflictsWithRule = card.rules.some(rule => rule.dueDate < activatedAt || (rule.lastCompletedAt && rule.lastCompletedAt < activatedAt));
  const conflictsWithHistory = events.some(event => event.cardId === card.id && event.completedAt < activatedAt);
  if (conflictsWithRule || conflictsWithHistory) throw new Error('开通日期不能晚于已有的续期记录或计划日期');
}

export const ACTIONS = {
  sms:{label:'发送短信', icon:'message'},
  call:{label:'拨打电话', icon:'phone'},
  purchase:{label:'购买套餐', icon:'bag'},
  reset:{label:'重置有效期', icon:'refresh'},
  topup:{label:'账户充值', icon:'wallet'},
  custom:{label:'自定义操作', icon:'check'},
};

export function dueStatus(date, today = todayString()) {
  const days = daysUntil(date, today);
  if (days < 0) return {label:`逾期 ${-days} 天`, tone:'danger', days};
  if (days === 0) return {label:'今天到期', tone:'danger', days};
  if (days <= 7) return {label:`${days} 天后到期`, tone:'warning', days};
  return {label:`${days} 天后到期`, tone:'success', days};
}

export const cycleText = rule => `每 ${rule.interval} ${rule.unit === 'months' ? '个月' : '天'}`;

export function formatDate(value, short = false) {
  if (!value) return '尚未设置';
  const date = parseDate(value);
  return short ? `${date.getUTCMonth() + 1} 月 ${date.getUTCDate()} 日` : value.replaceAll('-', '.');
}
