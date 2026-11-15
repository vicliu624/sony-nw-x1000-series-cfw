"""Build this application without device access."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"tools"))
from native_app_build import build

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    build(Path(__file__).resolve().parent, output=parser.parse_args().output)
