"""Local-only QA wrapper for the in-chat mockup; no account or device activity."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
skill=Path('C:/Users/VicLi/.codex/plugins/cache/openai-bundled/visualize/1.0.55/skills/visualize')
fragment=ROOT/'work/previews/qqmusic-ui-review.html'
text=fragment.read_text(encoding='utf-8')
assert not re.search(r'<!doctype|<html|<head>|<body',text,re.I)
assert not re.search(r'\bfetch\s*\(|XMLHttpRequest|WebSocket',text)
work=ROOT/'work/qqmusic-ui-review';work.mkdir(exist_ok=True)
test=r'''<script>
window.addEventListener('load',()=>{
 const q=new URLSearchParams(location.search),page=q.get('page')||'home';
 if(q.get('theme')==='dark')document.documentElement.style.colorScheme='dark';
 const id=q.get('variant')==='list'?'qq-readable':'qq-classic';
 if(id==='qq-readable'){const next=document.querySelector('.viz-carousel-next');if(next)next.click();}
 const app=document.getElementById(id);
 const click=selector=>{const element=app.querySelector(selector);if(!element)throw Error('Missing '+selector);element.click();};
 if(['songs','detail','progress','result','cancel','blocked'].includes(page))click('[data-action="playlist"]');
 if(['detail','progress','result','cancel'].includes(page))click('[data-action="song"][data-song="0"]');
 if(page==='blocked')click('[data-action="song"][data-song="3"]');
 if(['progress','result','cancel'].includes(page))click('[data-action="download"]');
 if(page==='cancel')setTimeout(()=>click('[data-action="cancel"]'),200);
 if(['profile','login'].includes(page))click('[data-action="page"][data-page="profile"]');
 if(page==='login')click('[data-action="page"][data-page="login"]');
 setTimeout(()=>{
  const body=app.querySelector('.qq-body');
  const rect=app.closest('.qq-device').getBoundingClientRect();
  const metrics={page,variant:id,width:app.clientWidth,height:app.clientHeight,deviceTop:rect.top,deviceBottom:rect.bottom,
   bodyWidth:body?.clientWidth,bodyScrollWidth:body?.scrollWidth,
   horizontalOverflow:body?body.scrollWidth>body.clientWidth:false,
   bodyHeight:body?.clientHeight,bodyScrollHeight:body?.scrollHeight,
   text:app.innerText};
  const output=document.createElement('script');output.type='application/json';output.id='qq-ui-qa';output.textContent=JSON.stringify(metrics);document.body.append(output);
 },page==='result'?3900:400);
});
</script>'''
kit=(skill/'assets/visualize.html').read_text(encoding='utf-8').replace('<!--__INLINE_VISUALIZATION_FRAGMENT__-->',text+test)
css=(skill/'assets/visualize.css').read_text(encoding='utf-8')
document='<!doctype html><html lang="zh-CN" style="color-scheme:light"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>X1060 QQ音乐界面评审</title><style>'+css+'\nbody{margin:0;padding:16px;background:light-dark(#f7f9f8,#171b18)}[hidden]{display:none!important}</style>'+kit+'</html>'
(work/'preview.html').write_text(document,encoding='utf-8')
(work/'build.json').write_text(json.dumps({'fragment_sha256':hashlib.sha256(fragment.read_bytes()).hexdigest(),'synthetic_ui':True,'device_access':False,'network_account_calls':False},indent=2)+'\n')
print(work/'preview.html')
