"""Host-only comparison of actual old/new app renderers; not device FPS."""
from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];w=R/'work/gbc-shell-benchmark';w.mkdir(exist_ok=True)
rows=[]
for name,source in [('baseline',R/'work/gbc-audio-optimization-baseline/runtime/apps/emulators/app.c'),('optimized',R/'runtime/apps/emulators/app.c')]:
 c=w/(name+'.c');c.write_text('#define main unused_app_main\n#include "'+str(source)+'"\n#undef main\n#include <time.h>\nstatic uint16_t pixels[160*144];\nconst uint16_t *gb_pixels(void){return pixels;}\nint main(void){mode=GAME;audio.enabled=1;displayed_keys=0;clock_t begin=clock();for(int i=0;i<300;i++){pixels[0]=(uint16_t)i;render();}printf("%.6f\\n",(double)(clock()-begin)/CLOCKS_PER_SEC);return 0;}\n')
 exe=w/name
 subprocess.run(['gcc','-std=c99','-O2','-D_DEFAULT_SOURCE','-ffunction-sections','-fdata-sections','-I'+str(R/'runtime/apps/emulators'),str(c),'runtime/apps/emulators/platform.c','runtime/platform/pcm_output.c','runtime/apps/fm-radio/fm_audio.c','-Wl,--gc-sections','-o',str(exe)],cwd=R,check=True)
 t=float(subprocess.check_output([str(exe)],text=True));rows.append({'renderer':name,'300_frames_cpu_seconds':t,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
assert rows[1]['300_frames_cpu_seconds']<rows[0]['300_frames_cpu_seconds']
report={'passed':True,'cases':rows,'scope':'Host CPU time, same 300 stationary-key GAME renders of production app code; excludes core, framebuffer driver, hardware and real headphone audio.'}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
