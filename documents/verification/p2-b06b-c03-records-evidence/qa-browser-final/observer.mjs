// Scratch-only bounded derivative; old reports are not rewritten.
import {randomUUID} from 'node:crypto';
import {performance} from 'node:perf_hooks';
export function allowedResponse(r, id) {
 return r.status < 400 ||
  (r.status === 422 && ['POST','PUT'].includes(r.method) && ['/api/v1/engagements',`/api/v1/engagements/${id}`].includes(r.path) && ['BOUND-01','BOUND-02','BOUND-03','BOUND-04'].includes(r.scenario)) ||
  (r.status === 401 && r.method === 'GET' && r.path === '/api/session' && r.scenario === 'BOOT');
}
export function bootControls(responses,browserId) {
 return [['GET','/health/ready'],['POST','/api/pairing'],['GET','/api/session']].every(([method,path])=>responses.some(r=>r.browser_id===browserId && r.request_id && r.method===method && r.path===path && r.status===200));
}
export function allowedFailure(r, stage, responses) {
 if(!['supplement','after'].includes(stage) || r.fault || r.method!=='GET' || r.path!=='/health/ready' || r.error!=='net::ERR_ABORTED')return false;
 if(!['BOOT','VISUAL-01','OBS-after'].includes(r.scenario))return false;
 if(!['BOOT_NAVIGATION','BOOT_AUTH','NAVIGATION'].includes(r.action_phase) || !r.action_id || !r.request_id || !r.browser_id)return false;
 if(!Number.isFinite(r.action_started_ms) || !Number.isFinite(r.failed_ms) || r.failed_ms<r.action_started_ms || r.failed_ms-r.action_started_ms>10000)return false;
 return bootControls(responses,r.browser_id);
}
// Every request retains its original identity/start attribution. Cancellation
// also records the active explicit navigation/auth action at failure time.
export function observeBrowser(context,state,getScenario) {
 const browserId=randomUUID(),identities=new WeakMap(),actions=[];
 let serial=0,active=null;
 function identity(r){let v=identities.get(r);if(!v){v={browser_id:browserId,request_id:`${browserId}:${++serial}`,method:r.method(),path:new URL(r.url()).pathname,started_ms:performance.now(),start_scenario:getScenario(),start_action_id:active?.id??null};identities.set(r,v);}return v;}
 const extra=()=>({scenario:getScenario(),fault:false,action_id:active?.id??null,action_phase:active?.phase??'IDLE',action_started_ms:active?.started_ms??null});
 context.on('request',r=>state.requests.push({...identity(r),...extra()}));
 context.on('response',r=>state.responses.push({...identity(r.request()),...extra(),status:r.status(),received_ms:performance.now()}));
 context.on('requestfailed',r=>state.failed.push({...identity(r),...extra(),error:r.failure()?.errorText,failed_ms:performance.now()}));
 context.on('page',p=>{p.on('pageerror',e=>state.pageErrors.push(e.message));p.on('console',m=>state.consoles.push({type:m.type(),text:m.text(),...extra()}));});
 async function action(phase,label,fn){if(active)throw Error('Nested observation action');const a={id:randomUUID(),phase,label,scenario:getScenario(),started_ms:performance.now()};active=a;actions.push(a);try{return await fn();}finally{a.finished_ms=performance.now();active=null;}}
 return {browserId,actions,action};
}
