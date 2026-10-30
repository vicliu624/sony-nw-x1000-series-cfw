"""Explicit live original-Cardputer smoke test; no flashing or X1060 commands.

Requires chat firmware already installed. Sends one marked broadcast message;
tests absent-peer timeout and rejects unexpected peer discovery in this fixture.
Never invoked by offline builds. All logs go to a NEW directory under work/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import serial

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve()
    if not out.is_relative_to((ROOT/'work').resolve()) or out.exists():
        raise ValueError('output must be a new directory under project work/')
    out.mkdir(parents=True)
    raw=bytearray();checks=[]
    link=serial.Serial();link.port=args.port;link.baudrate=115200;link.timeout=.1
    link.dtr=False;link.rts=False
    def collect(seconds):
        start=len(raw);deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:raw.extend(link.read(4096))
        return bytes(raw[start:]).decode(errors='replace')
    def command(text,seconds=.3):
        link.write(text.encode('ascii')+b'\n');link.flush();return collect(seconds)
    def status():
        text=command('status',.5)
        rows=re.findall(r'CHAT_STATUS version=(\S+) channel=(\d+) paired=(\d+) active=(\d+) mac_ok=(\d+) mac_fail=(\d+) drops=(\d+)',text)
        if not rows:raise AssertionError('missing live status: '+text)
        version,channel,paired,active,ok,failed,drops=rows[-1]
        return dict(version=version,channel=int(channel),paired=int(paired),active=int(active),
                    mac_ok=int(ok),mac_fail=int(failed),drops=int(drops))
    try:
        link.open();command('',.1);initial=status() # delimit any ROM-tool input residue
        assert initial['version']=='0.1.0-dev.2' and initial['channel']==8
        assert not initial['paired'] and not initial['active'],'requires unpaired idle lab fixture'
        checks.append('live firmware identity and unpaired idle state')
        payload=('CARDPUTER_NATIVE_TEST_'+'1234567890'*8)[:96]
        assert len(payload)==96
        started=command('say '+payload)
        assert 'CHAT_SUBMIT seq=' in started
        assert status()['active']==1
        duplicate=command('say DO_NOT_QUEUE_ANOTHER_MESSAGE')
        assert 'CHAT_SUBMIT' not in duplicate
        checks.append('96-byte submission and single-outstanding-message bound')
        timed_out=collect(6.0)
        assert 'CHAT_UNCONFIRMED seq=' in timed_out
        after_timeout=status();assert not after_timeout['active'] and not after_timeout['paired']
        checks.append('missing peer reaches unconfirmed state and returns idle')
        for channel in ('0','14','-1'):
            assert 'CHAT_ERROR channel rejected' in command('channel '+channel)
            assert status()['channel']==8
        checks.append('invalid channel requests leave channel8 unchanged')
        assert 'CHAT_ERROR line too long' in command('x'*140)
        command('pair');final=status()
        assert not final['active'] and not final['paired'] and final['drops']==initial['drops']
        checks.append('oversized serial input rejected; discovery reset remains responsive')
        report={'passed':True,'port':args.port,'checks':checks,'initial':initial,'final':final,
                'firmware_sha256':hashlib.sha256((ROOT/'work/espnow-chat-cardputer-build/cardputer-chat/firmware.bin').read_bytes()).hexdigest(),
                'physical_cardputer_tested':True,'mac_success_is_not_application_ack':True,
                'physical_lcd_appearance_qualified':False,'x1060_app_exchange_tested':False,
                'flashed_by_this_test':False,'x1060_modified':False}
        (out/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    finally:
        if link.is_open:link.close()
        (out/'serial.txt').write_bytes(raw)


if __name__=='__main__':main()
