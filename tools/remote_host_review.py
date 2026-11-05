"""PC-side identity check for the source-built native five-mode host."""
from review_managed_remote_profile import receipt,artifact

def mode_host(path):
 path,host=receipt(path)
 if not host.get('passed') or not host.get('analysis_only') or not host.get('native_prepare') or not host.get('play_mode_read_supported'):
  raise ValueError('A fresh native mode-reader host review is required')
 library=path.parent/'libx1000-player-analysis.so'
 artifact(library,host['library_sha256'],host['library_bytes'])
 return path,host
