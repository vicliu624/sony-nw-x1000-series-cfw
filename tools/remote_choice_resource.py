"""Shared construction of the private Remote SWD from the pinned stock page."""
import re
SOURCE='usr/local/share/gemini/res/swd/ucs2-dev-sid-139-00.swd'
TARGET='usr/local/share/gemini/res/swd/ucs2-dev-sid-139-01.swd'
RESOURCE_ID=13901
def compose(raw):
 raw,n=re.subn(rb'(^sid:\s*)"sid-139-00"',rb'\1"sid-139-01"',raw,flags=re.M)
 if n!=1:raise ValueError('Expected native On/Off SID')
 raw,n=re.subn(rb'(^title:\s*)"tid-6810"',rb'\1"tid-7310"',raw,flags=re.M)
 if n!=1:raise ValueError('Expected native On/Off title')
 if re.findall(rb'^tid\.(\d+):\s*"tid-(\d+)"',raw,re.M)!=[(b'0',b'0255'),(b'1',b'0256')]:raise ValueError('Unexpected choice wording')
 return raw
