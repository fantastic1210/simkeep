import test from 'node:test';
import assert from 'node:assert/strict';

const core = await import('../core.js').catch(error => {
  if (error.code === 'ERR_MODULE_NOT_FOUND') return {};
  throw error;
});

function invoke(name, ...args) {
  assert.equal(typeof core[name], 'function', `${name} is required for renewal calculations`);
  return core[name](...args);
}

test('days advance across a year boundary', () => {
  assert.equal(invoke('addDays', '2026-12-31', 2), '2027-01-02');
});

test('calendar months clamp January 31 to the last day of February', () => {
  assert.equal(invoke('addCycle', '2026-01-31', 1, 'months'), '2026-02-28');
});

test('calendar months respect leap years', () => {
  assert.equal(invoke('addCycle', '2028-01-31', 1, 'months'), '2028-02-29');
});

test('days use whole business dates independent of daylight saving time', () => {
  assert.equal(invoke('daysUntil', '2026-03-09', '2026-03-07'), 2);
  assert.equal(invoke('daysUntil', '2026-10-03', '2026-10-04'), -1);
});

test('completion-based renewal starts from the actual completion date', () => {
  const rule = {dueDate:'2026-10-03', interval:90, unit:'days', anchor:'completion', anchorDate:'2026-07-05'};
  assert.equal(invoke('nextAfterCompletion', rule, '2026-10-04'), '2027-01-02');
});

test('early fixed renewal advances one scheduled cycle rather than retaining the completed deadline', () => {
  const rule = {dueDate:'2026-10-10', interval:1, unit:'months', anchor:'scheduled', anchorDate:'2026-10-10'};
  assert.equal(invoke('nextAfterCompletion', rule, '2026-10-04'), '2026-11-10');
});

test('overdue fixed renewal skips elapsed cycles', () => {
  const rule = {dueDate:'2026-01-31', interval:1, unit:'months', anchor:'scheduled', anchorDate:'2026-01-31'};
  assert.equal(invoke('nextAfterCompletion', rule, '2026-04-01'), '2026-04-30');
});

test('fixed monthly schedules restore the original day after a short month', () => {
  const rule = {dueDate:'2026-02-28', interval:1, unit:'months', anchor:'scheduled', anchorDate:'2026-01-31'};
  assert.equal(invoke('nextAfterCompletion', rule, '2026-02-28'), '2026-03-31');
});

test('invalid dates and cycles are rejected instead of silently overflowing', () => {
  assert.throws(() => invoke('addCycle', '2026-02-30', 1, 'months'), /日期/);
  assert.throws(() => invoke('addCycle', '2026-10-04', 0, 'days'), /周期/);
  assert.throws(() => invoke('addCycle', '2026-10-04', -1, 'days'), /周期/);
  assert.throws(() => invoke('addCycle', '2026-10-04', 1.5, 'days'), /周期/);
});

test('recording one rule leaves another renewal rule untouched', () => {
  const card = {id:'c1', activatedAt:'2026-01-01', rules:[
    {id:'sms', dueDate:'2026-10-03', interval:90, unit:'days', anchor:'completion', anchorDate:'2026-10-03'},
    {id:'plan', dueDate:'2026-10-20', interval:1, unit:'months', anchor:'scheduled', anchorDate:'2026-10-20'}
  ]};
  const result = invoke('completeRenewal', card, 'sms', '2026-10-04', '2026-10-04', '发了一条短信');
  assert.equal(result.card.rules[0].dueDate, '2027-01-02');
  assert.equal(result.card.rules[1].dueDate, '2026-10-20');
  assert.equal(card.rules[0].dueDate, '2026-10-03');
  assert.equal(result.event.oldDueDate, '2026-10-03');
  assert.equal(result.event.newDueDate, '2027-01-02');
});

test('completion cannot be in the future, before activation or before the last completion', () => {
  const card = {activatedAt:'2026-02-01', rules:[{id:'r1', dueDate:'2026-10-20', lastCompletedAt:'2026-09-20', interval:30, unit:'days', anchor:'completion'}]};
  assert.throws(() => invoke('completeRenewal', card, 'r1', '2026-10-05', '2026-10-04'), /未来/);
  assert.throws(() => invoke('completeRenewal', card, 'r1', '2026-01-01', '2026-10-04'), /开通/);
  assert.throws(() => invoke('completeRenewal', card, 'r1', '2026-09-01', '2026-10-04'), /上次/);
});

test('archived cards are excluded and remaining tasks sort by their actual deadline', () => {
  const cards = [
    {id:'a', archived:false, rules:[{id:'late',dueDate:'2026-10-20'},{id:'soon',dueDate:'2026-10-03'}]},
    {id:'b', archived:true, rules:[{id:'archived',dueDate:'2026-09-01'}]},
    {id:'c', archived:false, rules:[{id:'middle',dueDate:'2026-10-10'}]}
  ];
  assert.deepEqual(invoke('getTasks', cards).map(task => task.rule.id), ['soon','middle','late']);
});

test('user timezone determines today around the UTC midnight boundary', () => {
  const instant = new Date('2026-10-03T17:00:00Z');
  assert.equal(invoke('todayString', 'Asia/Shanghai', instant), '2026-10-04');
  assert.equal(invoke('todayString', 'America/New_York', instant), '2026-10-03');
});

test('editing activation cannot invalidate an older renewal event even when the latest completion is later', () => {
  const card = {id:'c1', activatedAt:'2026-01-01', rules:[{dueDate:'2026-12-01',lastCompletedAt:'2026-10-04'}]};
  const events = [
    {cardId:'c1',completedAt:'2026-06-01'},
    {cardId:'c1',completedAt:'2026-10-04'},
  ];
  assert.throws(() => invoke('validateActivationChange', card, events, '2026-08-01', '2026-10-04'), /续期记录/);
});

test('editing activation ignores another card history and permits a correction before its own history', () => {
  const card = {id:'c1',activatedAt:'2026-01-01',rules:[{dueDate:'2026-12-01'}]};
  const events = [{cardId:'c2',completedAt:'2026-02-01'},{cardId:'c1',completedAt:'2026-06-01'}];
  assert.doesNotThrow(() => invoke('validateActivationChange', card, events, '2026-05-01', '2026-10-04'));
});

test('HTTP browsers without randomUUID can still generate distinct valid card identifiers', () => {
  const httpCrypto = {getRandomValues:globalThis.crypto.getRandomValues.bind(globalThis.crypto)};
  const first = invoke('createId', httpCrypto);
  const second = invoke('createId', httpCrypto);
  assert.match(first, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.match(second, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.notEqual(first,second);
});
