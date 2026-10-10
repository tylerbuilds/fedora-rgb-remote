#!/usr/bin/env python3
import http.server,json,os,re,secrets,subprocess,threading,time,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HOST=os.environ.get('RGB_HOST','127.0.0.1'); PORT=int(os.environ.get('RGB_PORT','8769'))
import ipaddress,hashlib
_bind=ipaddress.ip_address(HOST)
if not (_bind.is_loopback or (_bind.version==4 and _bind in ipaddress.ip_network('100.64.0.0/10'))):
    raise ValueError('RGB_HOST must be loopback or a Tailscale IPv4 address')
CONFIG=ROOT/'config'
BINARY=ROOT/'vendor/usr/bin/openrgb'
CSRF=secrets.token_urlsafe(32)
LOCK=threading.Lock()
STATE={'colour':'#7c6aff','on':None,'message':'Choose a colour, or turn the lights on or off.'}
STATE_PATH=ROOT/'last-colour.json'
try:
    saved=json.loads(STATE_PATH.read_text())
    if isinstance(saved.get('colour'),str) and re.fullmatch('#[0-9a-fA-F]{6}',saved['colour']):
        STATE['colour']=saved['colour']
        STATE['message']='Ready. Your last colour is remembered; lights have not been changed at startup.'
except (OSError,ValueError,AttributeError):
    pass

def persist_colour():
    pending=STATE_PATH.with_suffix('.tmp')
    pending.write_text(json.dumps({'colour':STATE['colour']}))
    pending.replace(STATE_PATH)

def notify(message):
    address=os.environ.get('NOTIFY_SOCKET')
    if not address:return
    if address.startswith('@'):address='\0'+address[1:]
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
        sock.connect(address);sock.sendall(message.encode())


def command(args):
    if hashlib.sha256(BINARY.read_bytes()).hexdigest()!='79437b7fab445fcaa531f35116de72e030ce6299963ea569edb5ee7624e78f60':
        raise RuntimeError('Unrecognised OpenRGB binary; refusing hardware access')
    cfg=json.loads((ROOT/'config/OpenRGB.json').read_text())
    enabled=[k for k,v in cfg['Detectors']['detectors'].items() if v]
    if enabled!=['MSI Mystic Light MS_7D75']: raise RuntimeError('Controller allowlist changed; refusing hardware access')
    matches=[]
    for p in Path('/sys/class/hidraw').glob('*'):
        for parent in p.resolve().parents:
            if (parent/'idVendor').exists():
                if (parent/'idVendor').read_text().strip()=='1462' and (parent/'idProduct').read_text().strip()=='7d75': matches.append('/dev/'+p.name)
                break
    if len(matches)!=1: raise RuntimeError('Expected one MSI 7D75 controller; refusing hardware access')
    cmd=['bwrap','--ro-bind','/','/','--dev','/dev','--dev-bind',matches[0],matches[0],'--proc','/proc','--unshare-net','--bind',str(ROOT/'config'),str(ROOT/'config'),'--',str(ROOT/'vendor/usr/bin/openrgb'),'--config',str(ROOT/'config'),'--noautoconnect']+args
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    if result.returncode: raise RuntimeError('Lighting command failed; no retry was attempted')
    return result.stdout

def apply(action,colour=None):
    with LOCK:
        if action=='restore':
            command(['--device','0','--zone','2','--size','1','--zone','3','--size','1','--mode','Rainbow wave','--device','0','--mode','Rainbow wave'])
            STATE.update(on=None,message='Rainbow wave command sent. Check the lights to confirm.')
        else:
            chosen=colour if action=='colour' else STATE['colour']
            rgb='000000' if action=='off' else chosen[1:]
            # One virtual LED per ARGB header enables uniform static colour.
            # Never request per-LED direct mode, device save, firmware or effects.
            command(['--device','0','--zone','2','--size','1','--zone','3','--size','1','--mode','Static','--color',rgb,'--device','0','--mode','Static','--color',rgb,'--brightness','40'])
            STATE.update(colour=chosen,on=action!='off',message='Command sent: '+('off' if action=='off' else STATE['colour'])+'. Check the case lights to confirm.')
        persist_colour()
        return dict(STATE)

PAGE='''<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PC lights</title><style>body{font:18px system-ui;background:#11151e;color:#f3f4fa;margin:0;min-height:100vh;display:grid;place-items:center}main{width:min(86vw,420px);padding:30px;background:#1d2330;border-radius:24px}h1{margin-top:0}p{line-height:1.5;color:#bac2d6}button{border:0;border-radius:14px;padding:16px 22px;font:inherit;cursor:pointer;background:#7c6aff;color:white;margin:6px 4px 6px 0}button.secondary{background:#343d50}.presets{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:18px 0}.presets button{margin:0;padding:12px 8px;background:#343d50;font-size:15px;border:2px solid transparent}.presets button[aria-pressed="true"]{border-color:#f3f4fa}.swatch{display:block;width:24px;height:24px;border-radius:50%;margin:0 auto 8px;background:var(--colour)}#preset-name{color:#f3f4fa;margin:12px 0 0}input{width:100%;height:72px;border:0;background:transparent;margin:14px 0}small{color:#bac2d6}button:disabled{opacity:.5}#status{min-height:56px}a{color:#c8c1ff}</style><main><h1>PC lights</h1><p>A little remote for your Fedora PC.</p><button onclick="send('on')">On</button><button class="secondary" onclick="send('off')">Off</button><div class="presets" id="presets" aria-label="Colour presets"></div><button class="secondary" onclick="cyclePreset()">Cycle colours →</button><p id="preset-name" aria-live="polite">Custom colour</p><input oninput="markPreset(this.value)" type="color" id="colour" value="#7c6aff" aria-label="Light colour"><button onclick="send('colour')">Apply colour</button><p id="status">Choose a colour, or turn the lights on or off.</p><button class="secondary" onclick="send('restore')">Rainbow wave</button><p><small>Motherboard-connected lights · Private Tailscale access<br>Changes may reset when the PC restarts.</small></p></main><script>
const presets=[['Lavender','#7c6aff'],['Ocean','#00aaff'],['Mint','#34d399'],['Amber','#ffb347'],['Rose','#ff5e99'],['Red','#ff3030'],['Ice','#c4e7ff'],['Warm white','#ffe4b5'],['Violet','#b347ff']];
const picker=document.querySelector('#colour');
const grid=document.querySelector('#presets');
let busy=false;
presets.forEach(([name,colour],index)=>{
 const b=document.createElement('button');b.type='button';b.style.setProperty('--colour',colour);b.setAttribute('aria-pressed','false');
 const swatch=document.createElement('span');swatch.className='swatch';swatch.setAttribute('aria-hidden','true');
 b.append(swatch,document.createTextNode(name));b.onclick=()=>choosePreset(index);grid.append(b);
});
function markPreset(colour){
 const index=presets.findIndex(p=>p[1]===colour.toLowerCase());
 Array.from(grid.children).forEach((b,i)=>b.setAttribute('aria-pressed',String(i===index)));
 document.querySelector('#preset-name').textContent=index<0?'Custom colour':presets[index][0];
}
async function choosePreset(index){if(busy)return;picker.value=presets[index][1];markPreset(picker.value);await send('colour');}
async function cyclePreset(){const index=presets.findIndex(p=>p[1]===picker.value.toLowerCase());await choosePreset((index+1)%presets.length);}
async function send(action){
 if(busy)return;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);picker.disabled=true;
 try{
  const r=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-RGB-CSRF':'__CSRF__'},body:JSON.stringify({action,colour:picker.value})});
  const s=await r.json();document.querySelector('#status').textContent=s.message||s.error;
  if(r.ok&&s.colour){picker.value=s.colour;markPreset(s.colour);}
 }catch(e){document.querySelector('#status').textContent='Could not reach the PC.';}
 finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);picker.disabled=false;}
}
markPreset(picker.value);
fetch('/api').then(r=>r.json()).then(s=>{if(busy)return;document.querySelector('#status').textContent=s.message;picker.value=s.colour;markPreset(s.colour)}).catch(()=>{document.querySelector('#status').textContent='Could not reach the PC.'});
</script></html>'''
class Handler(http.server.BaseHTTPRequestHandler):
    def respond(self,status,data,ctype='application/json'):
        body=data.encode() if isinstance(data,str) else json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def valid_host(self): return self.headers.get('Host')==f'{HOST}:{PORT}'
    def do_GET(self):
        if not self.valid_host():return self.respond(403,{'error':'Unexpected host'})
        if self.path=='/':return self.respond(200,PAGE.replace('__CSRF__',CSRF),'text/html; charset=utf-8')
        if self.path=='/api':return self.respond(200,STATE)
        return self.respond(404,{'error':'Not found'})
    def do_POST(self):
        if not self.valid_host() or self.path!='/api':return self.respond(403,{'error':'Request rejected'})
        if self.headers.get('Origin')!=f'http://{HOST}:{PORT}' or not secrets.compare_digest(self.headers.get('X-RGB-CSRF',''),CSRF):return self.respond(403,{'error':'Request rejected'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<512:raise ValueError('Invalid request size')
            if self.headers.get('Content-Type')!='application/json':raise ValueError('Expected application/json')
            self.connection.settimeout(5)
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):raise ValueError('Expected a JSON object')
            action=data.get('action'); colour=data.get('colour')
            if action not in ['on','off','colour','restore']:raise ValueError('Invalid action')
            if action=='colour' and (not isinstance(colour,str) or not re.fullmatch('#[0-9a-fA-F]{6}',colour)):raise ValueError('Invalid colour')
            self.respond(200,apply(action,colour))
        except ValueError as e:self.respond(400,{'error':str(e)})
        except Exception:self.respond(503,{'error':'Lighting command failed. Check the local service logs and device access.'})
    def log_message(self,fmt,*args):pass
class Server(http.server.ThreadingHTTPServer):
    daemon_threads=True
    last_watchdog=0
    def service_actions(self):
        now=time.monotonic()
        if now-self.last_watchdog>=5:
            notify('WATCHDOG=1');self.last_watchdog=now

if __name__=='__main__':
    server=Server((HOST,PORT),Handler)
    server.socket.settimeout(5)
    notify('READY=1')
    server.serve_forever(poll_interval=.5)
