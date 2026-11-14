"""Shared construction of the private Remote SWD from the pinned stock page."""
import re
SOURCE='usr/local/share/gemini/res/swd/ucs2-dev-sid-139-00.swd'
TARGET='usr/local/share/gemini/res/swd/ucs2-dev-sid-139-01.swd'
RESOURCE_ID=13901
BOUND_TARGET=TARGET.replace('139-01','139-02')
BOUND_RESOURCE_ID=13902
CONFIRM_SOURCE=SOURCE.replace('139-00','144-00')
CONFIRM_TARGET=TARGET.replace('139-01','139-03')
PAIR_TARGET=TARGET.replace('139-01','139-04')
def compose(raw,pairing=False):
 raw,n=re.subn(rb'(^sid:\s*)"sid-139-00"',rb'\1"sid-139-01"',raw,flags=re.M)
 if n!=1:raise ValueError('Expected native On/Off SID')
 raw,n=re.subn(rb'(^title:\s*)"tid-6810"',rb'\1"tid-7310"',raw,flags=re.M)
 if n!=1:raise ValueError('Expected native On/Off title')
 if re.findall(rb'^tid\.(\d+):\s*"tid-(\d+)"',raw,re.M)!=[(b'0',b'0255'),(b'1',b'0256')]:raise ValueError('Unexpected choice wording')
 return raw.rstrip()+b'\n\ntid.2:\t"tid-3014"\n' if pairing else raw

def compose_bound(raw):
 return compose(raw,True).replace(b'"sid-139-01"',b'"sid-139-02"').replace(b'"tid-3014"',b'"tid-3065"')
