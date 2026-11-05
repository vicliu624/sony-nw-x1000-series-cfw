"""Compose wireless labels after an existing Settings overlay; PC-side only."""
import re
from resources import append_stx, parse_stx


def compose(wordings, swd, mode_swd):
    if not wordings:
        raise ValueError('No language resources')
    counts = {len(parse_stx(data)) for data in wordings.values()}
    if len(counts) != 1:
        raise ValueError('Language resource indices differ')
    first = counts.pop()
    if not re.search(rb'^sid:\s*"sid-100-00"',swd,re.M) or not re.search(rb'^sid:\s*"sid-139-00"',mode_swd,re.M):
        raise ValueError('Expected parent WLAN and native On/Off resource pages')
    if re.search(rb'^tid\.2:', mode_swd, re.M):
        raise ValueError('Third wireless choice already exists')
    # Allocate after all preceding labels, including the independent Remote row.
    ids = dict(wifi=first, espnow=first + 1, mode_title=first + 2)
    result = {}
    for language, data in wordings.items():
        title = {'jp': '無線モード', 'cs': '无线模式', 'ct': '無線模式'}.get(language, 'Wireless Mode')
        for key, text in (('wifi', 'Wi-Fi'), ('espnow', 'ESP-NOW'), ('mode_title', title)):
            data, index = append_stx(data, text)
            if index != ids[key]:
                raise ValueError('Unexpected resource allocation')
        result[language] = data
    for local, old, key in ((0, 6675, 'mode_title'),):
        pattern = rb'(^tid\.' + str(local).encode() + rb':\s*)"tid-' + f'{old:04d}'.encode() + rb'"'
        swd, count = re.subn(pattern, lambda m: m[1] + f'"tid-{ids[key]:04d}"'.encode(), swd, flags=re.M)
        if count != 1:
            raise ValueError('Unexpected original wireless label')
    # Control0x1d's original Pcs descriptor resolves resource13900, not the
    # parent sid100 page. Each displayed row is local tid0/1/2 on sid139.
    for field, old, key in ((b'title',6810,'mode_title'),(b'tid.0',255,'wifi')):
        pattern=rb'(^'+re.escape(field)+rb':\s*)"tid-'+f'{old:04d}'.encode()+rb'"'
        mode_swd,count=re.subn(pattern,lambda m:m[1]+f'"tid-{ids[key]:04d}"'.encode(),mode_swd,flags=re.M)
        if count!=1:raise ValueError('Unexpected native On/Off title or first choice')
    if not re.search(rb'^tid\.1:\s*"tid-0256"',mode_swd,re.M):
        raise ValueError('Original OFF choice changed')
    mode_swd=mode_swd.rstrip()+f'\n\ntid.2:\t"tid-{ids["espnow"]:04d}"\t; ESP-NOW\n'.encode()
    return result, swd, mode_swd, ids
