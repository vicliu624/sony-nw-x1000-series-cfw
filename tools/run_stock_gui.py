"""Local interactive viewer for original Sony userspace in the modeled ARM guest."""
import argparse,atexit,hashlib,io,json,os,secrets,signal,socket,struct,subprocess,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
PROFILE=['--normal-boot-fixture','--ram-state-fixture','--stock-home-fixture','--omf-ram-fixture',
 '--japanese-model-fixture','--empty-serial-fixture','--empty-media-registry',
 '--zero-platform-config-fixture','--ncan-control-model','--display-touch-model','--stock-daemons',
 '--silent-mixer-model','--touch-serial','--prepare-only','--interactive-guest']

PAGE='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NW-X1000 Sony UI</title><style>
body{margin:0;background:#15171b;color:#f3f4f5;font:15px system-ui;text-align:center}header{padding:13px}h1{font-size:19px;margin:0 0 6px}p{margin:5px;color:#bfc6d0}canvas{display:block;margin:10px auto;background:#000;touch-action:none;image-rendering:auto;width:min(480px,calc((100vh - 150px)*240/432));height:auto;border:1px solid #3a424e;border-radius:3px}button{background:#28323f;color:#fff;border:1px solid #556272;border-radius:6px;padding:7px 15px;margin:0 4px;cursor:pointer}#status{font-size:13px}
</style><header><h1>NW-X1000 · Original Sony interface</h1><p>Click or drag on the screen. Audio, DSP and RF are unavailable.</p><div id="status">Starting the isolated player…</div></header>
<canvas id="screen" width="240" height="432"></canvas><footer><button id="release">Release touch</button><button id="stop">Close emulator</button><p>This isolated session resets when closed.</p></footer>
<script>const token="__TOKEN__", c=document.querySelector('#screen'), ctx=c.getContext('2d');let pressed=false,last=0,stopped=false;
async function post(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':token},body:JSON.stringify(data)});if(!r.ok)throw Error(await r.text());return r.json()}
function point(e){const b=c.getBoundingClientRect();return{x:Math.max(0,Math.min(239,Math.floor((e.clientX-b.left)*240/b.width))),y:Math.max(0,Math.min(431,Math.floor((e.clientY-b.top)*432/b.height)))}}
let input=Promise.resolve(),contact=false;function touch(e,down){let p=point(e);input=input.then(async()=>{let first=down&&!contact;await post('/touch',{...p,down});contact=!!down;if(down)await new Promise(resolve=>setTimeout(resolve,first?250:50))}).catch(x=>document.querySelector('#status').textContent=x.message)}
c.onpointerdown=e=>{e.preventDefault();c.setPointerCapture(e.pointerId);pressed=true;touch(e,1)};c.onpointermove=e=>{if(pressed&&performance.now()-last>50){last=performance.now();touch(e,1)}};
c.onpointerup=e=>{if(pressed){pressed=false;touch(e,0)}};c.onpointercancel=c.onpointerup;c.oncontextmenu=e=>e.preventDefault();
document.querySelector('#release').onclick=()=>post('/release',{});document.querySelector('#stop').onclick=async()=>{stopped=true;await post('/stop',{});document.querySelector('#status').textContent='Emulator closed'};
async function refresh(){if(stopped)return;try{let response=await fetch('/frame.png?t='+Date.now());if(response.ok){let bitmap=await createImageBitmap(await response.blob());ctx.drawImage(bitmap,0,0);bitmap.close()}let s=await(await fetch('/status')).json();document.querySelector('#status').textContent=s.message}catch(e){document.querySelector('#status').textContent='Waiting for the emulator…'}setTimeout(refresh,120)}refresh();</script></html>'''

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output');p.add_argument('--session');p.add_argument('--port',type=int,default=0);p.add_argument('--firmware-review');p.add_argument('--settings-layout',choices=['primary','secondary'],default='primary')
 p.add_argument('--homebrew-roundtrip-fixture',action='store_true',help='Use a short guest-only external child to test native Homebrew return')
 p.add_argument('--catalog-trace',action='store_true',help='Observe delegated SQLite filenames/errors in a new isolated guest')
 p.add_argument('--ram-user-volume',action='store_true',help='Supply a volatile FAT32 block for stock /contents mounting in a new isolated guest')
 p.add_argument('--remote-runtime-review',help='Stage reviewed Remote binaries and synthetic config in a new volatile guest')
 p.add_argument('--mg-constructor-model',action='store_true',help='Guest-only empty MG constructor; no crypto/key operations')
 args=p.parse_args();assert bool(args.output)!=bool(args.session),'Choose a new output or a prepared session'
 if args.homebrew_roundtrip_fixture and not args.output:p.error('--homebrew-roundtrip-fixture requires a new --output')
 if args.catalog_trace and not args.output:p.error('--catalog-trace requires a new --output')
 if args.mg_constructor_model and not args.output:p.error('--mg-constructor-model requires a new --output')
 if args.ram_user_volume and not args.output:p.error('--ram-user-volume requires a new --output')
 if args.remote_runtime_review and (not args.output or not args.ram_user_volume or not args.firmware_review):p.error('--remote-runtime-review requires new output, RAM user volume and firmware review')
 session=(ROOT/(args.output or args.session)).resolve();assert session.is_relative_to(ROOT/'work')
 if args.output:
  profile=[('--stock-env-fallback-fixture' if item=='--japanese-model-fixture' and args.settings_layout=='secondary' else item) for item in PROFILE]
  subprocess.run([sys.executable,str(ROOT/'tools/probe_stock_manager_system.py'),'--output',args.output,*profile,*(['--firmware-review',args.firmware_review] if args.firmware_review else []),*(['--homebrew-roundtrip-fixture'] if args.homebrew_roundtrip_fixture else []),*(['--catalog-trace'] if args.catalog_trace else []),*(['--ram-user-volume'] if args.ram_user_volume else []),*(['--remote-runtime-review',args.remote_runtime_review] if args.remote_runtime_review else []),*(['--mg-constructor-model'] if args.mg_constructor_model else [])],cwd=ROOT,check=True)
 elif args.firmware_review:p.error('--firmware-review requires a new --output')
 prepared=json.loads((session/'prepared.json').read_text());assert prepared['physical_device_access'] is False and prepared['interactive_guest']
 for name,digest in prepared['binary_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
 for name,digest in prepared['compiled_source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'Prepared sources changed; use a new --output'
 assert prepared['command'][prepared['command'].index('-M')+1]=='versatilepb'
 env=dict(os.environ,LD_LIBRARY_PATH=prepared['runtime_library_path'],QEMU_AUDIO_DRV='none')
 monitor_lock=threading.Lock();touch_lock=threading.Lock();token=secrets.token_hex(24);control=None;last=(120,216)
 serial=(session/'serial.log').open('wb');errors=(session/'qemu.log').open('wb')
 process=subprocess.Popen(prepared['command'],env=env,stdout=serial,stderr=errors,cwd=ROOT)
 def cleanup():
  if control is not None:control.close()
  if process.poll() is None:
   process.terminate()
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:process.kill();process.wait()
  serial.close();errors.close()
  (session/'viewer-ended.json').write_text(json.dumps(dict(qemu_exit=process.returncode,physical_device_access=False))+'\n')
 atexit.register(cleanup)
 def terminate(signum,frame):raise KeyboardInterrupt
 signal.signal(signal.SIGTERM,terminate)
 launch=dict(command=prepared['command'],monitor_port=prepared['monitor_port'],touch_port=prepared['touch_port'],qemu_pid=process.pid,physical_device_access=False,compiled_source_hashes=prepared['compiled_source_hashes'])
 (session/'launch.json').write_text(json.dumps(launch,indent=2)+'\n')
 def live():
  if process.poll() is not None:raise RuntimeError('QEMU has stopped; read serial.log and qemu.log')
 def prompt(monitor):
  data=b''
  while b'(qemu)' not in data:
   chunk=monitor.recv(4096)
   if not chunk:raise EOFError('QEMU monitor closed')
   data+=chunk
  return data
 def frame():
  live();target=session/'viewer-clcd.ppm'
  with monitor_lock:
   with socket.create_connection(('127.0.0.1',prepared['monitor_port']),timeout=3) as monitor:
    prompt(monitor);monitor.sendall(('screendump "'+str(target)+'"\n').encode());answer=prompt(monitor)
   if not target.is_file():raise RuntimeError(answer.decode(errors='replace'))
   with Image.open(target) as screen:
    left=(screen.width-240)//2;top=(screen.height-432)//2
    assert left>=0 and top>=0
    cropped=screen.crop((left,top,left+240,top+432));out=io.BytesIO();cropped.save(out,format='PNG');return out.getvalue()
 def touch(x,y,down):
  nonlocal control,last
  live();assert type(x) is int and type(y) is int and type(down) is int
  assert 0<=x<240 and 0<=y<432 and down in (0,1)
  with touch_lock:
   if control is None:control=socket.create_connection(('127.0.0.1',prepared['touch_port']),timeout=3)
   control.sendall(struct.pack('<4sHHB',b'XWT1',x,y,down));last=(x,y)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def reply(self,status,body,kind='application/json'):
   self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  def do_GET(self):
   try:
    path=self.path.split('?',1)[0]
    if path=='/':return self.reply(200,PAGE.replace('__TOKEN__',token).encode(),'text/html; charset=utf-8')
    if path=='/frame.png':return self.reply(200,frame(),'image/png')
    if path=='/status':
     try:text=(session/'serial.log').read_text(errors='replace')
     except OSError:text=''
     if process.poll() is not None:message='Emulator stopped — inspect its local logs.'
     elif 'PANIC at' in text or 'GUEST_MANAGER_PROBE_COMPLETE' in text:message='Sony userspace stopped — inspect its local logs.'
     elif 'GUEST_SONY_RGB565_FRAME_PRESENTED' in text:message='Original Sony screen is running · touch input enabled'
     else:message='Booting the original Sony userspace…'
     return self.reply(200,json.dumps(dict(message=message,qemu_pid=process.pid,physical_device_access=False)).encode())
    return self.reply(404,b'{}')
   except (OSError,RuntimeError,AssertionError,EOFError) as error:self.reply(503,json.dumps(dict(error=str(error))).encode())
  def do_POST(self):
   if self.headers.get('X-Control-Token')!=token:return self.reply(403,b'{}')
   try:
    size=int(self.headers.get('Content-Length','0'));assert 0<size<=512
    value=json.loads(self.rfile.read(size))
    if self.path=='/touch':touch(value['x'],value['y'],value['down'])
    elif self.path=='/release':touch(*last,0)
    elif self.path=='/stop':threading.Thread(target=server.shutdown,daemon=True).start()
    else:return self.reply(404,b'{}')
    self.reply(200,b'{"accepted":true}')
   except (OSError,RuntimeError,AssertionError,ValueError,KeyError) as error:self.reply(400,json.dumps(dict(error=str(error))).encode())
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 metadata=dict(url=f'http://127.0.0.1:{server.server_port}/',server_pid=os.getpid(),qemu_pid=process.pid,control_token=token,physical_device_access=False,source=__file__,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),session=str(session.relative_to(ROOT)),limitations=['Generic ARM kernel and modeled peripherals; not MP200/kernel/DSP/RF qualification.','No audio or media components.','Only original Sony libc device calls are adapted; direct-syscall external apps require further support.'])
 (session/'server.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({k:v for k,v in metadata.items() if k!='control_token'}),flush=True)
 try:server.serve_forever(poll_interval=.2)
 except KeyboardInterrupt:pass
 finally:
  server.server_close()
  cleanup();atexit.unregister(cleanup)
if __name__=='__main__':main()
