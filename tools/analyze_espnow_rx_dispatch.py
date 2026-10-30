"""Offline REA/Ghidra review of exact stock RX software ingress; no device IO."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',choices=['rx-dispatch','mac-control','security-state'],default='rx-dispatch');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/('work/espnow-'+args.profile+'-rea');OUT.mkdir(parents=True,exist_ok=True)
procedures={'rx-dispatch':['0xc0003188','0xe164','0xa314'],'mac-control':['0x54c0','0x6b6c','0xa674','0xa698'],'security-state':['0xc00048c8','0xc0004cd8','0xc0003c8c','0xc0006144']}[args.profile]
image=ROOT/'work/espnow-audit/analysis-io.elf';stock=ROOT/'work/targets-jp/sd8686.bin'
assert hashlib.sha256(image.read_bytes()).hexdigest()=='094457f71d272cae14e42b90e58fc78c6299f0894170a45b092eff9f14d993ff'
assert hashlib.sha256(stock.read_bytes()).hexdigest()=='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
env=dict(os.environ,GHIDRA_INSTALL_DIR=str(ROOT/'work/stock-wifi-decompiler/ghidra_12.1.4_PUBLIC'),JAVA_HOME='/usr/lib/jvm/java-21-openjdk-amd64',REA_GHIDRA_STARTUP_TIMEOUT_MS='240000')
sequence=0
with (OUT/'stderr.log').open('w') as error:
    p=subprocess.Popen(['npx','--offline','--yes','rea-agents@6.5.0','--mcp'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error,text=True,env=env)
    def rpc(method,params):
        global sequence
        sequence+=1;p.stdin.write(json.dumps({'jsonrpc':'2.0','id':sequence,'method':method,'params':params})+'\n');p.stdin.flush()
        while True:
            line=p.stdout.readline()
            if not line:raise RuntimeError('REA process ended')
            response=json.loads(line)
            if response.get('id')==sequence:return response
    try:
        rpc('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'xnow-rx-dispatch','version':'1'}})
        response=rpc('tools/call',{'name':'open_binary','arguments':{'path':str(image),'provider_id':'ghidra'}})
        (OUT/'open.json').write_text(json.dumps(response,indent=2)+'\n');print('REA opened pinned stock analysis image',flush=True)
        for address in procedures:
            response=rpc('tools/call',{'name':'procedure_pseudo_code','arguments':{'procedure':address}})
            (OUT/(address+'.json')).write_text(json.dumps(response,indent=2)+'\n')
            body=response.get('result',{});value=body.get('structuredContent')
            if value is None and body.get('content'):
                try:value=json.loads(body['content'][0]['text'])
                except (ValueError,KeyError):value=body['content'][0].get('text','')
            normalized=value.get('normalized_result',value) if isinstance(value,dict) else value
            (OUT/(address+'.txt')).write_text(str(normalized)+'\n');print('REA reviewed '+address,flush=True)
    finally:
        p.stdin.close()
        try:p.wait(timeout=30)
        except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=15)
report={'analysis_elf_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'stock_radio_sha256':hashlib.sha256(stock.read_bytes()).hexdigest(),'procedures':procedures,'device_accessed':False,'driver_modified':False,'radio_loaded':False,'semantic_conclusions_require_review':True}
(OUT/'inputs.json').write_text(json.dumps(report,indent=2)+'\n')
