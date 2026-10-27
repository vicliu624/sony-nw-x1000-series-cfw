"""Compatibility entry for the offline popup diagnostic harness."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).parent/'debug/probe_home_feedback_popup.py'), run_name='__main__')
