import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {allowedResponse,allowedFailure} from './observer.mjs';
const d=JSON.parse(readFileSync(new URL('../browser-before.json',import.meta.url)));
const id=d.rows.find(r=>r.id==='PERSIST-01').evidence.id;
let count=0; function check(v){assert(v);count++;}
const cas=d.responses.find(r=>r.status===409);check(allowedResponse(cas,id));
for(const m of [{status:500},{status:403},{method:'POST'},{path:'/api/v1/engagements/other'},{scenario:'FORM-01'}])check(!allowedResponse({...cas,...m},id));
// Original requestfailed records omitted method; reconstruction is source-derived,
// not measured request-method evidence. The fresh driver now records the method.
for(const r of d.failed){const method=r.path==='/api/logout'?'POST':'GET';check(allowedFailure({...r,method},'before',d.responses));}
const nav={method:'GET',path:'/health/ready',error:'net::ERR_ABORTED',fault:false,scenario:'NAV-01'};
for(const m of [{method:'PUT'},{path:'/api/unexpected'},{error:'net::ERR_FAILED'},{error:'net::ERR_CONNECTION_REFUSED'},{scenario:'FORM-06'}])check(!allowedFailure({...nav,...m},'before',d.responses));
const logout={method:'POST',path:'/api/logout',error:'net::ERR_ABORTED',fault:false,scenario:'AUTH-before-logout'};
check(allowedFailure(logout,'before',d.responses));check(!allowedFailure(logout,'before',[]));check(!allowedFailure(logout,'before',d.responses.filter(r=>r.status!==204)));check(!allowedFailure(logout,'before',d.responses.filter(r=>r.status!==401)));
const report={status:'PASS_SCOPED_OBSERVER_ONLY',assertions:count,source:'../browser-before.json',reason:'Observed intended CAS409 and lifecycle ERR_ABORTED wrongly rejected by original aggregate observer; original FAIL retained. Exact methods/path/scenario and logout204+401 constrain exceptions. No product edit.'};writeFileSync(new URL('observer-controls.json',import.meta.url),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
