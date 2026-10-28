"""Render public SDK website fixtures from actual host C apps. No device/account."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from PIL import Image
from app_registry import ROOT
from sdk_build import compile_app

def main():
    output=ROOT/'work/sdk-gallery'/str(time.time_ns());output.mkdir(parents=True)
    assets=ROOT/'website/assets';assets.mkdir(exist_ok=True)
    report={'hardware_accessed':False,'synthetic_events':True,'files':{}}
    for ident in ('sdk-counter','sdk-canvas'):
        folder=output/ident;folder.mkdir();data=folder/'data';data.mkdir()
        artifact=compile_app(ROOT/'runtime/apps'/ident,folder/'host',host=True)
        events=folder/'events.txt';events.write_text('tap 60 215\ntick 100\ntick 100\n')
        frame=folder/'frame.ppm'
        subprocess.run([str(artifact),'--render',str(frame),'--events',str(events),'--data',str(data)],cwd=ROOT,check=True)
        with Image.open(frame) as image:image.save(folder/'frame.png')
        public=assets/(ident+'.png');public.write_bytes((folder/'frame.png').read_bytes())
        build=json.loads((folder/'host.build-report.json').read_text())
        report['files'][public.name]={'sha256':hashlib.sha256(public.read_bytes()).hexdigest(),'source_hashes':build['source_hashes'],'events':events.read_text()}
    (assets/'sdk-previews.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Rendered two credential-free SDK fixture previews into website/assets.')
if __name__=='__main__':main()
