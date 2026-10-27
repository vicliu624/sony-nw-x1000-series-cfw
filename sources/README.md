# Provenance and local evidence

Keep public dependency/download provenance, pinned revisions, licenses and source
manifests in version control. Generated native replay reports, device-specific
snapshots and workflow results are local evidence and are ignored by default.
The explicit .gitignore exceptions identify the maintained provenance manifests.

Do not edit an old report's hashes after a source move. Rerun the applicable check
to produce current evidence, or preserve the old report as historical. Private
session material belongs in .tmp or work, never in a public manifest. Original
Sony archives/binaries stay under ignored firmware or work.
