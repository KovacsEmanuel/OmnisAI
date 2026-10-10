// Scratch-only classification of observed browser cancellation outcomes.
export function allowedResponse(r, id) {
 return r.status < 400 ||
  (r.status === 422 && r.path.startsWith('/api/v1/engagements')) ||
  (r.status === 401 && ['/api/session','/api/pairing'].includes(r.path)) ||
  (r.status === 404 && r.path === '/unknown-qa-route') ||
  (r.status === 409 && r.method === 'PUT' && r.path === `/api/v1/engagements/${id}` && r.scenario === 'CAS-01');
}
export function allowedFailure(r, stage, responses) {
 if (r.fault && r.error === 'net::ERR_FAILED' && ['STATE-02','STATE-03'].includes(r.scenario)) return true;
 if (r.error !== 'net::ERR_ABORTED') return false;
 const transitions = ['NAV-01','STATE-01','NAV-02','PERSIST-02','CAS-01','NAV-03','PERSIST-03','VISUAL-01',`KEY-${stage}-1280`,`KEY-${stage}-390`,`AUTH-${stage}-logout`];
 if (r.method === 'GET' && r.path === '/health/ready' && transitions.includes(r.scenario)) return true;
 if (r.method === 'GET' && r.path === '/api/v1/dashboard' && r.scenario === 'FORM-01') return true;
 if (r.scenario !== `AUTH-${stage}-logout`) return false;
 if (r.method === 'GET' && r.path === '/api/instance') return true;
 return r.method === 'POST' && r.path === '/api/logout' &&
  responses.some(x => x.method === 'POST' && x.path === r.path && x.status === 204 && x.scenario === r.scenario) &&
  responses.some(x => x.path === '/api/session' && x.status === 401 && x.scenario === r.scenario);
}
