"""Audit the final UPG's Homebrew icon wiring and exact preserved textures."""
import argparse
from pathlib import Path

from release_firmware import unpack, verify_homebrew_icon_root


def verify(path):
    _, parts = unpack(Path(path).read_bytes(), require_stock=False)
    verify_homebrew_icon_root(parts[3])
    print('Final UPG: both Homebrew entries use139, catalog140, accepted shadow pixels match; original Settings/textures preserved.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('firmware',type=Path);a=p.parse_args();verify(a.firmware)
