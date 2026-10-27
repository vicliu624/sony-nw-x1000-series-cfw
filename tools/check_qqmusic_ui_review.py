"""Isolated headless Chrome rendering of owned synthetic mockup; no real account."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'tools/prepare_qqmusic_ui_review.py')],cwd=ROOT,check=True)
work=ROOT/'work/qqmusic-ui-review';chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
assert chrome.is_file();base=(work/'preview.html').as_uri();rows=[]
cases=[('home',''),('songs','?page=songs'),('detail','?page=detail'),('progress','?page=progress'),('result','?page=result'),('login','?page=login'),('profile','?page=profile'),('cancel','?page=cancel'),('blocked','?page=blocked'),('list','?variant=list'),('dark','?theme=dark')]
for name,query in cases:
    budget='750' if name=='progress' else '6000'
    info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
    run=subprocess.run([str(chrome),'--headless=new','--disable-gpu','--no-first-run','--user-data-dir='+str(work/'chrome-profile'),'--window-size=780,880','--virtual-time-budget='+budget,'--screenshot='+str(work/(name+'.png')),'--dump-dom',base+query],capture_output=True,text=True,encoding='utf-8',timeout=30,startupinfo=info)
    assert run.returncode==0,(name,run.stderr[-1000:])
    match=re.search(r'<script type="application/json" id="qq-ui-qa">(.*?)</script>',run.stdout,re.S)
    assert match,(name,'missing QA output')
    metrics=json.loads(match.group(1));assert metrics['width']==240 and metrics['height']==432 and not metrics['horizontalOverflow'],metrics
    assert metrics['deviceTop']>=0,metrics
    expected={'home':'我的音乐','songs':'选择一首','detail':'下载为 MP3','progress':'正在导入','result':'MP3 已准备好','login':'二维码仅作界面示意','cancel':'本次导入已取消','blocked':'暂无下载权限','list':'我的音乐','dark':'我的音乐','profile':'默认 MP3 音质'}[name]
    assert expected in metrics['text'],(name,metrics['text'])
    rows.append({k:v for k,v in metrics.items() if k!='text'})
report={'passed':True,'synthetic_ui':True,'device_access':False,'cases':rows,'fragment_sha256':hashlib.sha256((ROOT/'work/previews/qqmusic-ui-review.html').read_bytes()).hexdigest(),
        'limits':['Visual/interaction review only, no backend or device writes.','Screenshots rendered by isolated PC Chrome, not X1060 framebuffer.']}
(work/'qa.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
