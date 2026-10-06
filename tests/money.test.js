import assert from 'node:assert/strict';
let money;
try {money=await import('../money.js');} catch {}
assert.ok(money,'Exact currency helpers must exist');
const {normalizeAmount,sumMoney,balanceAfter,formatMoney}=money;
assert.equal(normalizeAmount('00019.9','USD'),'19.90');
assert.equal(normalizeAmount('1000.00','JPY'),'1000');
assert.equal(normalizeAmount('1.234','KWD'),'1.234');
for(const [amount,currency] of [['1.001','USD'],['1.1','JPY'],['-1','USD'],['1e3','USD'],['NaN','USD'],['1000000000','USD'],['1','ZZZ']]) {
  assert.throws(()=>normalizeAmount(amount,currency));
}
assert.deepEqual(sumMoney([{currency:'USD',amount:'0.10'},{currency:'USD',amount:'0.20'},{currency:'JPY',amount:'1000'}]),[{currency:'JPY',amount:'1000'},{currency:'USD',amount:'0.30'}]);
assert.equal(balanceAfter([{currency:'USD',amount:'0.30'}],{currency:'USD',amount:'0.10'},'deduct').amount,'0.20');
assert.throws(()=>balanceAfter([],{currency:'USD',amount:'0.10'},'deduct'));
assert.throws(()=>balanceAfter([{currency:'USD',amount:'0.30'}],{currency:'USD',amount:'0.31'},'deduct'));
assert.equal(balanceAfter([],{currency:'HKD',amount:'5.50'},'credit').amount,'5.50');
assert.equal(formatMoney({currency:'USD',amount:'1250.50'}),'USD 1,250.50');
assert.equal(formatMoney({currency:'JPY',amount:'1000'}),'JPY 1,000');
assert.equal(formatMoney(null),'未填写');
console.log('Money: 18 checks passed');
