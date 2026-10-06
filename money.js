export const CURRENCIES={
  CNY:{label:'人民币',places:2},USD:{label:'美元',places:2},HKD:{label:'港币',places:2},
  GBP:{label:'英镑',places:2},EUR:{label:'欧元',places:2},JPY:{label:'日元',places:0},
  TWD:{label:'新台币',places:2},SGD:{label:'新加坡元',places:2},AUD:{label:'澳元',places:2},
  CAD:{label:'加元',places:2},CHF:{label:'瑞士法郎',places:2},NZD:{label:'新西兰元',places:2},
  KRW:{label:'韩元',places:0},THB:{label:'泰铢',places:2},MYR:{label:'马来西亚林吉特',places:2},
  AED:{label:'阿联酋迪拉姆',places:2},SAR:{label:'沙特里亚尔',places:2},IDR:{label:'印尼盾',places:2},
  INR:{label:'印度卢比',places:2},PHP:{label:'菲律宾比索',places:2},VND:{label:'越南盾',places:0},
  KWD:{label:'科威特第纳尔',places:3},BHD:{label:'巴林第纳尔',places:3},
};
export const COUNTRY_CURRENCY={GB:'GBP',US:'USD',HK:'HKD',JP:'JPY',CN:'CNY',DE:'EUR',SG:'SGD',OTHER:'USD'};

export function normalizeAmount(value,currency) {
  const places=CURRENCIES[currency]?.places;
  if(places===undefined) throw new Error('请选择支持的币种');
  if(typeof value!=='string'||value.length>30||!/^\d+(?:\.\d+)?$/.test(value)) throw new Error('金额须为不小于 0 的数字');
  const [rawInteger,fraction='']=value.split('.');
  const integer=rawInteger.replace(/^0+(?=\d)/,'');
  if(BigInt(integer)>999999999n||(BigInt(integer)===999999999n&&/[1-9]/.test(fraction))) throw new Error('金额不能超过 999999999');
  if(/[1-9]/.test(fraction.slice(places))) throw new Error(`${currency} 金额最多保留 ${places} 位小数`);
  return integer+(places ? '.'+fraction.slice(0,places).padEnd(places,'0') : '');
}
const units = money => BigInt(normalizeAmount(money.amount,money.currency).replace('.',''));
function fromUnits(value,currency) {
  const places=CURRENCIES[currency].places;
  const digits=value.toString().padStart(places+1,'0');
  return places ? digits.slice(0,-places)+'.'+digits.slice(-places) : digits;
}
export function sumMoney(values) {
  const sums=new Map();
  for(const money of values.filter(Boolean)) sums.set(money.currency,(sums.get(money.currency)||0n)+units(money));
  return [...sums].sort(([a],[b])=>a.localeCompare(b)).map(([currency,value])=>({currency,amount:fromUnits(value,currency)}));
}
export function balanceAfter(balances,cost,operation) {
  if(!cost||!['deduct','credit'].includes(operation)) throw new Error('更新余额时须填写本次金额和币种');
  const current=balances.find(item=>item.currency===cost.currency);
  if(!current&&operation==='deduct') throw new Error(`尚未记录 ${cost.currency} 余额，请先在卡片资料中添加`);
  const before=current ? units(current) : 0n;
  const after=operation==='deduct' ? before-units(cost) : before+units(cost);
  if(after<0n) throw new Error(`${cost.currency} 余额不足，可取消更新余额后单独记录费用`);
  return {currency:cost.currency,amount:normalizeAmount(fromUnits(after,cost.currency),cost.currency)};
}
export function formatMoney(money) {
  if(!money) return '未填写';
  const [integer,fraction]=money.amount.split('.');
  return `${money.currency} ${integer.replace(/\B(?=(\d{3})+(?!\d))/g,',')}${fraction===undefined ? '' : '.'+fraction}`;
}
