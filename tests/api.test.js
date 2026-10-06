import assert from 'node:assert/strict';
let API;
try { ({API}=await import('../api.js')); } catch {}
assert.ok(API,'Same-origin authenticated API client must exist');

const requests=[];
const transport=async (path,options) => {
  requests.push({path,options});
  if (path==='/api/auth/login') return {ok:true,status:200,json:async()=>({csrfToken:'session-csrf',user:{name:'Alice'}})};
  if (path==='/api/failure') return {ok:false,status:409,json:async()=>({detail:'资料已更新'})};
  if (path==='/api/validation') return {ok:false,status:422,json:async()=>({detail:[{msg:'Value error, 请输入有效日期'}]})};
  return {ok:true,status:200,json:async()=>({workspace:{cards:[{name:'Persisted SIM'}]}})};
};
const client=new API(transport);
await client.request('POST','/api/auth/login',{email:'alice@example.com',password:' password '});
const result=await client.request('POST','/api/cards',{name:'Persisted SIM'});
assert.equal(requests[0].options.credentials,'same-origin');
assert.equal(JSON.parse(requests[0].options.body).password,' password ');
assert.equal(requests[1].options.headers['X-CSRF-Token'],'session-csrf');
assert.equal(result.workspace.cards[0].name,'Persisted SIM');
await assert.rejects(client.request('GET','/api/failure'),error=>error.status===409 && error.message==='资料已更新');
await assert.rejects(client.request('GET','/api/validation'),error=>error.message==='请输入有效日期');
const offline=new API(async()=>{throw new TypeError('Failed to fetch')});
await assert.rejects(offline.request('GET','/api/workspace'),/无法连接服务器/);
client.clear();
await client.request('GET','/api/workspace');
assert.equal(requests.at(-1).options.headers['X-CSRF-Token'],undefined);
let finishOldRead, finishOldError;
const deferred = new API((path) => {
  if(path==='/api/old-workspace') return new Promise(resolve=>{finishOldRead=resolve;});
  if(path==='/api/old-error') return new Promise(resolve=>{finishOldError=resolve;});
  return Promise.resolve({ok:true,status:200,json:async()=>({csrfToken:'bob-csrf',user:{id:'bob'},workspace:{cards:[]}})});
});
const oldRead=deferred.request('GET','/api/old-workspace');
const oldError=deferred.request('GET','/api/old-error');
deferred.clear();
const bob=await deferred.request('POST','/api/auth/login',{email:'bob@example.com',password:'long-password'});
const rejectOld=assert.rejects(oldRead,error=>error.name==='StaleResponse');
const rejectError=assert.rejects(oldError,error=>error.name==='StaleResponse');
finishOldRead({ok:true,status:200,json:async()=>({csrfToken:'alice-csrf',workspace:{cards:[{name:'Alice private SIM'}]}})});
finishOldError({ok:false,status:401,json:async()=>({detail:'请先登录'})});
await rejectOld;await rejectError;
assert.equal(bob.user.id,'bob');
assert.equal(deferred.csrf,'bob-csrf');
deferred.clear();
assert.throws(()=>deferred.assertCurrent(bob),error=>error.name==='StaleResponse');
console.log('API client: 12 checks passed');
