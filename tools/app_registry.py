"""Discover self-contained application definitions; no application ID registry."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIELDS={'title':48,'summary':96,'description':640,'changes':384,'channel':16}

def applications(root=None):
    root=Path(root) if root is not None else ROOT/'runtime/apps'
    result={}
    for path in sorted(root.glob('*/app.json')):
        if path.is_symlink() or path.parent.is_symlink():raise ValueError('Linked application definition')
        info=json.loads(path.read_text(encoding='utf-8'));ident=info.get('id','')
        if not re.fullmatch('[a-z0-9][a-z0-9-]{0,31}',ident) or ident!=path.parent.name:raise ValueError('Invalid application ID: '+str(path))
        if info.get('schema')!=1 or info.get('target')!='sony-nw-x1000-jp':raise ValueError('Unsupported application definition: '+ident)
        for field,limit in FIELDS.items():
            value=info.get(field)
            if not isinstance(value,str) or not 1<=len(value)<=limit or any(ord(c)<32 or ord(c)>126 for c in value):raise ValueError('Invalid app metadata: '+ident+'/'+field)
        if info['channel'] not in ('stable','experimental'):raise ValueError('Invalid release channel')
        recipe=info.get('build')
        if not isinstance(recipe,dict) or recipe.get('script')!='build.py' or not (path.parent/'build.py').is_file():raise ValueError('Missing local builder: '+ident)
        package=recipe.get('package','')
        if not isinstance(package,str) or not package.startswith('work/') or '..' in Path(package).parts:raise ValueError('Invalid build package path: '+ident)
        if not (path.parent/'VERSION').is_file() or not (path.parent/'assets/icon.png').is_file():raise ValueError('Missing app version or icon: '+ident)
        result[ident]=info
    return result

def asset(ident,name):
    if ident not in applications():raise ValueError('Unknown application: '+ident)
    if name not in ('icon.png','icon.svg'):raise ValueError('Unsupported source asset')
    return ROOT/'runtime/apps'/ident/'assets'/name
