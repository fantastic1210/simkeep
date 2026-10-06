import {ACTIONS, addCycle, completeRenewal, createId, cycleText, daysUntil, dueStatus, formatDate, getTasks, parseDate, todayString, validateActivationChange} from './core.js';
import {COUNTRIES} from './countries.js';
import {api} from './api.js';
import {CURRENCIES,COUNTRY_CURRENCY,normalizeAmount,sumMoney,balanceAfter,formatMoney} from './money.js';

const paths = {
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  sim:'<path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a2 2 0 0 1 2-2Z"/><rect x="8" y="11" width="8" height="6" rx="1.5"/><path d="M12 11v6m-4-3h8"/>',
  esim:'<path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a2 2 0 0 1 2-2Z"/><path d="m13 10-4 5h4l-2 4"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2m-8 3h2"/>',
  layers:'<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  left:'<path d="m15 5-7 7 7 7"/>',
  down:'<path d="m7 10 5 5 5-5"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  export:'<path d="M12 3v12m-4-4 4 4 4-4M5 15v5h14v-5"/>',
  more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  list:'<path d="M9 6h12M9 12h12M9 18h12M3 6h1m-1 6h1m-1 6h1"/>',
  message:'<path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-5 3V6a2 2 0 0 1 2-2Z"/><path d="M7 9h10m-10 4h6"/>',
  phone:'<path d="m8 3 3 5-3 3c1.5 2.4 2.6 3.5 5 5l3-3 5 3c1 5-3 5-5 4C9 18 6 15 3 8 2 6 3 2 8 3Z"/>',
  bag:'<path d="M4 7h16l1 14H3L4 7Z"/><path d="M8 8V6a4 4 0 0 1 8 0v2"/>',
  refresh:'<path d="M20 10a8 8 0 0 0-14-5L3 8m0-5v5h5M4 14a8 8 0 0 0 14 5l3-3m0 5v-5h-5"/>',
  wallet:'<path d="M20 7H5a2 2 0 0 1 0-4h13v4M3 5v14a2 2 0 0 0 2 2h15V7m0 5h-5v5h5"/><path d="M16 14.5h1"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  checkCircle:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  link:'<path d="m10 13 4-4m-7 6-1 1a3.5 3.5 0 0 1-5-5l4-4a3.5 3.5 0 0 1 5 0m4 2 1-1a3.5 3.5 0 0 1 5 5l-4 4a3.5 3.5 0 0 1-5 0" transform="translate(1 1)"/>',
  telegram:'<path d="M21 3 3 10l7 3 3 7 8-17Z"/><path d="m10 13 6-6"/>',
  mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
  shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  edit:'<path d="m14 5 5 5M4 20l5-1L21 7a2 2 0 0 0-4-4L5 15l-1 5Z"/>',
  settings:'<path d="m10 3-.5 3-2 1.2L4.7 6 2.8 9.3l2.3 1.8v2L2.8 15l1.9 3.3 2.8-1.2 2 1.2.5 2.7h4l.5-2.7 2-1.2 2.8 1.2 1.9-3.3-2.3-1.9v-2l2.3-1.8L19.3 6l-2.8 1.2-2-1.2L14 3Z"/><circle cx="12" cy="12" r="3"/>',
  archive:'<path d="M4 8h16v13H4V8Z"/><path d="M3 3h18v5H3zm6 10h6"/>',
  trash:'<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
  menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 0 1 6 0c0 2-3 2-3 4m0 4h.01"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>',
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.sim}</svg>`;
const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uid = createId;
const el = selector => document.querySelector(selector);
const NAV = [
  {id:'overview',label:'总览',icon:'grid'}, {id:'cards',label:'我的卡片',icon:'sim'},
  {id:'renewals',label:'续期计划',icon:'calendar'}, {id:'platforms',label:'关联平台',icon:'layers'},
  {id:'settings',label:'通知设置',icon:'bell'},
];
const colors = {Telegram:'#63a9d9',WhatsApp:'#4cac88',Google:'#5e8be3',PayPal:'#5b80b7',Apple:'#7e8593',Amazon:'#da9b43',Discord:'#7987d9',WeChat:'#65b684',AlipayHK:'#609ee2',GitHub:'#697487',Microsoft:'#6d9dce',MobiMatter:'#e6935e',My3:'#5c87df',Tello:'#56a294',Airalo:'#ce7689'};

let serverUser = null, authMode = 'login', isMutating = false;
let view = 'overview', filter = 'all', layout = 'grid', query = '', showArchived = false, taskFilter = 'all';
const emptyWorkspace = () => ({version:2,cards:[],events:[],settings:{timezone:'Asia/Shanghai',time:'09:00',offsets:[7,3,1],overdue:true,telegram:false,email:false,emailAddress:'',emailVerified:false,telegramVerified:false,chatId:''},services:{telegram:{configured:false},email:{configured:false}},notifications:[]});
let data = emptyWorkspace();
let monthDate = parseDate(`${today().slice(0,7)}-01`), selectedDate = null;
let previousFocus = null, overlayCleanup = null, toastTimer, detailReturn = null, telegramBindingCode = '';

function today() {return todayString(data?.settings?.timezone || 'Asia/Shanghai');}
const user = () => serverUser;
const findCard = id => data.cards.find(card => card.id === id);
const tasks = () => getTasks(data.cards);
const nearest = card => [...card.rules].sort((a,b) => a.dueDate.localeCompare(b.dueDate))[0];
function savedMessage(message) {toast(message);}
const configured = channel => Boolean(data.services?.[channel]?.configured);
const verified = channel => Boolean(data.settings[channel === 'telegram' ? 'telegramVerified' : 'emailVerified']);
const channelReady = channel => configured(channel) && verified(channel) && data.settings[channel];
const channelStatus = channel => !configured(channel) ? '服务待配置' : !verified(channel) ? channel === 'telegram' ? '待绑定' : '待验证' : data.settings[channel] ? '已启用' : '未启用';
async function mutation(method,path,payload) {
  if (isMutating) throw new Error('上一项操作正在保存，请稍候');
  isMutating = true;
  try {const result = await api.request(method,path,payload);api.assertCurrent(result);if (result.workspace) data = result.workspace;return result;}
  finally {isMutating = false;}
}
function reportError(error,form=null) {
  if (error.name === 'StaleResponse') return;
  if (error.sessionGeneration !== undefined && error.sessionGeneration !== api.generation) return;
  if (error.status === 401 && serverUser) {
    closeOverlay(false);serverUser = null;data = emptyWorkspace();api.clear();renderAuth('登录已过期，请重新登录');return;
  }
  if (form?.isConnected && form.querySelector('.form-error')) formError(form,error.message);else toast(error.message,true);
}
async function refreshWorkspace() {
  const result = await api.request('GET','/api/workspace');
  api.assertCurrent(result);data = result.workspace;
}

function flag(country) {
  const graphics = {
    GB:'<rect width="60" height="40" fill="#344579"/><path d="m0 0 60 40m0-40L0 40" stroke="#fff" stroke-width="9"/><path d="m0 0 60 40m0-40L0 40" stroke="#d95364" stroke-width="3"/><path d="M30 0v40M0 20h60" stroke="#fff" stroke-width="13"/><path d="M30 0v40M0 20h60" stroke="#d95364" stroke-width="7"/>',
    US:'<rect width="60" height="40" fill="#fff"/><path d="M0 3h60M0 10h60M0 17h60M0 24h60M0 31h60M0 38h60" stroke="#d46b77" stroke-width="3.5"/><rect width="26" height="22" fill="#5477b2"/><path d="M5 5h1m5 0h1m5 0h1m-13 6h1m5 0h1m5 0h1m-13 6h1m5 0h1m5 0h1" stroke="#fff" stroke-width="2"/>',
    HK:'<rect width="60" height="40" fill="#dc6268"/><g fill="#fff" transform="translate(30 20)"><ellipse rx="4" ry="8" transform="translate(0 -6)"/><ellipse rx="4" ry="8" transform="rotate(72) translate(0 -6)"/><ellipse rx="4" ry="8" transform="rotate(144) translate(0 -6)"/><ellipse rx="4" ry="8" transform="rotate(216) translate(0 -6)"/><ellipse rx="4" ry="8" transform="rotate(288) translate(0 -6)"/></g>',
    JP:'<rect width="60" height="40" fill="#fff"/><circle cx="30" cy="20" r="11" fill="#d95b6a"/>',
    CN:'<rect width="60" height="40" fill="#dc6268"/><path d="m12 7 2 5 5 .2-4 3 1.4 5L12 17l-4.4 3.2 1.4-5-4-3 5-.2Z" fill="#f2d077"/>',
    DE:'<rect width="60" height="14" fill="#3f4450"/><rect y="14" width="60" height="13" fill="#d66b72"/><rect y="27" width="60" height="13" fill="#edc660"/>',
    SG:'<rect width="60" height="20" fill="#d96b74"/><rect y="20" width="60" height="20" fill="#fff"/><circle cx="15" cy="10" r="7" fill="#fff"/><circle cx="18" cy="9" r="6" fill="#d96b74"/>',
  };
  return `<span class="flag" title="${e(COUNTRIES[country] || COUNTRIES.OTHER)}"><svg viewBox="0 0 60 40" aria-hidden="true">${graphics[country] || '<rect width="60" height="40" fill="#aab7cf"/><circle cx="30" cy="20" r="12" fill="none" stroke="white" stroke-width="3"/>'}</svg></span>`;
}
const provider = (card, mini = false) => `<span class="${mini ? 'provider-mini' : 'provider-logo'}" style="--brand-color:${e(card.color)}" data-provider="${e(card.provider)}">${e(card.mark)}</span>`;
const typeTag = card => `<span class="type-tag ${card.type === 'SIM' ? 'physical' : ''}">${icon(card.type === 'SIM' ? 'sim' : 'esim')}${e(card.type)}</span>`;
const statusBadge = date => {const status = dueStatus(date,today());return `<span class="status ${status.tone}">${status.label}</span>`;};
const platformBadge = registration => `<span class="platform-tag"><span class="platform-dot" style="--platform-color:${colors[registration.name] || '#8e9ab3'}">${e(registration.name[0])}</span>${e(registration.name)}</span>`;
const moneyTags = values => values.length ? values.map(value=>`<span class="money-tag">${e(formatMoney(value))}</span>`).join('') : '<span class="money-unknown">未记录余额</span>';
const cardCurrency = card => card?.balances?.[0]?.currency || COUNTRY_CURRENCY[card?.country] || 'USD';

function renderMoneySummary() {
  const balances = sumMoney(data.cards.filter(card=>!card.archived).flatMap(card=>card.balances || []));
  const upcoming = tasks().filter(task=>daysUntil(task.rule.dueDate,today())<=30);
  const costs = sumMoney(upcoming.map(task=>task.rule.cost));
  const unpriced = upcoming.filter(task=>!task.rule.cost).length;
  return `<section class="money-summary" aria-label="余额与续期金额"><div><h2>${icon('wallet')}在用卡片余额</h2><div class="money-tags">${moneyTags(balances)}</div><p>按币种分别汇总</p></div><div><h2>${icon('calendar')}近 30 天待办金额</h2><div class="money-tags">${costs.length ? moneyTags(costs) : '<span class="money-unknown">暂无已填写金额的待办</span>'}</div><p>含逾期${unpriced ? ` · ${unpriced} 项未填写金额` : ''}</p></div></section>`;
}

function renderAuth(message = '') {
  const registering = authMode === 'register';
  el('#app').innerHTML = `<main class="auth-shell"><section class="auth-story"><a class="brand" href="#" aria-label="续卡 SIMKEEP"><span class="brand-symbol">${icon('sim')}</span><span class="brand-name">续卡<small>SIMKEEP</small></span></a><div class="auth-story-content"><h1>每个号码，<br>都有它的下一次。</h1><p>从第一次开通，到每一次续期。<br>把卡片、账号与提醒，放在自己的空间里。</p><div class="connection-illustration" aria-hidden="true"><div class="illustration-sim">${icon('sim')}<span>SIM & eSIM</span><div class="sim-chip"><i></i><i></i><i></i><i></i><i></i><i></i></div></div><div class="illustration-timeline"><div><span class="timeline-dot done"></span><strong>开通连接</strong><small>留下最初的日期</small></div><div><span class="timeline-dot"></span><strong>安排下次续期</strong><small>短信、通话、重置或购买套餐</small></div><div><span class="timeline-dot hollow"></span><strong>提醒，准时到达</strong><small>Telegram 与邮箱陪你记得</small></div></div></div></div><p class="auth-story-foot">每一条连接，都有迹可循</p></section><section class="auth-panel"><div class="auth-form-wrap"><div class="auth-tabs" role="group" aria-label="账号入口"><button data-action="auth-login" class="${!registering ? 'active' : ''}" aria-pressed="${!registering}">登录</button><button data-action="auth-register" class="${registering ? 'active' : ''}" aria-pressed="${registering}">创建账号</button></div><h2>${registering ? '开启你的卡片空间' : '回来照顾你的连接'}</h2><p class="auth-intro">${registering ? '每个人都有独立的卡片、平台与续期记录。' : '登录后，接着管理你的 SIM 与 eSIM。'}</p><form id="auth-form"><div class="form-error" ${message ? '' : 'hidden'} role="alert">${e(message)}</div>${registering ? field('auth-name','你的名字',`<input id="auth-name" name="name" autocomplete="nickname" required maxlength="45" placeholder="怎么称呼你">`) : ''}${field('auth-email','邮箱',`<input id="auth-email" name="email" type="email" autocomplete="username" required maxlength="120" placeholder="you@example.com">`)}${field('auth-password','密码',`<input id="auth-password" name="password" type="password" autocomplete="${registering ? 'new-password' : 'current-password'}" minlength="${registering ? '10' : '1'}" maxlength="128" required placeholder="${registering ? '至少 10 个字符' : '输入密码'}">`)}<button class="btn btn-primary auth-submit" type="submit">${registering ? '创建账号，开始管理' : '登录我的空间'}${icon('chevron')}</button></form><p class="auth-account-note">${icon('shield')}你的卡片记录随账号保存</p></div><footer class="auth-footer">续卡 SIMKEEP · SIM 与 eSIM 管理</footer></section></main>`;
}
async function bootstrap() {
  const generation = api.generation;
  el('#app').innerHTML = `<main class="bootstrap"><span class="brand-symbol">${icon('sim')}</span><p>正在打开你的卡片空间…</p></main>`;
  try {
    const session = await api.request('GET','/api/auth/me');
    const result = await api.request('GET','/api/workspace');
    api.assertCurrent(session);api.assertCurrent(result);
    serverUser = session.user;data = result.workspace;
    monthDate = parseDate(`${today().slice(0,7)}-01`);renderApp();
  } catch (error) {
    if (generation !== api.generation) return;
    if (error.name === 'StaleResponse') return;
    if (error.status === 401) renderAuth();
    else el('#app').innerHTML = `<main class="bootstrap"><span class="brand-symbol">${icon('sim')}</span><p>${e(error.message)}</p><button class="btn btn-primary" data-action="retry-bootstrap">重新连接</button></main>`;
  }
}

function renderApp(keepSearch = false) {
  if (!serverUser) {renderAuth();return;}
  const pos = keepSearch ? el('#global-search')?.selectionStart : null;
  const count = tasks().filter(task => daysUntil(task.rule.dueDate,today()) <= 7).length;
  el('#app').innerHTML = `<div class="app-shell">
    <aside class="sidebar" aria-label="主导航">
      <a class="brand" href="#overview" data-nav="overview"><span class="brand-symbol">${icon('sim')}</span><span class="brand-name">续卡<small>SIMKEEP</small></span></a>
      <div class="nav-caption">工作空间</div><nav class="nav-list">${NAV.map(item => `<button class="nav-button ${view === item.id ? 'active' : ''}" data-nav="${item.id}" title="${item.label}" ${view === item.id ? 'aria-current="page"' : ''}>${icon(item.icon)}<span>${item.label}</span>${item.id === 'renewals' && count ? `<span class="nav-count">${count}</span>` : ''}</button>`).join('')}</nav>
      <div class="sidebar-spacer"></div>
      <button class="nav-button" data-action="help" title="帮助与说明">${icon('help')}<span>帮助与说明</span></button>
      <div class="sidebar-note"><div class="note-icon">${icon('shield')}</div><h4>你的号码，你的空间</h4><p>卡片与平台记录随账号管理<br>每一条连接都有自己的归属</p><button data-action="account">查看当前账号 ${icon('chevron')}</button></div>
      <button class="sidebar-user" data-action="account" aria-label="我的账号"><span class="avatar">${e(user().initial)}</span><span class="user-text"><strong>${e(user().name)}</strong><small>我的个人空间</small></span>${icon('down')}</button>
    </aside>
    <div class="main-shell"><header class="topbar"><button class="icon-button mobile-menu" data-action="menu" aria-label="打开导航">${icon('menu')}</button><div class="breadcrumbs"><span>工作空间</span>${icon('chevron')}<strong>${NAV.find(item => item.id === view)?.label}</strong></div>
      <div class="topbar-right"><label class="global-search" for="global-search">${icon('search')}<input id="global-search" name="global-search" value="${e(query)}" placeholder="搜索卡片、号码或平台" aria-label="搜索卡片、号码或平台"><kbd>⌘ K</kbd></label><button class="icon-button" data-action="refresh" aria-label="刷新卡片资料" title="刷新卡片资料">${icon('refresh')}</button><button class="icon-button notification-button" data-action="reminders" aria-label="查看近期提醒">${icon('bell')}</button><span class="topbar-divider"></span><button class="topbar-avatar" data-action="account" aria-label="我的账号"><span class="avatar">${e(user().initial)}</span>${icon('down')}</button></div>
    </header><main class="content" id="content">${renderContent()}</main></div>
  </div>`;
  if (keepSearch) {el('#global-search').focus();if (pos !== null) el('#global-search').setSelectionRange(pos,pos);}
}

function heading(title, subtitle, actions = true) {
  return `<div class="page-heading"><div><div class="heading-title"><h1>${title}</h1></div><p>${subtitle}</p></div>${actions ? `<div class="heading-actions"><button class="btn" data-action="export">${icon('export')}导出</button><button class="btn btn-primary" data-action="add-card">${icon('plus')}添加卡片</button></div>` : ''}</div>`;
}
function footer() {return `<footer class="page-footer"><span>续卡 SIMKEEP <span>·</span> 每一条连接，都有迹可循</span><span>${icon('shield')}资料已保存到你的账号</span></footer>`;}
function renderContent() {
  if (view === 'settings') return renderSettings() + footer();
  if (view === 'renewals') return renderRenewals() + footer();
  if (view === 'platforms') return renderPlatforms() + footer();
  return heading(view === 'overview' ? '卡片总览' : '我的卡片', view === 'overview' ? '管理每一条连接，让重要的号码一直在线。' : '号码、开通时间与平台记录，放在一起更清楚。') +
    (view === 'overview' ? renderStats() + renderMoneySummary() + renderUpcoming() : '') +
    `<div class="workspace-grid"><section aria-label="卡片集合">${renderCollection()}</section><aside class="right-rail">${renderCalendar()}${renderReminderPanel()}<p class="rail-tip">${icon('clock')}所有日期按 ${e(data.settings.timezone)} 计算</p></aside></div>` + footer();
}
function renderStats() {
  const active = data.cards.filter(card => !card.archived);
  const soon = tasks().filter(task => daysUntil(task.rule.dueDate,today()) <= 7).length;
  const registrations = active.reduce((sum,card) => sum + card.platforms.length,0);
  return `<section class="stat-strip" aria-label="管理概况">
    <div class="stat"><div class="stat-label">${icon('sim')}卡片总数</div><div class="stat-line"><span class="stat-value">${active.length.toString().padStart(2,'0')}</span><span class="stat-unit">张</span></div><p class="stat-foot"><span class="stat-colored">${active.filter(card => card.type === 'eSIM').length} eSIM</span> <span> / </span> ${active.filter(card => card.type === 'SIM').length} 实体 SIM</p></div>
    <div class="stat"><div class="stat-label">${icon('calendar')}近期续期</div><div class="stat-line"><span class="stat-value">${soon.toString().padStart(2,'0')}</span><span class="stat-unit">项</span></div><p class="stat-foot">未来 7 天内需要照顾的连接</p></div>
    <div class="stat"><div class="stat-label">${icon('layers')}平台绑定</div><div class="stat-line"><span class="stat-value">${registrations.toString().padStart(2,'0')}</span><span class="stat-unit">条</span></div><p class="stat-foot">重要账号与号码一一对应</p></div>
    <div class="stat"><div class="stat-label">${icon('bell')}提醒渠道</div><div class="stat-line"><span class="stat-value">${['telegram','email'].filter(channelReady).length.toString().padStart(2,'0')}</span><span class="stat-unit">个</span></div><p class="stat-foot">Telegram 和邮箱自动提醒</p></div>
  </section>`;
}
function renderUpcoming() {
  const soon = tasks().filter(task => daysUntil(task.rule.dueDate,today()) <= 7);
  return `<section class="renewal-strip" aria-label="近期续期任务"><span class="renewal-strip-icon">${icon(soon.length ? 'calendar' : 'checkCircle')}</span><div class="renewal-intro"><h3>${soon.length ? `${soon.length} 项续期，记得安排` : '本周的连接都已照顾好'}</h3><p>${soon.length ? '做一个小动作，让号码继续在线' : '没有临近到期的任务，安心使用'}</p></div><div class="renewal-pills">${soon.slice(0,3).map(({card,rule}) => `<button class="renewal-pill" data-action="complete" data-card="${e(card.id)}" data-rule="${e(rule.id)}" title="记录 ${e(card.name)} 的${ACTIONS[rule.action].label}">${provider(card,true)}<span><strong>${e(card.provider)}</strong><small>${formatDate(rule.dueDate,true)} · ${ACTIONS[rule.action].label}</small></span></button>`).join('')}</div><button class="text-button" data-nav="renewals">查看计划 ${icon('chevron')}</button></section>`;
}
function matches(card) {
  const haystack = [card.name,card.provider,card.phone,COUNTRIES[card.country],...card.platforms.flatMap(platform => [platform.name,platform.account])].join(' ').toLowerCase();
  return haystack.includes(query.trim().toLowerCase());
}
function visibleCards() {return data.cards.filter(card => (showArchived ? card.archived : !card.archived) && (filter === 'all' || card.type === filter) && matches(card));}
function renderCollection() {
  const cards = visibleCards();
  const all = data.cards.filter(card => showArchived ? card.archived : !card.archived);
  const count = type => all.filter(card => card.type === type).length;
  return `<div class="section-header"><h2 class="section-title">${showArchived ? '已归档卡片' : '我的卡片'}<span class="count">${cards.length}</span></h2><div class="section-controls"><div class="segmented" aria-label="按卡片类型筛选">${[['all','全部',all.length],['eSIM','eSIM',count('eSIM')],['SIM','SIM',count('SIM')]].map(([value,label,n]) => `<button data-filter="${value}" class="${filter === value ? 'active' : ''}" aria-pressed="${filter === value}">${label}<span>${n}</span></button>`).join('')}</div><div class="view-toggle" aria-label="卡片视图"><button data-layout="grid" class="${layout === 'grid' ? 'active' : ''}" aria-label="网格视图" aria-pressed="${layout === 'grid'}">${icon('grid')}</button><button data-layout="list" class="${layout === 'list' ? 'active' : ''}" aria-label="列表视图" aria-pressed="${layout === 'list'}">${icon('list')}</button></div></div></div>
  ${cards.length ? layout === 'grid' ? `<div class="card-grid">${cards.map(renderCard).join('')}</div>` : renderCardTable(cards) : empty(query ? '没有找到匹配的卡片' : showArchived ? '还没有归档的卡片' : '在这里，留下你的第一条连接', query ? '试试搜索运营商、号码尾号或已关联的平台。' : '添加 SIM 或 eSIM，设置续期周期，剩下的日期交给续卡。', !query && !showArchived)}
  <div class="collection-foot"><span>${query ? `搜索“${e(query)}” · ` : ''}共 ${cards.length} 张${showArchived ? '归档' : ''}卡片</span><button class="text-button" data-action="toggle-archived">${showArchived ? '返回在用卡片' : '查看已归档'}</button></div>`;
}
function empty(title, description, add = false) {return `<div class="empty-state">${icon('sim')}<h3>${title}</h3><p>${description}</p>${add ? `<button class="btn btn-primary" data-action="add-card">${icon('plus')}添加卡片</button>` : ''}</div>`;}
function renderCard(card) {
  const rule = nearest(card);
  return `<article class="sim-card"><div class="card-top">${provider(card)}<div class="card-heading"><button data-action="detail" data-card="${e(card.id)}"><h3>${e(card.name)}</h3></button><p>${e(card.provider)}</p></div>${typeTag(card)}<button class="icon-button" data-action="card-actions" data-card="${e(card.id)}" aria-label="${e(card.name)}的更多操作">${icon('more')}</button></div>
    <div class="card-number ${!card.phone.startsWith('+') ? 'data-number' : ''}">${flag(card.country)}${e(card.phone || '未记录号码')}</div><div class="card-meta"><span>${icon('globe')}${e(COUNTRIES[card.country] || COUNTRIES.OTHER)}</span><span>${icon('clock')}${formatDate(card.activatedAt)} 开通</span></div>
    <div class="card-rule">${icon(rule ? ACTIONS[rule.action].icon : 'calendar')}<div class="card-rule-name">${rule ? ACTIONS[rule.action].label : '未设置续期'}<span>${rule ? cycleText(rule) : '添加一条规则'}${rule?.cost ? ` · ${e(formatMoney(rule.cost))}` : ''}</span></div><span class="card-rule-date">${rule ? formatDate(rule.dueDate) : '—'}</span></div>
    <div class="card-balance"><span>余额</span><div class="money-tags">${moneyTags(card.balances || [])}</div></div>
    <div class="platform-label">${icon('link')}关联平台 ${card.platforms.length ? `<span>(${card.platforms.length})</span>` : ''}${card.rules.length > 1 ? `<span style="margin-left:auto">${card.rules.length} 条续期规则</span>` : ''}</div><div class="platform-tags">${card.platforms.length ? card.platforms.slice(0,3).map(platformBadge).join('') + (card.platforms.length > 3 ? `<span class="platform-tag">+${card.platforms.length-3}</span>` : '') : '<span class="platform-tag">尚未关联平台</span>'}</div>
    <div class="card-footer">${card.archived ? '<span class="status neutral">已归档</span>' : rule ? statusBadge(rule.dueDate) : '<span class="status neutral">待设置续期</span>'}<button class="text-button" data-action="detail" data-card="${e(card.id)}">查看详情 ${icon('chevron')}</button></div>
  </article>`;
}
function renderCardTable(cards) {
  return `<div class="card-list"><table><thead><tr><th>卡片名称</th><th>类型 / 地区</th><th>开通日期</th><th>余额</th><th>下次操作 / 金额</th><th>下次续期</th><th></th></tr></thead><tbody>${cards.map(card => {const rule = nearest(card);return `<tr><td><button class="list-card-name" data-action="detail" data-card="${e(card.id)}">${provider(card,true)}<span><strong>${e(card.name)}</strong><small>${e(card.phone)}</small></span></button></td><td>${typeTag(card)} <span class="muted">${e(COUNTRIES[card.country])}</span></td><td class="muted">${formatDate(card.activatedAt)}</td><td><div class="money-tags">${moneyTags(card.balances || [])}</div></td><td>${rule ? ACTIONS[rule.action].label : '尚未设置'}${rule?.cost ? `<br><span class="muted">${e(formatMoney(rule.cost))}</span>` : ''}</td><td>${rule ? `${formatDate(rule.dueDate)}<br>${statusBadge(rule.dueDate)}` : '—'}</td><td><button class="icon-button" data-action="detail" data-card="${e(card.id)}" aria-label="查看${e(card.name)}">${icon('chevron')}</button></td></tr>`;}).join('')}</tbody></table></div>`;
}

function renderCalendar() {
  const year = monthDate.getUTCFullYear(), month = monthDate.getUTCMonth();
  const start = new Date(Date.UTC(year,month,1));
  start.setUTCDate(1 - ((start.getUTCDay() + 6) % 7));
  const dates = Array.from({length:42},(_,i) => {const date = new Date(start);date.setUTCDate(start.getUTCDate()+i);return date;});
  const upcoming = selectedDate ? tasks().filter(task => task.rule.dueDate === selectedDate) : tasks().filter(task => task.rule.dueDate.slice(0,7) === `${year}-${String(month+1).padStart(2,'0')}`).slice(0,3);
  return `<section class="panel calendar-panel"><div class="panel-heading"><h2>${icon('calendar')}续期日历</h2><button class="text-button" data-action="calendar-today">今天</button></div><div class="calendar-toolbar"><strong>${year} 年 ${month+1} 月</strong><div class="calendar-controls"><button class="icon-button" data-month="-1" aria-label="上个月">${icon('left')}</button><button class="icon-button" data-month="1" aria-label="下个月">${icon('chevron')}</button></div></div><div class="calendar-grid">${['一','二','三','四','五','六','日'].map(day => `<span class="weekday">${day}</span>`).join('')}${dates.map(date => {const value = date.toISOString().slice(0,10);const n = tasks().filter(task => task.rule.dueDate === value).length;return `<button class="calendar-day ${date.getUTCMonth() !== month ? 'other' : ''} ${value === today() ? 'today' : ''} ${selectedDate === value ? 'selected' : ''} ${n ? 'has-task' : ''}" data-date="${value}" aria-label="${value}${n ? `，${n}项续期` : '，没有续期任务'}" aria-pressed="${selectedDate === value}">${date.getUTCDate()}</button>`;}).join('')}</div><div class="calendar-legend"><span><i class="legend-dot"></i>今天</span><span><i class="legend-dot orange"></i>有续期任务</span></div><div class="calendar-events"><h4>${selectedDate ? `${formatDate(selectedDate,true)}的续期` : '本月接下来的安排'}</h4>${upcoming.length ? upcoming.map(({card,rule}) => `<button class="calendar-event" data-action="complete" data-card="${e(card.id)}" data-rule="${e(rule.id)}"><span class="calendar-event-day"><small>${Number(rule.dueDate.slice(5,7))}月</small>${Number(rule.dueDate.slice(8))}</span><span class="calendar-event-text"><strong>${e(card.name)}</strong><small>${ACTIONS[rule.action].label} · ${cycleText(rule)}</small></span>${icon('chevron')}</button>`).join('') : '<p class="empty-calendar">这段时间没有续期任务。<br>可以安心使用你的号码。</p>'}</div></section>`;
}
function renderReminderPanel() {
  return `<section class="panel reminder-panel"><div class="reminder-head"><span class="reminder-icon">${icon('bell')}</span><h3>重要的续期，有人记得</h3><p>提前收到提醒，按照步骤完成操作。<br>让每一张卡保持连接。</p></div><div class="channel-line"><span class="channel-symbol">${icon('telegram')}</span><strong>Telegram Bot</strong><span class="channel-label">${e(channelStatus('telegram'))}</span></div><div class="channel-line"><span class="channel-symbol email">${icon('mail')}</span><strong>邮箱提醒</strong><span class="channel-label">${e(channelStatus('email'))}</span></div><div class="panel-actions"><button class="text-button" data-nav="settings">管理通知 ${icon('chevron')}</button><button class="text-button" data-action="preview">预览提醒</button></div></section>`;
}
function renderRenewals() {
  const all = tasks().filter(task => matches(task.card));
  const shown = all.filter(task => taskFilter === 'all' || (taskFilter === 'soon' ? daysUntil(task.rule.dueDate,today()) <= 7 : daysUntil(task.rule.dueDate,today()) < 0));
  return heading('续期计划','什么时候，做什么。每一次保号与续订都有清楚的安排。') + `<section class="section-full"><div class="section-header"><h2 class="section-title">待完成的续期<span class="count">${shown.length}</span></h2><div class="segmented">${[['all','全部计划'],['soon','近 7 天'],['overdue','已逾期']].map(([key,label]) => `<button data-task-filter="${key}" class="${taskFilter === key ? 'active' : ''}" aria-pressed="${taskFilter === key}">${label}</button>`).join('')}</div></div><div class="task-list">${shown.length ? shown.map(({card,rule}) => `<article class="task-row"><div class="task-date"><small>${Number(rule.dueDate.slice(5,7))}月</small>${Number(rule.dueDate.slice(8))}</div>${provider(card,true)}<div class="task-info"><h3>${e(card.name)} <span class="muted">/ ${e(card.provider)}</span></h3><p><span>${icon(ACTIONS[rule.action].icon)}${ACTIONS[rule.action].label}</span><span>${cycleText(rule)}</span><span>${rule.anchor === 'scheduled' ? '固定周期' : '完成后顺延'}</span>${rule.cost ? `<span class="renewal-cost">${e(formatMoney(rule.cost))}</span>` : '<span class="muted">金额未填写</span>'}</p></div>${statusBadge(rule.dueDate)}<button class="btn btn-soft btn-small" data-action="complete" data-card="${e(card.id)}" data-rule="${e(rule.id)}">${icon('check')}记录完成</button></article>`).join('') : empty('这段时间没有待办','完成操作后，新的续期日期会自动出现在这里。')}</div></section>`;
}
function renderPlatforms() {
  const registrations = data.cards.filter(card => !card.archived && matches(card)).flatMap(card => card.platforms.map(platform => ({card,platform}))).filter(({platform,card}) => !query || `${platform.name} ${platform.account} ${card.name} ${card.phone} ${card.provider}`.toLowerCase().includes(query.toLowerCase()));
  return heading('关联平台','记住每个号码注册过什么，让账号归属有迹可循。',false) + `<div class="section-header"><h2 class="section-title">平台记录<span class="count">${registrations.length}</span></h2><button class="btn btn-primary btn-small" data-action="choose-platform">${icon('plus')}添加平台关联</button></div>${registrations.length ? `<div class="card-list"><table class="platform-table"><thead><tr><th>平台</th><th>关联卡片</th><th>账号标识</th><th>用途</th><th></th></tr></thead><tbody>${registrations.map(({card,platform}) => `<tr><td><span class="platform-name-cell"><span class="platform-initial" style="--platform-color:${colors[platform.name] || '#8e9ab3'}">${e(platform.name[0])}</span>${e(platform.name)}</span></td><td><button class="text-button" data-action="detail" data-card="${e(card.id)}">${e(card.name)}</button></td><td class="muted">${e(platform.account || '未填写')}</td><td class="muted">${e(platform.purpose || '未填写')}</td><td><button class="icon-button" data-action="remove-platform" data-card="${e(card.id)}" data-platform="${e(platform.id)}" aria-label="移除${e(platform.name)}关联">${icon('trash')}</button></td></tr>`).join('')}</tbody></table></div>` : empty('还没有匹配的平台记录','在卡片详情中关联平台，也可以点击上方按钮添加。')}`;
}

function previewMessage(task = tasks()[0]) {
  if (!task) return '<p class="preview-note">添加卡片和续期规则后，就可以预览提醒内容。</p>';
  const {card,rule} = task;
  const balance = (card.balances || []).find(item=>rule.cost && item.currency===rule.cost.currency);
  return `<div class="preview-message"><strong>${icon('bell')}续卡提醒 · ${e(card.name)}</strong><div><span class="preview-label">卡片</span>${e(card.provider)} / ${e(card.type)}</div><div><span class="preview-label">号码</span>${card.phone.startsWith('+') ? `尾号 ${e(card.phone.replace(/\s/g,'').slice(-4))}` : '数据卡 / 未填写号码'}</div><div><span class="preview-label">到期时间</span>${formatDate(rule.dueDate)}</div><div><span class="preview-label">续期操作</span>${ACTIONS[rule.action].label}</div><div><span class="preview-label">续期金额</span>${e(formatMoney(rule.cost))}</div>${balance ? `<div><span class="preview-label">同币种余额</span>${e(formatMoney(balance))}</div>` : ''}<div class="preview-instructions">${e(rule.instructions || '完成后在续卡记录操作，自动计算下一次日期。')}</div><button class="preview-link" data-action="detail" data-card="${e(card.id)}" style="width:100%">查看卡片并记录操作</button></div>`;
}
function renderSettings() {
  const s = data.settings;
  const zones = [['Asia/Shanghai','中国标准时间 · UTC+8'],['Asia/Hong_Kong','香港时间 · UTC+8'],['Europe/London','伦敦时间'],['America/New_York','纽约时间'],['Asia/Tokyo','东京时间 · UTC+9']];
  if (!zones.some(([zone]) => zone === s.timezone)) zones.push([s.timezone,s.timezone]);
  return heading('通知设置','配置自己的通知服务，再绑定接收账号，按时收到续期提醒。',false) + `<div class="settings-layout"><form id="settings-form" class="settings-main"><div class="form-error" hidden role="alert"></div><section class="panel settings-panel"><h2>${icon('telegram')}通知渠道</h2><p>Bot Token 和 SMTP 按账号单独保存。可以同时启用两种提醒。</p>
    <div class="settings-channel"><div class="settings-channel-head"><span class="channel-symbol">${icon('telegram')}</span><div><strong>Telegram Bot</strong><p>在 Bot 中点击开始，绑定你的个人账号</p></div><input class="switch" type="checkbox" name="telegram" aria-label="启用 Telegram 提醒" ${s.telegram ? 'checked' : ''}></div>${serviceSetup('telegram')}<div class="channel-actions"><span class="status ${channelReady('telegram') ? 'success' : 'neutral'}">${e(channelStatus('telegram'))}</span><button class="btn btn-small" type="button" data-action="bind-telegram" ${!configured('telegram') ? 'disabled' : ''}>${s.telegramVerified ? '重新绑定' : '绑定 Telegram'}</button>${s.telegramVerified ? `<button class="text-button" type="button" data-action="test-telegram" ${!configured('telegram') ? 'disabled' : ''}>发送测试</button><button class="text-button" type="button" data-action="unbind-telegram">解除绑定</button>` : ''}</div></div>
    <div class="settings-channel"><div class="settings-channel-head"><span class="channel-symbol email">${icon('mail')}</span><div><strong>邮箱提醒</strong><p>验证接收邮箱，确保提醒送到你手中</p></div><input class="switch" type="checkbox" name="email" aria-label="启用邮箱提醒" ${s.email ? 'checked' : ''}></div>${serviceSetup('email')}<div class="field"><label for="notify-email">接收邮箱</label><input id="notify-email" name="emailAddress" type="email" value="${e(s.emailAddress)}" placeholder="you@example.com" maxlength="120"><small>修改邮箱后先保存设置，再发送验证码。</small></div><div class="channel-actions"><span class="status ${s.emailVerified ? 'success' : 'neutral'}">${s.emailVerified ? '邮箱已验证' : '邮箱待验证'}</span><button class="btn btn-small" type="button" data-action="verify-email" ${!configured('email') ? 'disabled' : ''}>${s.emailVerified ? '重新验证' : '发送验证码'}</button>${s.emailVerified ? `<button class="text-button" type="button" data-action="test-email" ${!configured('email') ? 'disabled' : ''}>发送测试</button>` : ''}</div></div></section>
    <section class="panel settings-panel"><h2>${icon('clock')}提醒时间</h2><p>按你所在的时区安排提醒。到期当天总会提醒一次。</p><div class="fields-grid"><div class="field"><label for="timezone">时区</label><select name="timezone" id="timezone">${zones.map(([key,label]) => option(key,label,s.timezone)).join('')}</select></div><div class="field"><label for="notify-time">每天提醒时间</label><input type="time" id="notify-time" name="time" value="${e(s.time)}" required></div></div><hr class="form-divider"><span class="field-label">提前几天提醒</span><div class="offsets">${[...new Set([14,7,3,1,...s.offsets])].sort((a,b) => b-a).map(offset => `<label class="offset-check"><input type="checkbox" name="offset" value="${offset}" ${s.offsets.includes(offset) ? 'checked' : ''}>${offset} 天前</label>`).join('')}<span class="offset-check">${icon('check')}到期当天</span></div><label class="checkbox-line"><input type="checkbox" name="overdue" ${s.overdue ? 'checked' : ''}>已逾期的任务，每天提醒一次，直到记录完成</label></section><div class="settings-actions"><button class="btn" type="button" data-action="preview">${icon('mail')}预览提醒</button><button class="btn btn-primary" type="submit">${icon('check')}保存设置</button></div></form>
    <aside class="panel notification-preview"><h3>${icon('message')}通知看起来会是这样</h3>${previewMessage()}<p class="preview-note">开启渠道、完成绑定或验证并保存设置后，提醒会自动发送。关闭页面也能收到。</p><div class="service-status"><span>Telegram 服务 <strong>${configured('telegram') ? '已配置' : '待配置'}</strong></span><span>邮件服务 <strong>${configured('email') ? '已配置' : '待配置'}</strong></span></div></aside></div>${renderNotificationLog()}`;
}
function serviceSetup(channel) {
  const service = data.services[channel];
  const name = channel === 'telegram' ? 'Telegram' : '邮件';
  const explanation = service.source === 'account' ? '已保存本账号的配置' : service.source === 'server' ? '当前使用公共服务，可配置自己的服务' : channel === 'telegram' ? '先填写 BotFather 提供的 Bot Token' : '先填写发信服务器与 SMTP 授权码';
  return `<div class="channel-setup"><p>${icon(service.configured ? 'checkCircle' : 'settings')}${e(explanation)}</p><button type="button" class="btn btn-small service-config-button" data-action="configure-service" data-channel="${channel}">${icon('settings')}配置${name === 'Telegram' ? ' ' : ''}${name}</button></div>`;
}
function notificationConfigForm(channel) {
  const service = data.services[channel], telegram = channel === 'telegram';
  const secretNote = saved => saved ? '已保存，留空保留原值' : '填写后只保存在服务器，不会回显';
  const body = telegram ? `<div class="config-intro">${icon('telegram')}使用你在 BotFather 创建的 Bot。保存后，回到通知设置绑定 Telegram。</div>${field('telegram-token','Bot Token',`<input id="telegram-token" name="token" type="password" autocomplete="new-password" autocapitalize="off" spellcheck="false" maxlength="160" ${service.tokenSaved ? '' : 'required'} placeholder="${service.tokenSaved ? '已保存，留空保留原 Token' : '123456789:AA…'}"><small>${secretNote(service.tokenSaved)}</small>`)}<p class="channel-help">同一个 Bot 只能用于一个账号。更换 Token 后需要重新绑定。请让续卡独占这个 Bot 的更新读取。</p>` : `<div class="config-intro">${icon('mail')}配置发送邮件的服务。接收提醒的邮箱仍在通知设置中填写。</div><div class="fields-grid">${field('smtp-host','SMTP 服务器',`<input id="smtp-host" name="host" required maxlength="253" value="${e(service.host || '')}" placeholder="smtp.example.com" autocapitalize="off" spellcheck="false">`,true)}${field('smtp-port','端口',`<input id="smtp-port" name="port" type="number" min="1" max="65535" required value="${service.port || 587}">`)}${field('smtp-mode','安全方式',`<select id="smtp-mode" name="mode">${[['starttls','STARTTLS · 通常 587'],['ssl','SSL / TLS · 通常 465'],['plain','无加密']].map(([value,label])=>option(value,label,service.mode || 'starttls')).join('')}</select>`)}${field('smtp-from','发件邮箱',`<input id="smtp-from" name="sender" type="email" required maxlength="120" value="${e(service.from || '')}" placeholder="sender@example.com"><small>填写邮件服务允许使用的发件地址。</small>`,true)}${field('smtp-user','SMTP 用户名',`<input id="smtp-user" name="user" maxlength="254" value="${e(service.user || '')}" autocomplete="off" placeholder="通常为完整邮箱"><small>服务无需登录认证时留空。</small>`,true)}${field('smtp-password','SMTP 密码 / 授权码',`<input id="smtp-password" name="password" type="password" maxlength="1024" autocomplete="new-password" placeholder="${service.passwordSaved ? '已保存，留空保留原密码' : '填写密码或邮箱授权码'}"><small>${secretNote(service.passwordSaved)}</small>`,true)}</div>`;
  openOverlay(telegram ? '配置 Telegram' : '配置邮件','仅用于当前账号。Token 和密码保存后不会回显。',`<form id="notification-config-form" data-channel="${channel}"><div class="form-error" hidden role="alert"></div><div class="config-feedback" hidden role="status"></div>${body}<p class="config-check-note">“保存并检查”会测试连接与认证，不发送消息。</p>${service.source === 'account' ? `<button type="button" class="text-button config-clear" data-action="clear-service-config" data-channel="${channel}">清除本账号配置</button>` : ''}</form>`,`<button class="btn" data-action="close">取消</button><button class="btn" type="submit" form="notification-config-form" value="save">保存配置</button><button class="btn btn-primary" type="submit" form="notification-config-form" value="check">保存并检查</button>`,'config-modal');
}
function renderNotificationLog() {
  const labels = {pending:'等待发送',processing:'发送中',sent:'已发送',failed:'发送失败',cancelled:'已取消'};
  return `<section class="notification-log"><div class="section-header"><h2 class="section-title">发送记录<span class="count">${data.notifications.length}</span></h2><button class="text-button" data-action="refresh">${icon('refresh')}刷新记录</button></div>${data.notifications.length ? `<div class="card-list"><table><thead><tr><th>提醒渠道</th><th>安排时间</th><th>状态</th><th>尝试次数</th><th>说明</th></tr></thead><tbody>${data.notifications.map(log => `<tr><td>${log.channel === 'telegram' ? 'Telegram' : '邮箱'}</td><td>${e(new Intl.DateTimeFormat('zh-CN',{timeZone:data.settings.timezone,dateStyle:'short',timeStyle:'short'}).format(new Date(log.created_at*1000)))}</td><td><span class="status ${log.status === 'sent' ? 'success' : log.status === 'failed' ? 'danger' : 'neutral'}">${labels[log.status] || e(log.status)}</span></td><td>${log.attempts}</td><td>${e(log.error || (log.status === 'sent' ? '已提交到通知服务' : '—'))}</td></tr>`).join('')}</tbody></table></div>` : `<div class="notification-log-empty">${icon('bell')}还没有发送记录。续期提醒安排发送后，会出现在这里。</div>`}</section>`;
}
function emailCodeForm() {
  openOverlay('验证接收邮箱',`验证码已发送至 ${e(data.settings.emailAddress)}`,`<form id="email-code-form"><div class="form-error" hidden role="alert"></div>${field('email-code','6 位验证码',`<input id="email-code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" required placeholder="输入邮件里的验证码">`)}<p class="account-note">验证码 10 分钟内有效。没有收到时，请检查垃圾邮件。</p></form>`,`<button class="btn" data-action="close">稍后验证</button><button class="btn btn-primary" form="email-code-form" type="submit">验证邮箱</button>`,'small');
}
async function bindTelegram() {
  const binding = await mutation('POST','/api/notifications/telegram/binding');
  telegramBindingCode = binding.code;
  openOverlay('绑定 Telegram','打开 Bot，点击“开始”，然后回到这里检查绑定。',`<div class="binding-steps"><span class="channel-symbol">${icon('telegram')}</span><a class="btn btn-primary" href="${e(binding.url)}" target="_blank" rel="noopener noreferrer">打开 Telegram Bot ${icon('link')}</a><p>如果没有自动发送，手动向 Bot 发送：</p><div class="field"><input aria-label="Telegram 绑定指令" readonly value="/start ${e(binding.code)}"></div><p>绑定指令 10 分钟内有效，仅绑定你的私人聊天。</p></div>`,`<button class="btn" data-action="close">稍后绑定</button><button class="btn btn-primary" data-action="check-telegram">检查绑定</button>`,'small');
}

function toast(message, error = false) {
  clearTimeout(toastTimer);
  el('#toast-root').innerHTML = `<div class="toast ${error ? 'error' : ''}" role="status">${icon(error ? 'help' : 'checkCircle')}${e(message)}</div>`;
  toastTimer = setTimeout(() => {el('#toast-root').innerHTML = '';},4200);
}
function closeOverlay(restoreFocus = true) {
  if (overlayCleanup) {overlayCleanup();overlayCleanup = null;}
  el('#overlay-root').innerHTML = '';
  document.body.classList.remove('body-overlay');
  el('#app').inert = false;
  if (restoreFocus && previousFocus?.isConnected) previousFocus.focus();
}
function openOverlay(title, subtitle, body, footerHtml = '', kind = '') {
  closeOverlay(false);
  previousFocus = document.activeElement;
  el('#overlay-root').innerHTML = `<div class="overlay-backdrop ${kind === 'drawer' ? 'drawer-backdrop' : ''}"><section class="${kind === 'drawer' ? 'drawer' : `modal ${kind}`}" role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabindex="-1"><header class="modal-header"><div><h2 id="dialog-title">${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}</div><button class="icon-button" data-action="close" aria-label="关闭对话框">${icon('close')}</button></header><div class="modal-body">${body}</div>${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}</section></div>`;
  document.body.classList.add('body-overlay');
  el('#app').inert = true;
  const dialog = el('[role="dialog"]');
  const focusables = () => Array.from(dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]'));
  requestAnimationFrame(() => {(dialog.querySelector('input:not([type="hidden"]),select') || dialog.querySelector('button') || dialog).focus();});
  const onKey = event => {
    if (event.key === 'Escape') {event.preventDefault();closeOverlay();}
    if (event.key === 'Tab') {
      const elements = focusables(), first = elements[0], last = elements.at(-1);
      if (!first) {event.preventDefault();dialog.focus();}
      else if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {event.preventDefault();last.focus();}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault();first.focus();}
    }
  };
  document.addEventListener('keydown',onKey);
  overlayCleanup = () => document.removeEventListener('keydown',onKey);
}
const formError = (form, message) => {const target = form.querySelector('.form-error');target.textContent = message;target.hidden = false;target.scrollIntoView({block:'nearest'});};
const option = (value, label, selected) => `<option value="${e(value)}" ${value === selected ? 'selected' : ''}>${e(label)}</option>`;
const field = (id, label, input, wide = false) => `<div class="field ${wide ? 'wide' : ''}"><label for="${id}">${label}</label>${input}</div>`;
const currencyOptions = selected => Object.entries(CURRENCIES).map(([code,item])=>option(code,`${code} · ${item.label}`,selected)).join('');
function amountField(id,name,label,value='') {
  return field(id,label,`<input id="${e(id)}" name="${e(name)}" inputmode="decimal" maxlength="30" pattern="[0-9]+([.][0-9]+)?" value="${e(value)}" placeholder="留空表示未填写">`);
}
function costFields(prefix,cost=null,currency='USD',label='预计续期金额') {
  return `${amountField(prefix+'-amount','costAmount',label,cost?.amount || '')}${field(prefix+'-currency','金额币种',`<select id="${prefix}-currency" name="costCurrency">${currencyOptions(cost?.currency || currency)}</select>`)}`;
}
function readCost(form) {
  const value = form.elements.costAmount.value.trim();
  if (!value) return null;
  const currency = form.elements.costCurrency.value;
  return {currency,amount:normalizeAmount(value,currency)};
}
function balanceRow(balance={currency:'USD',amount:''}) {
  const id = 'balance-'+uid();
  return `<div class="balance-row">${field(id+'-currency','余额币种',`<select id="${id}-currency" name="balanceCurrency">${currencyOptions(balance.currency)}</select>`)}${amountField(id+'-amount','balanceAmount','余额金额',balance.amount)}<button class="icon-button" type="button" data-action="remove-balance-row" aria-label="移除这条余额">${icon('trash')}</button></div>`;
}
function readBalances(form) {
  const balances = [...form.querySelectorAll('.balance-row')].flatMap(row => {
    const amount = row.querySelector('[name="balanceAmount"]').value.trim();
    if (!amount) return [];
    const currency = row.querySelector('[name="balanceCurrency"]').value;
    return [{currency,amount:normalizeAmount(amount,currency)}];
  });
  if (new Set(balances.map(item=>item.currency)).size !== balances.length) throw new Error('同一张卡的每个币种只能记录一条余额');
  return balances;
}

function ruleFields(rule = {}, minDate = today(), currency = 'USD') {
  return `<div class="fields-grid">
    ${field('rule-action','续期操作<span>*</span>',`<select id="rule-action" name="action">${Object.entries(ACTIONS).map(([key,item]) => option(key,item.label,rule.action || 'sms')).join('')}</select>`)}
    ${field('rule-anchor','日期计算方式',`<select id="rule-anchor" name="anchor">${option('completion','按完成日期顺延',rule.anchor || 'completion')}${option('scheduled','保持固定周期',rule.anchor)}</select>`)}
    ${field('rule-interval','续期周期<span>*</span>',`<input id="rule-interval" name="interval" type="number" min="1" max="3650" step="1" required value="${rule.interval || 90}">`)}
    ${field('rule-unit','周期单位',`<select id="rule-unit" name="unit">${option('days','天',rule.unit || 'days')}${option('months','个月',rule.unit)}</select>`)}
    ${field('rule-due','下次到期日期<span>*</span>',`<input id="rule-due" name="dueDate" type="date" min="${minDate}" required value="${rule.dueDate || addCycle(minDate,rule.interval || 90,rule.unit || 'days')}">`,true)}
    ${costFields('rule-cost',rule.cost,currency)}
    ${field('rule-instructions','操作步骤',`<textarea id="rule-instructions" name="instructions" maxlength="1000" placeholder="例如：发送一条收费短信，确认成功后记录完成。">${e(rule.instructions || '')}</textarea>`,true)}
  </div>`;
}
function cardForm(card = null) {
  const editing = Boolean(card);
  const c = card || {name:'',provider:'',phone:'',type:'eSIM',country:'HK',activatedAt:today(),notes:'',plan:''};
  openOverlay(editing ? '编辑卡片' : '添加一张新卡片',editing ? '修改卡片档案；续期规则可在卡片详情中单独调整。' : '记下这条连接，再为它安排第一次续期。',`<form id="card-form" data-card="${e(card?.id || '')}" data-version="${card?.version || ''}"><div class="form-error" hidden role="alert"></div><div class="fields-grid">
    ${field('card-name','卡片名称<span>*</span>',`<input id="card-name" name="name" required maxlength="45" value="${e(c.name)}" placeholder="例如：英国常用号码">`,true)}
    ${field('card-provider','运营商<span>*</span>',`<input id="card-provider" name="provider" required maxlength="45" value="${e(c.provider)}" placeholder="例如：giffgaff">`)}
    ${field('card-type','卡片类型',`<select id="card-type" name="type">${option('eSIM','eSIM',c.type)}${option('SIM','实体 SIM',c.type)}</select>`)}
    ${field('card-phone','手机号码',`<input id="card-phone" name="phone" type="tel" maxlength="35" value="${e(c.phone)}" placeholder="数据 eSIM 可留空">`)}
    ${field('card-country','国家或地区',`<select id="card-country" name="country">${Object.entries(COUNTRIES).map(([key,label]) => option(key,label,c.country)).join('')}</select>`)}
    ${field('card-activation','开通日期<span>*</span>',`<input id="card-activation" name="activatedAt" type="date" required max="${today()}" value="${c.activatedAt}">`)}
    ${field('card-plan','套餐说明',`<input id="card-plan" name="plan" maxlength="60" value="${e(c.plan)}" placeholder="例如：10 GB / 30 天">`)}
  </div><hr class="form-divider"><div class="form-section-title"><h3>卡片余额</h3><button class="text-button" type="button" data-action="add-balance-row">${icon('plus')}添加币种</button></div><div id="balance-fields">${(c.balances?.length ? c.balances : [{currency:cardCurrency(c),amount:''}]).map(balanceRow).join('')}</div><p class="form-help">同一张卡可记录多个币种。留空表示未记录，填 0 表示余额为零。</p>${editing ? '' : `<hr class="form-divider"><h3 class="form-section-title">第一次续期<span class="muted" style="font-size:10px;font-weight:400">之后可添加更多规则</span></h3>${ruleFields({},today(),cardCurrency(c))}`}
  <hr class="form-divider">${field('card-notes','备注',`<textarea id="card-notes" name="notes" maxlength="1000" placeholder="卡片用途、保号条件或其他需要记住的事">${e(c.notes)}</textarea>`)}
  </form>`,`<button class="btn" data-action="close">取消</button><button class="btn btn-primary" type="submit" form="card-form">${icon('check')}${editing ? '保存修改' : '添加卡片'}</button>`);
  const form = el('#card-form');
  if (!editing) {
    form.addEventListener('input',event => {
      if (!['activatedAt','interval','unit'].includes(event.target.name)) return;
      try {form.elements.dueDate.min = form.elements.activatedAt.value;form.elements.dueDate.value = addCycle(form.elements.activatedAt.value,Number(form.elements.interval.value),form.elements.unit.value);} catch { /* Let form validation explain an unfinished value on submit. */ }
    });
  }
}
function readRule(form, existing = null) {
  const f = form.elements;
  const interval = Number(f.interval.value), unit = f.unit.value;
  if (!Number.isInteger(interval) || interval < 1 || interval > (unit === 'months' ? 120 : 3650)) throw new Error(`周期必须为 1–${unit === 'months' ? 120 : 3650} 的整数`);
  const dueDate = f.dueDate.value;
  parseDate(dueDate);
  return {action:f.action.value,interval,unit,dueDate,anchor:f.anchor.value,instructions:f.instructions.value.trim(),cost:readCost(form),...(existing ? {version:existing.version} : {})};
}
function ruleForm(cardId, ruleId = '') {
  const card = findCard(cardId), rule = card.rules.find(item => item.id === ruleId);
  detailReturn = cardId;
  openOverlay(rule ? '编辑续期规则' : '添加续期规则',`${e(card.name)} · 每条规则独立计算下一次日期`, `<form id="rule-form" data-card="${e(cardId)}" data-rule="${e(ruleId)}" data-version="${rule?.version || ''}"><div class="form-error" hidden role="alert"></div>${ruleFields(rule,card.activatedAt,cardCurrency(card))}<div class="instructions-box" style="margin-top:18px;margin-bottom:0">按完成日期顺延适合保号；固定周期适合套餐账单。修改当前到期日期会建立新的周期基准。</div></form>`,`<button class="btn" data-action="detail" data-card="${e(cardId)}">返回详情</button><button class="btn btn-primary" type="submit" form="rule-form">保存规则</button>`);
}
function completionForm(cardId, ruleId) {
  const card = findCard(cardId), rule = card?.rules.find(item => item.id === ruleId);
  if (!rule || card.archived) return;
  const minDate = rule.lastCompletedAt && rule.lastCompletedAt > card.activatedAt ? rule.lastCompletedAt : card.activatedAt;
  const balanceAction = rule.action === 'topup' ? 'credit' : 'deduct';
  openOverlay('记录续期完成','确认已经完成操作，记录花费并自动安排下一次。',`<div class="completion-summary">${provider(card)}<div><h3>${e(card.name)}</h3><p>${ACTIONS[rule.action].label} · ${cycleText(rule)} · ${rule.anchor === 'scheduled' ? '固定周期' : '完成后顺延'}</p></div></div><div class="instructions-box">${e(rule.instructions || '请确认续期操作成功后，再记录完成。')}</div><form id="completion-form" data-card="${e(cardId)}" data-rule="${e(ruleId)}" data-version="${rule.version}" data-card-version="${card.version}" data-balance-action="${balanceAction}"><div class="form-error" hidden role="alert"></div><div class="fields-grid">${field('completed-date','实际完成日期<span>*</span>',`<input id="completed-date" name="completedAt" type="date" required min="${minDate}" max="${today()}" value="${today()}">`,true)}${costFields('completed-cost',rule.cost,cardCurrency(card),'本次实际金额')}${field('completed-note','操作备注',`<textarea id="completed-note" name="note" maxlength="1000" placeholder="例如：短信已发送并扣费成功"></textarea>`,true)}</div><label class="checkbox-line balance-action"><input type="checkbox" name="updateBalance" ${balanceAction === 'deduct' ? 'checked' : ''}>${balanceAction === 'credit' ? '将本次金额计入同币种余额' : '从卡片同币种余额扣除本次金额'}</label><p class="form-help">${balanceAction === 'credit' ? '未勾选时只记录费用，余额保持当前记录。' : '默认扣除本次金额。取消勾选可只记录费用。'}</p><div class="calculation-preview balance-preview"><span>${balanceAction === 'credit' ? '入账后余额' : '扣除后余额'}</span><strong id="balance-after-preview">只记录费用</strong></div><div class="calculation-preview"><span>完成后，下次续期日期</span><strong id="next-date-preview">—</strong></div></form>`,`<button class="btn" data-action="close">取消</button><button class="btn btn-primary" type="submit" form="completion-form">${icon('check')}确认已完成</button>`,'small');
  const form = el('#completion-form');
  const updateDate = () => {try {el('#next-date-preview').textContent = formatDate(completeRenewal(card,ruleId,form.elements.completedAt.value,today()).card.rules.find(item => item.id === ruleId).dueDate);} catch (error) {el('#next-date-preview').textContent = error.message;}};
  const updateMoney = () => {
    const target = el('#balance-after-preview');
    try {
      target.textContent = form.elements.updateBalance.checked ? formatMoney(balanceAfter(card.balances || [],readCost(form),balanceAction)) : '只记录费用';
      target.classList.remove('money-error');
    } catch (error) {target.textContent = error.message;target.classList.add('money-error');}
  };
  form.dataset.requestId = uid();form.elements.completedAt.addEventListener('input',updateDate);form.addEventListener('input',updateMoney);form.addEventListener('change',updateMoney);updateDate();updateMoney();
}

function showDetail(cardId) {
  const card = findCard(cardId);
  if (!card) return;
  const history = data.events.filter(item => item.cardId === cardId).sort((a,b) => b.completedAt.localeCompare(a.completedAt));
  openOverlay('卡片详情','开通、平台与续期，一张卡的完整记录。',`<div class="detail-brand">${provider(card)}<div><h2>${e(card.name)}</h2><p>${e(card.provider)} ${typeTag(card)} ${card.archived ? '<span class="status neutral">已归档</span>' : ''}</p></div></div><dl class="detail-grid"><div><dt>号码</dt><dd>${e(card.phone)}</dd></div><div><dt>国家或地区</dt><dd>${flag(card.country)} ${e(COUNTRIES[card.country])}</dd></div><div><dt>开通日期</dt><dd>${formatDate(card.activatedAt)}</dd></div><div><dt>套餐说明</dt><dd>${e(card.plan || '未填写')}</dd></div><div class="detail-money"><dt>卡片余额</dt><dd class="money-tags">${moneyTags(card.balances || [])}</dd></div></dl><section class="detail-section"><div class="section-header"><h3>续期规则 <span class="muted">${card.rules.length}</span></h3><button class="text-button" data-action="add-rule" data-card="${e(cardId)}">${icon('plus')}添加规则</button></div>${card.rules.length ? [...card.rules].sort((a,b) => a.dueDate.localeCompare(b.dueDate)).map(rule => `<div class="detail-rule"><div class="detail-rule-head">${icon(ACTIONS[rule.action].icon)}<strong>${ACTIONS[rule.action].label}</strong><span>${cycleText(rule)}</span></div><div class="detail-rule-cost">预计续期金额 <strong>${e(formatMoney(rule.cost))}</strong></div><p>${e(rule.instructions || '尚未填写操作说明')}</p><div class="detail-rule-bottom"><span>下次 ${formatDate(rule.dueDate)}<br><span style="line-height:2">${rule.anchor === 'scheduled' ? '固定周期' : '按完成日顺延'}</span></span><div><button class="text-button" data-action="edit-rule" data-card="${e(cardId)}" data-rule="${e(rule.id)}">编辑</button>${!card.archived ? `<button class="btn btn-soft btn-small" data-action="complete" data-card="${e(cardId)}" data-rule="${e(rule.id)}">记录完成</button>` : ''}</div></div></div>`).join('') : '<p class="detail-note">添加一条规则，开始记录这张卡的续期计划。</p>'}</section><section class="detail-section"><div class="section-header"><h3>关联平台 <span class="muted">${card.platforms.length}</span></h3><button class="text-button" data-action="add-platform" data-card="${e(cardId)}">${icon('plus')}添加平台</button></div>${card.platforms.length ? card.platforms.map(platform => `<div class="detail-platform"><span class="platform-initial" style="--platform-color:${colors[platform.name] || '#8e9ab3'}">${e(platform.name[0])}</span><div><strong>${e(platform.name)}</strong><p>${e([platform.account,platform.purpose].filter(Boolean).join(' · ') || '未填写账号标识')}</p></div><button class="icon-button" data-action="remove-platform" data-card="${e(cardId)}" data-platform="${e(platform.id)}" aria-label="移除${e(platform.name)}关联">${icon('trash')}</button></div>`).join('') : '<p class="detail-note">记录这张卡注册的平台，下次找账号更方便。</p>'}</section><section class="detail-section"><div class="section-header"><h3>续期历史 <span class="muted">${history.length}</span></h3></div>${history.length ? history.map(item => `<div class="history-item"><strong>${formatDate(item.completedAt)} · ${ACTIONS[item.action]?.label || '续期操作'}</strong><p>下次续期 ${formatDate(item.newDueDate)}<br>本次金额 ${e(formatMoney(item.cost))}${item.balanceAfter ? `<br>${item.balanceAction === 'credit' ? '计入余额后' : '扣除后余额'} ${e(formatMoney(item.balanceAfter))}` : ''}${item.note ? `<br>${e(item.note)}` : ''}</p></div>`).join('') : '<p class="detail-note">还没有操作记录。完成一次续期后，历史会留在这里。</p>'}</section>${card.notes ? `<section class="detail-section"><h3 style="margin-bottom:10px">备注</h3><p class="detail-note">${e(card.notes)}</p></section>` : ''}`,`<button class="btn" data-action="archive-card" data-card="${e(cardId)}">${icon('archive')}${card.archived ? '恢复卡片' : '归档卡片'}</button><button class="btn btn-primary" data-action="edit-card" data-card="${e(cardId)}">${icon('edit')}编辑卡片</button>`,'drawer');
}
function platformForm(cardId = '') {
  const card = findCard(cardId);
  detailReturn = cardId || null;
  const available = data.cards.filter(item => !item.archived);
  if (!available.length && !card) {toast('请先添加一张卡片，再关联平台');return;}
  openOverlay('添加平台关联',card ? `${e(card.name)} · 记住这个号码注册过什么` : '选择卡片，记录平台和账号归属。',`<form id="platform-form" data-card="${e(cardId)}"><div class="form-error" hidden role="alert"></div><div class="fields-grid">${!card ? field('platform-card','关联卡片',`<select name="cardId" id="platform-card">${available.map(item => option(item.id,item.name,available[0].id)).join('')}</select>`,true) : ''}${field('platform-name','平台名称<span>*</span>',`<input name="name" id="platform-name" required maxlength="45" list="platform-options" placeholder="例如：Telegram、Google、PayPal"><datalist id="platform-options">${Object.keys(colors).map(name => `<option value="${name}">`).join('')}</datalist>`,true)}${field('platform-account','账号标识',`<input name="account" id="platform-account" maxlength="120" placeholder="邮箱、用户名或号码尾号">`,true)}${field('platform-purpose','用途',`<input name="purpose" id="platform-purpose" maxlength="80" placeholder="例如：账号验证、日常通讯、支付">`,true)}</div></form>`,`<button class="btn" ${card ? `data-action="detail" data-card="${e(cardId)}"` : 'data-action="close"'}>取消</button><button class="btn btn-primary" type="submit" form="platform-form">保存关联</button>`,'small');
}
function removePlatform(cardId, platformId) {
  const card = findCard(cardId), platform = card?.platforms.find(item => item.id === platformId);
  if (!platform) return;
  const wasDetail = Boolean(el('.drawer'));
  openOverlay('移除平台关联',`${e(card.name)} · ${e(platform.name)}`,`<p class="help-copy">移除这条平台记录？这只会更新续卡中的记录，不会注销该平台的实际账号。</p>`,`<button class="btn" ${wasDetail ? `data-action="detail" data-card="${e(cardId)}"` : 'data-action="close"'}>取消</button><button class="btn btn-danger" data-action="confirm-remove-platform" data-card="${e(cardId)}" data-platform="${e(platformId)}" data-return="${wasDetail ? cardId : ''}">移除关联</button>`,'small');
}
function showAccount() {
  openOverlay('我的账号','卡片、规则与通知设置保存在你的个人空间。',`<div class="account-option"><span class="avatar">${e(user().initial)}</span><div><strong>${e(user().name)}</strong><p>${e(user().email)}</p></div>${icon('checkCircle')}</div><p class="account-note">登录这个账号，可以在不同设备上继续管理你的卡片。导出的文件包含卡片和平台资料，请妥善保管。</p>`,`<button class="btn" data-action="logout">退出登录</button><button class="btn btn-primary" data-action="close">完成</button>`,'small');
}
function showHelp() {
  openOverlay('认识续卡','把号码与维护它的那些小事，放在同一个地方。',`<div class="help-copy"><h3>记录卡片</h3><p>添加运营商、号码、卡片类型和开通日期。数据 eSIM 可以不填写号码。</p><h3>安排续期</h3><p>一张卡可以有多条规则，分别管理短信保号、通话、充值、重置和购买套餐。实际完成后点击“记录完成”，自动更新所选规则的下次日期。</p><h3>找到平台注册记录</h3><p>打开卡片详情添加平台与账号标识；使用顶部搜索可以按平台找到关联卡片。</p><h3>接收自动提醒</h3><p>在通知设置绑定 Telegram 或验证邮箱，开启渠道并保存提醒时间。归档卡片会停止安排提醒，历史资料仍然保留。</p></div>`,`<button class="btn btn-primary" data-action="close">知道了</button>`);
}

function showReminders() {
  const upcoming = tasks().filter(task => daysUntil(task.rule.dueDate,today()) <= 7);
  openOverlay('近期提醒',`${upcoming.length} 项操作需要在未来 7 天内完成。`,upcoming.length ? `<div class="task-list">${upcoming.map(({card,rule}) => `<div class="completion-summary" style="margin-bottom:0">${provider(card,true)}<div style="flex:1"><h3>${e(card.name)}</h3><p>${formatDate(rule.dueDate)} · ${ACTIONS[rule.action].label}</p></div><button class="text-button" data-action="complete" data-card="${e(card.id)}" data-rule="${e(rule.id)}">记录完成</button></div>`).join('')}</div><p class="account-note">开启通知渠道并完成绑定或验证后，续期提醒会按设置的时间发送。</p>` : empty('本周没有待完成的续期','有新的临近到期任务时，会出现在这里。'),`<button class="btn btn-primary" data-nav="renewals">查看全部计划</button>`);
}
function exportData() {
  const blob = new Blob([JSON.stringify({exportedAt:new Date().toISOString(),user:user(),...data},null,2)],{type:'application/json'});
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url;link.download = `simkeep-${serverUser.id}-${today()}.json`;link.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);toast('已导出卡片、平台与续期记录');
}
function navigate(next) {
  closeOverlay(false);view = next;query = '';showArchived = false;filter = 'all';
  location.hash = next;
  renderApp();window.scrollTo({top:0,behavior:'instant'});
}
function showCardActions(cardId) {
  const card = findCard(cardId);
  openOverlay(e(card.name),'选择要进行的操作。',`<div class="task-list"><button class="btn" style="justify-content:flex-start" data-action="detail" data-card="${e(cardId)}">${icon('sim')}查看完整资料</button><button class="btn" style="justify-content:flex-start" data-action="edit-card" data-card="${e(cardId)}">${icon('edit')}编辑卡片</button><button class="btn" style="justify-content:flex-start" data-action="archive-card" data-card="${e(cardId)}">${icon('archive')}${card.archived ? '恢复到在用卡片' : '归档，不再安排提醒'}</button></div>`,'','small');
}

document.addEventListener('click',async event => {
  if (event.target.classList.contains('overlay-backdrop')) {closeOverlay();return;}
  if (event.target.classList.contains('menu-scrim')) {event.target.remove();el('.sidebar').classList.remove('open');return;}
  const button = event.target.closest('[data-action],[data-nav],[data-filter],[data-layout],[data-month],[data-date],[data-task-filter]');
  if (!button || button.disabled) return;
  if (button.dataset.nav) {event.preventDefault();navigate(button.dataset.nav);return;}
  if (button.dataset.filter) {filter = button.dataset.filter;renderApp();return;}
  if (button.dataset.layout) {layout = button.dataset.layout;renderApp();return;}
  if (button.dataset.taskFilter) {taskFilter = button.dataset.taskFilter;renderApp();return;}
  if (button.dataset.month) {monthDate.setUTCMonth(monthDate.getUTCMonth()+Number(button.dataset.month));selectedDate = null;renderApp();return;}
  if (button.dataset.date) {selectedDate = selectedDate === button.dataset.date ? null : button.dataset.date;renderApp();return;}
  const {action,card:cardId,rule:ruleId,platform:platformId} = button.dataset;
  if (button.type !== 'submit') event.preventDefault();
  const busy = ['refresh','retry-bootstrap','confirm-remove-platform','confirm-archive','archive-card','logout','bind-telegram','check-telegram','verify-email','test-email','test-telegram','confirm-unbind-telegram','confirm-clear-service-config'].includes(action);
  if (busy) button.disabled = true;
  try {
    switch (action) {
      case 'auth-login':authMode = 'login';renderAuth();break;
      case 'auth-register':authMode = 'register';renderAuth();break;
      case 'retry-bootstrap':await bootstrap();break;
      case 'refresh':await refreshWorkspace();closeOverlay(false);renderApp();toast('资料已刷新');break;
      case 'close':closeOverlay();break;
      case 'add-card':cardForm();break;
      case 'add-balance-row': {
        const container = el('#balance-fields');
        const used = [...container.querySelectorAll('[name="balanceCurrency"]')].map(input=>input.value);
        const currency = Object.keys(CURRENCIES).find(code=>!used.includes(code));
        if (!currency) throw new Error('所有支持的币种均已添加');
        container.insertAdjacentHTML('beforeend',balanceRow({currency,amount:''}));container.lastElementChild.querySelector('select').focus();break;
      }
      case 'remove-balance-row':button.closest('.balance-row').remove();break;
      case 'edit-card':cardForm(findCard(cardId));break;
      case 'detail':showDetail(cardId);break;
      case 'card-actions':showCardActions(cardId);break;
      case 'complete':completionForm(cardId,ruleId);break;
      case 'add-rule':ruleForm(cardId);break;
      case 'edit-rule':ruleForm(cardId,ruleId);break;
      case 'add-platform':platformForm(cardId);break;
      case 'choose-platform':platformForm();break;
      case 'remove-platform':removePlatform(cardId,platformId);break;
      case 'confirm-remove-platform': {
        const card = findCard(cardId);
        await mutation('DELETE',`/api/cards/${cardId}/platforms/${platformId}?version=${card.version}`);
        closeOverlay(false);renderApp();savedMessage('已移除平台关联');if (button.dataset.return) showDetail(button.dataset.return);break;
      }
      case 'archive-card': {
        const card = findCard(cardId);
        if (card.archived) {
          await mutation('POST',`/api/cards/${cardId}/archive`,{archived:false,version:card.version});closeOverlay(false);renderApp();savedMessage('卡片已恢复，续期计划重新显示');
        } else openOverlay('归档这张卡片？',e(card.name),'<p class="help-copy">归档后保留卡片资料、平台关联和操作历史，停止安排续期提醒。你可以随时在“已归档”中恢复。</p>',`<button class="btn" data-action="detail" data-card="${e(cardId)}">取消</button><button class="btn btn-primary" data-action="confirm-archive" data-card="${e(cardId)}">确认归档</button>`,'small');
        break;
      }
      case 'confirm-archive':await mutation('POST',`/api/cards/${cardId}/archive`,{archived:true,version:findCard(cardId).version});closeOverlay(false);renderApp();savedMessage('卡片已归档');break;
      case 'toggle-archived':showArchived = !showArchived;renderApp();break;
      case 'calendar-today':monthDate = parseDate(`${today().slice(0,7)}-01`);selectedDate = null;renderApp();break;
      case 'account':showAccount();break;
      case 'logout': {
        await mutation('POST','/api/auth/logout');closeOverlay(false);serverUser = null;data = emptyWorkspace();api.clear();view = 'overview';query = '';filter = 'all';showArchived = false;selectedDate = null;location.hash = '';renderAuth();toast('已退出登录');break;
      }
      case 'bind-telegram':await bindTelegram();break;
      case 'configure-service':notificationConfigForm(button.dataset.channel);break;
      case 'clear-service-config': {
        const channel = button.dataset.channel;
        openOverlay(`清除${channel === 'telegram' ? ' Telegram' : '邮件'}配置？`,'只影响当前账号。',`<p class="help-copy">清除后将停止使用你保存的凭据。${channel === 'telegram' ? 'Telegram 绑定也会解除。' : '已验证的接收邮箱会保留。'}如果服务器提供公共通知服务，将恢复使用公共服务。</p>`,`<button class="btn" data-action="configure-service" data-channel="${channel}">返回配置</button><button class="btn btn-danger" data-action="confirm-clear-service-config" data-channel="${channel}">清除配置</button>`,'small');break;
      }
      case 'confirm-clear-service-config':await mutation('DELETE',`/api/notifications/config/${button.dataset.channel}`);closeOverlay(false);renderApp();toast('本账号的通知服务配置已清除');break;
      case 'check-telegram': {
        const checked = await mutation('POST','/api/notifications/telegram/binding/check',{code:telegramBindingCode});
        if (checked.bindingStatus === 'bound') {closeOverlay(false);renderApp();toast('Telegram 已绑定，请开启提醒并保存设置');}
        else if (checked.bindingStatus === 'expired') toast('绑定指令已失效，请关闭后重新绑定',true);
        else toast('还未收到绑定指令，请在 Bot 中点击“开始”后再检查',true);
        break;
      }
      case 'unbind-telegram':openOverlay('解除 Telegram 绑定？','解除后将停止向这个 Telegram 账号发送提醒。','<p class="help-copy">你的卡片和操作记录仍保留，可以随时重新绑定。</p>','<button class="btn" data-action="close">取消</button><button class="btn btn-danger" data-action="confirm-unbind-telegram">解除绑定</button>','small');break;
      case 'confirm-unbind-telegram':await mutation('DELETE','/api/notifications/telegram/binding');closeOverlay(false);renderApp();toast('Telegram 绑定已解除');break;
      case 'verify-email': {
        if (el('#notify-email').value.trim().toLowerCase() !== data.settings.emailAddress) throw new Error('请先保存新的接收邮箱，再发送验证码');
        await mutation('POST','/api/notifications/email/verify');emailCodeForm();break;
      }
      case 'test-email':case 'test-telegram':await mutation('POST',`/api/notifications/test/${action === 'test-email' ? 'email' : 'telegram'}`);toast('测试提醒已发送，请检查接收消息');break;
      case 'preview':openOverlay('续期提醒预览','这是通知内容预览。可在通知设置中发送测试提醒。',previewMessage(),'<button class="btn btn-primary" data-action="close">关闭预览</button>','small');break;
      case 'reminders':showReminders();break;
      case 'help':showHelp();break;
      case 'export':exportData();break;
      case 'menu':el('.sidebar').classList.add('open');el('#app').insertAdjacentHTML('beforeend','<div class="menu-scrim"></div>');break;
    }
  } catch (error) {reportError(error);}
  finally {if (busy && button.isConnected) button.disabled = false;}
});
document.addEventListener('input',event => {
  if (event.target.id !== 'global-search') return;
  query = event.target.value;
  if (view === 'settings') view = 'cards';
  renderApp(true);
});
document.addEventListener('keydown',event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k' && !el('[role="dialog"]')) {event.preventDefault();el('#global-search')?.focus();}
  if (event.key === 'Escape' && el('.sidebar.open')) {el('.sidebar').classList.remove('open');el('.menu-scrim')?.remove();}
});
document.addEventListener('submit',async event => {
  const form = event.target;
  if (!['auth-form','card-form','rule-form','completion-form','platform-form','settings-form','email-code-form','notification-config-form'].includes(form.id)) return;
  event.preventDefault();
  if (form.dataset.pending === 'true') return;
  form.dataset.pending = 'true';
  const submits = [...form.querySelectorAll('button[type="submit"]'),...document.querySelectorAll(`button[type="submit"][form="${form.id}"]`)];
  for (const button of submits) button.disabled = true;
  const errorBox = form.querySelector('.form-error');if (errorBox) errorBox.hidden = true;
  try {
    const f = form.elements;
    if (form.id === 'auth-form') {
      const payload = {email:f.email.value.trim(),password:f.password.value};
      if (authMode === 'register') payload.name = f.name.value.trim();
      const result = await mutation('POST',`/api/auth/${authMode}`,payload);
      serverUser = result.user;data = result.workspace;query = '';filter = 'all';showArchived = false;monthDate = parseDate(`${today().slice(0,7)}-01`);renderApp();toast(authMode === 'register' ? '账号已创建，添加你的第一张卡片吧' : '已登录你的个人空间');
    } else if (form.id === 'card-form') {
      const existing = findCard(form.dataset.card);
      const activatedAt = f.activatedAt.value;
      validateActivationChange(existing,data.events,activatedAt,today());
      if (!f.name.value.trim() || !f.provider.value.trim()) throw new Error('请填写卡片名称和运营商');
      const card = {name:f.name.value.trim(),provider:f.provider.value.trim(),type:f.type.value,country:f.country.value,phone:f.phone.value.trim(),activatedAt,plan:f.plan.value.trim(),notes:f.notes.value.trim(),balances:readBalances(form)};
      if (!existing) {const rule = readRule(form);if (rule.dueDate < activatedAt) throw new Error('首次到期日期不能早于开通日期');card.rules = [rule];}
      else card.version = Number(form.dataset.version);
      await mutation(existing ? 'PUT' : 'POST',existing ? `/api/cards/${existing.id}` : '/api/cards',card);
      closeOverlay(false);renderApp();savedMessage(existing ? '卡片资料已更新' : '卡片已添加，第一次续期已安排');
    } else if (form.id === 'rule-form') {
      const card = findCard(form.dataset.card), existing = card.rules.find(item => item.id === form.dataset.rule), rule = readRule(form,existing);
      if (rule.dueDate < card.activatedAt) throw new Error('到期日期不能早于卡片开通日期');
      if (existing?.lastCompletedAt && rule.dueDate <= existing.lastCompletedAt) throw new Error('新的到期日期必须晚于上次完成日期');
      if (existing) rule.version = Number(form.dataset.version);
      await mutation(existing ? 'PUT' : 'POST',existing ? `/api/rules/${existing.id}` : `/api/cards/${card.id}/rules`,rule);
      renderApp();savedMessage('续期规则已保存');showDetail(card.id);
    } else if (form.id === 'completion-form') {
      const card = findCard(form.dataset.card);
      // The local calculation is a preview; the API owns the date and the atomic history write.
      completeRenewal(card,form.dataset.rule,f.completedAt.value,today());
      const cost = readCost(form), balanceAction = f.updateBalance.checked ? form.dataset.balanceAction : 'none';
      if (balanceAction !== 'none') balanceAfter(card.balances || [],cost,balanceAction);
      await mutation('POST',`/api/rules/${form.dataset.rule}/completions`,{completedAt:f.completedAt.value,note:f.note.value.trim(),requestId:form.dataset.requestId,version:Number(form.dataset.version),cost,balanceAction,cardVersion:Number(form.dataset.cardVersion)});
      const next = findCard(card.id).rules.find(rule => rule.id === form.dataset.rule).dueDate;
      closeOverlay(false);renderApp();savedMessage(`已记录完成，下次续期 ${formatDate(next)}`);
    } else if (form.id === 'platform-form') {
      const card = findCard(form.dataset.card || f.cardId.value);
      const name = f.name.value.trim();if (!name) throw new Error('请填写平台名称');
      await mutation('POST',`/api/cards/${card.id}/platforms`,{name,account:f.account.value.trim(),purpose:f.purpose.value.trim(),version:card.version});
      closeOverlay(false);renderApp();savedMessage('平台关联已保存');if (detailReturn) showDetail(card.id);
    } else if (form.id === 'settings-form') {
      const emailAddress = f.emailAddress.value.trim();
      if (f.email.checked && !emailAddress) throw new Error('启用邮箱提醒时，请填写接收邮箱');
      await mutation('PUT','/api/settings',{telegram:f.telegram.checked,email:f.email.checked,emailAddress,timezone:f.timezone.value,time:f.time.value,offsets:Array.from(form.querySelectorAll('input[name="offset"]:checked')).map(input => Number(input.value)),overdue:f.overdue.checked});
      selectedDate = null;monthDate = parseDate(`${today().slice(0,7)}-01`);renderApp();savedMessage('通知设置已保存');
    } else if (form.id === 'notification-config-form') {
      const channel = form.dataset.channel;
      const payload = channel === 'telegram' ? {token:f.token.value.trim()} : {host:f.host.value.trim(),port:Number(f.port.value),mode:f.mode.value,user:f.user.value.trim(),password:f.password.value,from:f.sender.value.trim()};
      const feedback = form.querySelector('.config-feedback');feedback.hidden = true;
      await mutation('PUT',`/api/notifications/config/${channel}`,payload);
      renderApp();
      const secret = channel === 'telegram' ? f.token : f.password;
      secret.value = '';secret.required = false;secret.placeholder = '已保存，留空保留原值';
      if (event.submitter?.value === 'check') {
        feedback.textContent = '配置已保存，正在检查连接…';feedback.hidden = false;
        try {
          const checked = await mutation('POST',`/api/notifications/config/${channel}/check`);
          feedback.textContent = channel === 'telegram' ? `配置已保存，已连接 @${checked.botUsername}。下一步绑定 Telegram。` : '配置已保存，SMTP 连接与认证通过。下一步验证接收邮箱。';
          feedback.scrollIntoView({block:'nearest'});
        } catch (error) {feedback.hidden = true;error.message = `配置已保存。${error.message}`;throw error;}
      } else {closeOverlay(false);toast(channel === 'telegram' ? 'Telegram 配置已保存，可以绑定账号了' : '邮件配置已保存，可以验证接收邮箱了');}
    } else if (form.id === 'email-code-form') {
      await mutation('POST','/api/notifications/email/confirm',{code:f.code.value});closeOverlay(false);renderApp();toast('邮箱已验证，请开启提醒并保存设置');
    }
  } catch (error) {reportError(error,form);}
  finally {form.dataset.pending = 'false';for (const button of submits) if (button.isConnected) button.disabled = false;}
});

if (NAV.some(item => `#${item.id}` === location.hash)) view = location.hash.slice(1);
window.addEventListener('hashchange',() => {const next = location.hash.slice(1);if (NAV.some(item => item.id === next) && next !== view) {view = next;closeOverlay(false);query = '';renderApp();}});
bootstrap();
