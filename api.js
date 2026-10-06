export class ApiError extends Error {
  constructor(message,status=0,generation) {super(message);this.status=status;this.sessionGeneration=generation;}
}
export class StaleResponse extends Error {
  constructor() {super('账号已切换，忽略旧请求');this.name='StaleResponse';}
}

export class API {
  constructor(transport=globalThis.fetch.bind(globalThis)) {
    this.transport=transport;
    this.csrf='';
    this.generation=0;
  }
  clear() {this.csrf='';this.generation++;}
  assertCurrent(result) {if(result._sessionGeneration!==this.generation) throw new StaleResponse();}
  async request(method,path,payload) {
    const generation=this.generation;
    const current=()=>{if(generation!==this.generation) throw new StaleResponse();};
    const headers={Accept:'application/json'};
    if (payload !== undefined) headers['Content-Type']='application/json';
    if (!['GET','HEAD'].includes(method) && this.csrf) headers['X-CSRF-Token']=this.csrf;
    let response;
    try {
      response=await this.transport(path,{method,headers,credentials:'same-origin',...(payload!==undefined ? {body:JSON.stringify(payload)} : {})});
    } catch {
      current();
      throw new ApiError('无法连接服务器，请检查网络后重试',0,generation);
    }
    let result;
    try {result=await response.json();} catch {current();throw new ApiError('服务器响应异常，请稍后重试',response.status,generation);}
    current();
    if (!response.ok) {
      const detail=result.detail;
      const message=typeof detail==='string' ? detail : Array.isArray(detail) ? detail[0]?.msg?.replace(/^Value error, /,'') : '';
      throw new ApiError(message || '操作未完成，请稍后重试',response.status,generation);
    }
    if (path==='/api/auth/login' || path==='/api/auth/register') this.generation++;
    if (result.csrfToken) this.csrf=result.csrfToken;
    Object.defineProperty(result,'_sessionGeneration',{value:this.generation});
    return result;
  }
}

export const api=new API();
