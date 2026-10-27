# Offline diagnostic probes

`probe_home_feedback_popup.py` is a PC-only reverse-engineering harness, not player code or a firmware builder. It uses candidate5, original SDK templates and virtual file/libc/display/allocation interfaces. `DEBUG-pool-retain` instrumentation stays here for reproduction; it is never packaged.

Use `tools/test_home_feedback_popup_pool.py` for the positive/negative lifecycle regression. Direct probe runs require a new `--output work/...` path. `--native-image-manager` enables the original image-manager initialization; omitting it deliberately retains the incomplete-initialization comparison. The old tools/probe_home_feedback_popup.py path delegates here.

Historical reports retain their own source hashes; the exact prior source is saved under work/popup-pool-diagnosis/source-before-cleanup.py. No existing candidate was changed by this cleanup.

`capture_popup_image.py --prepare-cache --output work/<new>` inspects the live text cache through the original cache-preparation API. Its default20M instruction budget is finite; check cache_preparation_completed, not just whether pixels changed. It intentionally stops before teardown. The ordinary regression now prepares and paints the cache before each positive-case teardown.
