import assert from 'node:assert/strict';
import {allowedResponse,allowedFailure,bootControls,observeBrowser} from './observer.mjs';
import {viewportProbe} from './viewport.mjs';
import {createHash,randomBytes,randomUUID} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import {writeSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname} from 'node:path';
import {createConnection} from 'node:net';
import {chromium,expect} from '/home/kali/OmnisAI/web/node_modules/@playwright/test/index.mjs';
const root=dirname(fileURLToPath(import.meta.url)),origin=process.env.QA_ORIGIN,stage=process.argv[2];
assert(['before','after','supplement'].includes(stage));
const cfg=JSON.parse(await readFile(`${root}/dispatch.json`,'utf8'));
assert(cfg.acceptance.launch_authorized===true && cfg.acceptance.verdict==='APPROVED_SCOPED');
const check=expect.configure({timeout:8000});
const rows=[],captures=[],responses=[],requests=[],failed=[],consoles=[],pageErrors=[],external=[],secrets=[];
let fault=false,current='BOOT',browser,context,page,id,latest,observer;
function remember(s){if(!secrets.includes(s)){secrets.push(s);writeSync(Number(process.env.QA_MARKER_FD),`SECRET ${s}\n`);}}
function record(id,action,expected,evidence={},verdict='PASS'){rows.push({id,action,expected,wait:'Playwright condition <=8s; HTTP <=10s',evidence,verdict,exclusions:[]});}
async function scenario(id,action,expected,fn){current=id;const evidence=await fn();record(id,action,expected,evidence??{});}
async function shot(name){const path=`${root}/captures/${stage}-${name}.png`;await page.screenshot({path,fullPage:true});captures.push({path,inspection:'PENDING'});return path;}
async function control(command){const capability=await readFile(`${root}/ipc/control.cap`,'utf8');remember(capability);return await new Promise((resolve,reject)=>{let data='';const s=createConnection(`${root}/ipc/control.sock`);const timer=setTimeout(()=>{s.destroy();reject(Error('Control deadline'));},5000);s.on('connect',()=>s.write(JSON.stringify({version:1,capability,command})+'\n'));s.on('data',c=>{data+=c;if(data.length>16384){clearTimeout(timer);s.destroy();reject(Error('Control bound'));}else if(data.endsWith('\n')){clearTimeout(timer);s.end();const r=JSON.parse(data);r.ok?resolve(r):reject(Error('Control denied'));}});s.on('error',()=>{clearTimeout(timer);reject(Error('Control unavailable'));});});}
async function pair(){const status=(await control({op:'status'})).status;const code=randomBytes(24).toString('base64url');remember(code);await control({op:'pairing',instance_id:status.instance_id,issuance_id:randomUUID(),digest:createHash('sha256').update(code).digest('hex')});await page.getByLabel('Pairing code').fill(code);await page.getByRole('button',{name:'Pair browser'}).click();await check(page.getByLabel('Pairing code')).toHaveCount(0);const cookie=(await context.cookies()).find(c=>c.name==='omnis_session');assert(cookie?.httpOnly&&cookie.sameSite==='Strict');remember(cookie.value);const session=await page.evaluate(async()=>await (await fetch('/api/session',{signal:AbortSignal.timeout(10000)})).json());remember(session.csrf_token);return status;}
async function getDraft(){return await page.evaluate(async id=>{const r=await fetch(`/api/v1/engagements/${id}`,{signal:AbortSignal.timeout(10000)});return {status:r.status,body:await r.json()};},id);}
async function step(n){await page.getByRole('button',{name:new RegExp(`^${n}\\. `)}).click();}
async function save(rev){await page.getByRole('button',{name:'Save draft',exact:true}).click();await check(page.getByText(`Saved · revision ${rev}`,{exact:true})).toBeVisible();}
async function invalid(label,value,status=422){await page.getByLabel(label,{exact:true}).fill(value);let response;
 if(status) [response]=await Promise.all([page.waitForResponse(r=>['POST','PUT'].includes(r.request().method())&&r.url().includes('/api/v1/engagements')),page.getByRole('button',{name:'Save draft',exact:true}).click()]);else await page.getByRole('button',{name:'Save draft',exact:true}).click();
 if(status)assert.equal(response.status(),status);await check(page.getByLabel(label,{exact:true})).toHaveAttribute('aria-invalid','true');return {status:response?.status()??'LOCAL_VALIDATION'};}
try{
 browser=await chromium.launch({executablePath:cfg.browser_executable,timeout:20000,args:['--disable-background-networking','--disable-component-update','--disable-sync']});context=await browser.newContext({viewport:{width:390,height:900},reducedMotion:'reduce',serviceWorkers:'block'});context.setDefaultTimeout(8000);context.setDefaultNavigationTimeout(10000);
 await context.route('**/*',async r=>{if(new URL(r.request().url()).origin!==origin){external.push(new URL(r.request().url()).origin);await r.abort();}else await r.continue();});
 observer=observeBrowser(context,{requests,responses,failed,consoles,pageErrors},()=>current);
 page=await context.newPage();page.setDefaultTimeout(8000);await observer.action('BOOT_NAVIGATION','initial root and pairing form',async()=>{await page.goto(origin);await check(page.getByLabel('Pairing code')).toBeVisible();});const initial=(await control({op:'status'})).status;if(!initial.admission_open)await control({op:'open',instance_id:initial.instance_id,command_id:randomUUID(),expected_generation:initial.generation});const status=await observer.action('BOOT_AUTH','fresh browser pairing',pair);

 current='OBS-after';
 await scenario('OBS-after','After API restart, pair fresh browser; direct Setup GET, reload and identical retained limit-draft readback; inspect BOOT outcomes','Same revision3/digest/full payload; readiness200+pairing200+session200 on this fresh browser; no unexpected errors',async()=>{
  const previous=JSON.parse(await readFile(`${root}/supplement-retained.json`,'utf8'));id=previous.engagement_id;
  await observer.action('NAVIGATION','direct retained Setup route after restart',async()=>{await page.goto(`${origin}/engagements/${id}/setup`);await check(page.getByLabel('Engagement name')).toHaveValue(previous.payload.name);});
  const restored=await getDraft();assert.equal(restored.status,200);assert.deepEqual(restored.body,previous);
  await observer.action('NAVIGATION','reload retained Setup after restart',async()=>{await page.reload();await check(page.getByLabel('Obiectiv / instrucțiuni pentru Brain')).toHaveValue(previous.payload.objective_text);});
  assert.deepEqual((await getDraft()).body,previous);assert.equal(previous.revision,3);assert.equal(previous.payload.name.length,128);assert.equal(previous.payload.objective_text.length,8192);
  assert(await page.getByRole('button',{name:'Start assessment'}).isDisabled());
  const path=`${root}/captures/after-restart-viewport.png`;await page.screenshot({path,fullPage:false});captures.push({path,inspection:'PENDING',kind:'viewport'});
  const storage=await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length,cookie:document.cookie}));assert.deepEqual(storage,{local:0,session:0,cookie:''});
  const material=JSON.stringify({requests,consoles,pageErrors,html:await page.content()});for(const secret of secrets)assert(!material.includes(secret));
  assert(bootControls(responses,observer.browserId),'Missing same-browser readiness/pair/session controls');
  const unexpected=responses.filter(r=>!allowedResponse(r,id));assert.deepEqual(unexpected,[]);assert(failed.every(r=>allowedFailure(r,stage,responses)),'Unexpected failed request');assert.deepEqual(pageErrors,[]);assert.deepEqual(external,[]);
  const bad=consoles.filter(c=>['error','warning'].includes(c.type) && !(c.type==='error' && /^Failed to load resource:/.test(c.text) && responses.some(r=>r.scenario===c.scenario && r.status>=400 && allowedResponse(r,id) && c.text.includes(String(r.status)))));assert.deepEqual(bad,[]);
  return {id,revision:previous.revision,digest:previous.digest,payload_exact:true,fresh_browser:true,browser_id:observer.browserId,boot_controls:true,responses:responses.length,unexpected:unexpected.length,navigation_cancellations:failed,storage,capture:path,assessment_disabled:true};
 });
 }catch(e){record(current,'Execute live scenario','All assertions hold',{error_name:e.name,message:'Assertion/driver failure; private stage log and captured state retained'},'FAIL');if(page){try{await shot('failure');await writeFile(`${root}/${stage}-failure-dom.txt`,await page.locator('body').innerText());}catch{}}process.exitCode=1;
}finally{let browserClosed=false;try{if(context)await context.close();if(browser){await browser.close();browserClosed=true;}}catch{process.exitCode=1;}await writeFile(`${root}/browser-${stage}.json`,JSON.stringify({stage,browser_id:observer?.browserId,actions:observer?.actions,rows,captures,requests,responses,failed,consoles,pageErrors,external,browser_closed:browserClosed,totals:rows.reduce((a,r)=>(a[r.verdict]=(a[r.verdict]??0)+1,a),{})},null,2));}
