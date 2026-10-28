"""Compatibility entry point; implementation lives with the app."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1]/"runtime/apps/language/build.py"),run_name="__main__")
