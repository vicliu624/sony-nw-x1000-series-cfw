"""Offline repository layout/documentation check. Never accesses a player."""
from pathlib import Path
import ast,json,re,sys
ROOT=Path(__file__).resolve().parents[1]
errors=[];warnings=[]
apps=ROOT/'runtime/apps'
for p in apps.iterdir():
 if p.is_file() and p.name!='README.md':errors.append('Flat app source: '+p.relative_to(ROOT).as_posix())
for name in ('ebook','dictionary','emulators','language','diagnostics'):
 if (ROOT/'runtime'/name).exists():errors.append('Old runtime directory remains: '+name)
docs=[ROOT/n for n in ('README.md','AGENTS.md','CHANGELOG.md','THIRD_PARTY.md')]
docs+=list((ROOT/'docs').rglob('*.md'))+list(apps.rglob('README.md'))
docs+=list((ROOT/'sources').glob('README.md'))+list((ROOT/'third_party').rglob('PROVENANCE.md'))
for p in docs:
 text=p.read_text(encoding='utf-8-sig')
 if re.search(r'[\u3400-\u9fff\u3040-\u30ff]',text):errors.append('Non-English documentation: '+p.relative_to(ROOT).as_posix())
 for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
  target=target.strip('<>').split('#',1)[0]
  if not target or re.match(r'\w+://',target):continue
  if not (p.parent/target).exists():errors.append(f'Broken link {p.relative_to(ROOT)}: {target}')
source_count=0;python_count=0
for folder in ('runtime','tools','scripts','tests'):
 for p in (ROOT/folder).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts:continue
  if p.suffix not in ('.py','.c','.h','.cpp','.hpp','.inc','.S','.ps1'):continue
  source_count+=1
  try:text=p.read_text(encoding='utf-8-sig')
  except UnicodeDecodeError:continue
  if p.suffix=='.py':
   python_count+=1
   try:ast.parse(text,filename=str(p))
   except SyntaxError as e:errors.append(str(e))
  if p.name==Path(__file__).name:continue
  checked='\n'.join(line for line in text.splitlines() if not line.startswith('baseline={'))
  for old in ('runtime/apps/qqmusic_','runtime/apps/fm_','runtime/apps/device_info_','runtime/apps/terminal.c','runtime/apps/terminal.h'):
   if old in checked:errors.append(f'Old source path in {p.relative_to(ROOT)}: {old}')
  if p.suffix in ('.c','.h','.cpp','.hpp','.inc','.S'):
   for include in re.findall(r'#include\s+"([^"\n]+)"',text):
    if include.startswith('.') and not (p.parent/include).exists():errors.append(f'Broken relative include {p.relative_to(ROOT)}: {include}')
  for literal in re.findall(r'''["']((?:runtime|docs)/[A-Za-z0-9_./+\-]+\.(?:c|h|inc|S|md))["']''',text):
   if not (ROOT/literal).exists():warnings.append(f'Literal path absent in {p.relative_to(ROOT)}: {literal}')
ignore=(ROOT/'.gitignore').read_text()
for required in ('/.tmp/','/work/','/firmware/','/dist/','/bundles/'):
 if required not in ignore:errors.append('Missing ignore rule: '+required)
report={'passed':not errors,'source_files_checked':source_count,'python_files_parsed':python_count,'english_documents_checked':len(docs),'errors':sorted(set(errors)),'warnings':sorted(set(warnings)),'device_accessed':False}
out=ROOT/'work/repository-layout-check';out.mkdir(parents=True,exist_ok=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
sys.exit(0 if report['passed'] else 1)
