"""PC-only PlatformIO source composition; no device Python."""
Import("env")
from pathlib import Path
project=Path(env.subst("$PROJECT_DIR"))
env.BuildSources(env.subst("$BUILD_DIR")+"/protocol",str(project.parent),src_filter=["+<link.c>","+<status_auth.c>","+<receiver.c>","+<session_wire.c>","+<control.c>","+<mode_wire.c>","+<library_wire.c>","+<library_client.c>"])
env.BuildSources(env.subst("$BUILD_DIR")+"/hash",str(project.parents[2]/"native"),src_filter=["+<sha256.c>"])

import json
version=(project/"VERSION").read_text().strip()
output=Path(env.subst("$BUILD_DIR"))/"generated"
output.mkdir(parents=True,exist_ok=True)
(output/"remote_version.h").write_text("#define XW_REMOTE_VERSION "+json.dumps(version)+"\n")
env.Append(CPPPATH=[str(output)])
