"""Build this application without device access."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"tools"))
from sdk_services import compiler as sdk_compiler
sdk_run = sdk_compiler(Path(__file__).resolve().parent)
from native_app_build import build
if __name__=="__main__":build(Path(__file__).resolve().parent)
