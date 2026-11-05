from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"tools"))
from sdk_build import build
if __name__ == "__main__":
    build(Path(__file__).resolve().parent)
