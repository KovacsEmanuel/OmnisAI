#!/usr/bin/env python3
"""Real Reticle MCP smoke against an inert HTTP fixture in a network namespace.

Run via run_probe.py. Only loopback is available. Uses existing Python
Playwright + an existing Chromium headless shell, not a new browser install.
Upstream tool text is
recorded as data; no suggested commands/feedback/update actions are executed.
"""
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from playwright.async_api import async_playwright
from verdicts import network_controls_passed

ROOT = Path(__file__).resolve().parent
BROWSER = os.environ["RETICLE_PROBE_BROWSER"]
RAW = ROOT / 'raw'
SID = 'omnis-inert-fixture'
URL = 'http://127.0.0.1:14401/'
TOKEN = 'probe-local-only-not-a-real-credential'
CLI = ROOT / 'node_modules/@reticlehq/server/bin/reticle.js'
REQUESTS = []
BROWSER_EVENTS = []
CHILDREN = []

# Refuse to run if the namespace has a non-loopback interface. No external
# connection is attempted to test this property.
# sysfs can still reflect the original mount's network namespace. if_nameindex
# queries this process's namespace, as does the recorded `ip address` netlink query.
interfaces = sorted(name for _, name in socket.if_nameindex())
if interfaces != ['lo']:
    raise SystemExit(f'Refusing: run under isolated net namespace; got {interfaces}')
ENV = {
    'PATH': '/usr/local/bin:/usr/bin:/bin',
    'HOME': str(ROOT / 'home'), 'TMPDIR': str(ROOT / 'tmp'),
    'XDG_CONFIG_HOME': str(ROOT / 'xdg-config'), 'XDG_CACHE_HOME': str(ROOT / 'xdg-cache'),
    'XDG_DATA_HOME': str(ROOT / 'xdg-data'),
    'RETICLE_STATE_DIR': str(ROOT / 'home/.reticle'),
    'RETICLE_PAIRING_TOKEN_DIR': str(ROOT / 'home/.reticle'),
    'RETICLE_TOKEN': TOKEN, 'RETICLE_HOST': '127.0.0.1', 'RETICLE_PORT': '14400',
    'RETICLE_TELEMETRY': '0', 'DO_NOT_TRACK': '1', 'CI': '1',
    'RETICLE_MAX_CONTEXTS': '1',
    # Empty credentials explicitly prevent any inherited or .env fallback.
    'ANTHROPIC_API_KEY': '', 'OPENAI_API_KEY': '', 'JEV_API_KEY': '',
    'RETICLE_API_KEY': '', 'RETICLE_CLOUD_KEY': '', 'RETICLE_CLOUD_URL': '',
    'RETICLE_LICENSE_KEY': '',
    'npm_config_cache': str(ROOT / 'npm-cache'),
    'npm_config_update_notifier': 'false', 'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD': '1',
}
os.environ.clear()
os.environ.update(ENV)
os.chdir(ROOT / 'fixture')
for path in ('raw', 'home/.reticle', 'tmp', 'xdg-config', 'xdg-cache', 'xdg-data'):
    (ROOT / path).mkdir(parents=True, exist_ok=True)

def save(name, data):
    (RAW / name).write_text(json.dumps(data, indent=2) + '\n')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.path = '/fixture/index.html'
        if self.path == '/favicon.ico':
            self.send_response(204); self.end_headers(); return
        super().do_GET()
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        REQUESTS.append({'method': 'POST', 'path': self.path, 'body': body.decode()})
        if self.path not in ('/api/save', '/api/ok'):
            self.send_error(404); return
        status = 200 if self.path == '/api/ok' else 500
        payload = json.dumps({'ok': status == 200, 'fixture': 'synthetic network control'}).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers(); self.wfile.write(payload)
    def log_message(self, format, *args):
        with (RAW / 'fixture-access.log').open('a') as f:
            f.write(format % args + '\n')

async def spawn(*args, name, env=ENV):
    err = (RAW / f'{name}.stderr').open('w')
    p = await asyncio.create_subprocess_exec(*args, cwd=ROOT / 'fixture', env=env,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=err,
        limit=1024*1024)
    CHILDREN.append((name, p, err))
    return p

async def cli(args, name):
    p = await spawn('node', str(CLI), *args, name=name)
    out, _ = await asyncio.wait_for(p.communicate(), 30)
    (RAW / f'{name}.stdout').write_bytes(out)
    save(f'{name}.result.json', {'argv': ['node', str(CLI)] + args, 'exit_code': p.returncode})
    return p.returncode, out.decode()

class Rpc:
    def __init__(self, process, prefix='mcp'):
        self.process = process; self.prefix = prefix; self.seq = 0
    async def send(self, method, params=None, notification=False) -> dict:
        request = {'jsonrpc': '2.0', 'method': method}
        if params is not None: request['params'] = params
        if not notification:
            self.seq += 1; request['id'] = self.seq
        with (RAW / f'{self.prefix}-requests.jsonl').open('a') as f:
            f.write(json.dumps(request) + '\n')
        self.process.stdin.write((json.dumps(request) + '\n').encode())
        await self.process.stdin.drain()
        if notification: return {}
        while True:
            line = await asyncio.wait_for(self.process.stdout.readline(), 45)
            if not line: raise RuntimeError(f'MCP closed: exit={self.process.returncode}')
            with (RAW / f'{self.prefix}-responses.jsonl').open('ab') as f:
                f.write(line)
            response = json.loads(line)
            if response.get('id') != self.seq: continue
            if 'error' in response: raise RuntimeError(response['error'])
            result = response['result']
            if not isinstance(result, dict):
                raise RuntimeError('MCP result must be an object')
            return result
    async def tool(self, name, args, label) -> dict:
        r = await self.send('tools/call', {'name': name, 'arguments': args})
        save(label + '.json', r)
        if r.get('isError'): raise RuntimeError(f'{label}: {r}')
        if 'structuredContent' in r: return r['structuredContent']
        for item in r.get('content', []):
            if item.get('type') == 'text':
                try: return json.loads(item['text'])
                except json.JSONDecodeError: pass
        return r

async def wait_port(port):
    for _ in range(150):
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.close(); await writer.wait_closed(); return
        except OSError: await asyncio.sleep(0.1)
    raise RuntimeError(f'No listener on {port}')

async def mcp_client(prefix='mcp', env=ENV):
    p = await spawn('node', str(CLI), 'mcp', '--port', '14400', '--headless', name=prefix, env=env)
    rpc = Rpc(p, prefix)
    init = await rpc.send('initialize', {'protocolVersion':'2024-11-05',
        'capabilities': {}, 'clientInfo': {'name':'inert-local-audit', 'version':'1.0.0'}})
    save(prefix + '-initialize.json', init)
    await rpc.send('notifications/initialized', notification=True)
    return rpc

async def main():
    result = {'status':'running', 'network_interfaces': interfaces, 'fixture_url':URL,
              'runtime_env': {k:v for k,v in ENV.items() if k != 'RETICLE_TOKEN'}}
    browser = None; server = None; httpd = None
    try:
        save('network-namespace.json', {
            'interfaces':interfaces,
            'ip_address':subprocess.check_output(['ip','-brief','address'], text=True),
            'routes':subprocess.check_output(['ip','route','show'], text=True),
        })
        for args, name in [(['version'],'cli-version'), (['telemetry','status'],'cli-telemetry'), (['--help'],'cli-help')]:
            await cli(args, name)
        httpd = ThreadingHTTPServer(('127.0.0.1', 14401), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        server = await spawn('node', str(ROOT / 'server-entry.mjs'), name='server')
        await wait_port(14400)
        rpc = await mcp_client()
        tools = await rpc.send('tools/list', {})
        save('mcp-tools.json', tools)
        result['default_tools'] = [t['name'] for t in tools['tools']]
        result['default_tool_count'] = len(result['default_tools'])
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=BROWSER, headless=True,
                env={**ENV}, args=['--disable-background-networking','--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding'])
            context = await browser.new_context()
            page = await context.new_page()
            page.on('pageerror', lambda e: BROWSER_EVENTS.append({'type':'pageerror','message':str(e)}))
            page.on('console', lambda msg: BROWSER_EVENTS.append({'type':'console','level':msg.type,'message':msg.text}))
            page.on('requestfailed', lambda req: BROWSER_EVENTS.append({'type':'requestfailed','url':req.url,'failure':req.failure}))
            await page.goto(URL, wait_until='load')
            await page.wait_for_function('window.fixtureReticle?.connected === true', timeout=20000)
            result['browser_version'] = browser.version
            result['sdk_connected'] = True
            await rpc.tool('reticle_session', {'action':'list'}, 'session-list')
            await rpc.tool('reticle_look', {'sessionId':SID, 'action':'page'}, 'look-page')
            await rpc.tool('reticle_look', {'sessionId':SID, 'action':'state'}, 'look-state-before')
            result['positive'] = await rpc.tool('reticle_act_and_wait', {
                'sessionId':SID, 'action':'click', 'target':{'testid':'increment'},
                'until':{'kind':'signal','name':'fixture:incremented','dataMatches':{'count':1}},
                'timeout_ms':4000}, 'positive-increment')
            result['count_after'] = await page.locator('#count').inner_text()
            await rpc.tool('reticle_look', {'sessionId':SID, 'action':'state'}, 'look-state-after')
            result['assert_existing_session'] = await rpc.tool('reticle_assert', {
                'sessionId':SID, 'predicate':{'kind':'state','store':'fixture','path':'count','equals':1}},
                'assert-existing-session')
            result['positive_network'] = await rpc.tool('reticle_act_and_wait', {
                'sessionId':SID, 'action':'click', 'target':{'testid':'healthy-request'},
                'until':{'kind':'net','method':'POST','urlContains':'/api/ok','status':200},
                'timeout_ms':4000}, 'positive-network')
            result['negative'] = await rpc.tool('reticle_act_and_wait', {
                'sessionId':SID, 'action':'click', 'target':{'testid':'failed-save'},
                'until':{'kind':'net','method':'POST','urlContains':'/api/save','status':200},
                'timeout_ms':3000}, 'negative-failed-save')
            result['dishonest_ui'] = await page.locator('#save-status').inner_text()
            result['network_observation'] = await rpc.tool('reticle_observe', {'sessionId':SID,'action':'network'}, 'observe-network')
            await rpc.tool('reticle_observe', {'sessionId':SID,'action':'console'}, 'observe-console')
            await page.screenshot(path=str(RAW / 'fixture.png'))
            # The separately reproduced CLI reload path is not the accepted MCP
            # workflow. Keep its failure evidence in verification/cli-reload-failure.json.
            await rpc.tool('reticle_session', {'sessionId':SID,'action':'yield'}, 'session-yield')
            await context.close()
            await browser.close(); browser = None
        result['checks'] = {
            'increment_visible':result['count_after']=='Count: 1',
            'positive_verdict_yes':result['positive'].get('verified')=='yes',
            'state_assertion_yes':result['assert_existing_session'].get('verified')=='yes',
            'negative_verdict_no':result['negative'].get('verified')=='no',
            'network_capture_controls':network_controls_passed(result['positive_network'], result['negative'], result['network_observation']),
            'inert_failed_request_reached_fixture':any(r['method']=='POST' and r['path']=='/api/save' for r in REQUESTS),
            'failure_hidden_by_screen':result['dishonest_ui']=='Saved successfully',
            'no_browser_js_exceptions':not any(e['type']=='pageerror' for e in BROWSER_EVENTS),
        }
        result['status'] = 'pass' if all(result['checks'].values()) else 'partial'
    except Exception as e:
        result['status']='blocked'
        result['error']=str(e)
        result['traceback']=traceback.format_exc()
    finally:
        if browser is not None:
            try: await browser.close()
            except Exception: pass
        for name, p, err in reversed(CHILDREN):
            if p.returncode is None:
                p.terminate()
                try: await asyncio.wait_for(p.wait(), 10)
                except asyncio.TimeoutError:
                    p.kill(); await p.wait()
            err.close()
            if name=='server':
                (RAW / 'server.stdout').write_bytes(await p.stdout.read())
        if httpd:
            httpd.shutdown(); httpd.server_close()
        result['child_exits'] = {name:p.returncode for name,p,_ in CHILDREN}
        result['listeners_after_cleanup']={}
        for port in (14400,14401):
            s=socket.socket(); s.settimeout(1)
            result['listeners_after_cleanup'][str(port)] = s.connect_ex(('127.0.0.1',port)) == 0
            s.close()
        if any(result['listeners_after_cleanup'].values()):
            result['status'] = 'cleanup_failed'
        save('browser-events.json', BROWSER_EVENTS)
        save('fixture-posts.json', REQUESTS)
        save('smoke-result.json', result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('positive','positive_network','negative','network_observation','runtime_env','traceback')},indent=2))
    return 0 if result['status']=='pass' else 1

if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
