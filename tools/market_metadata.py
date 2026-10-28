"""Shared bounded market metadata and SemVer release policy (standard library)."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATTERN=re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z')
def parse_version(value):
    match=PATTERN.fullmatch(value)
    if not match or len(value)>32:raise ValueError('Invalid SemVer: '+value)
    pre=match[4].split('.') if match[4] else []
    if any(x.isdigit() and len(x)>1 and x[0]=='0' for x in pre):raise ValueError('Leading zero in prerelease')
    return tuple(int(match[i]) for i in (1,2,3)),pre
def compare_versions(a,b):
    x,px=parse_version(a);y,py=parse_version(b)
    if x!=y:return (x>y)-(x<y)
    if not px or not py:return (not px)-(not py)
    for u,v in zip(px,py):
        if u==v:continue
        if u.isdigit() and v.isdigit():return (int(u)>int(v))-(int(u)<int(v))
        if u.isdigit()!=v.isdigit():return -1 if u.isdigit() else 1
        return (u>v)-(u<v)
    return (len(px)>len(py))-(len(px)<len(py))
def descriptions():
    from app_registry import applications,FIELDS
    return {ident:{key:info[key] for key in FIELDS} for ident,info in applications().items()}

def catalog_records(data):
    lines=data.decode('ascii').splitlines()
    if not lines or lines[0] not in ('HBSTORE1','HBSTORE2','HBSTORE3'):raise ValueError('Unknown catalog')
    records={}
    for row in lines[1:]:
        fields=row.split('\t');ident,version=fields[:2];parse_version(version)
        if ident in records:raise ValueError('Duplicate app ID')
        if len(fields)!={'HBSTORE1':7,'HBSTORE2':8,'HBSTORE3':14}[lines[0]]:raise ValueError('Wrong catalog fields')
        records[ident]={'version':version,'inventory_sha256':fields[6]}
    return records
def check_history(incoming,history):
    for previous in history:
        for ident,new in incoming.items():
            if ident not in previous:continue
            old=previous[ident];comparison=compare_versions(new['version'],old['version'])
            if comparison<0:raise ValueError('Release regresses app version: '+ident)
            if comparison==0 and new['inventory_sha256']!=old['inventory_sha256']:raise ValueError('Changed package requires a higher app version: '+ident)
def description_header():
    # Kept for PC callers during migration; no application identities in device code.
    return "/* App descriptions are supplied by package/catalog metadata. */\n"

def write_header():
    (ROOT/'runtime/store/market_descriptions.h').write_text(description_header())
if __name__=='__main__':write_header()
