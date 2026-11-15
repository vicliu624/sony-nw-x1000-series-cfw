# Offline diagnostic probes

`probe_home_feedback_popup.py` reproduces the historical popup-pool experiment
with original SDK templates and virtual file, libc, display and allocation
interfaces. Supply the retained candidate5 UPG with `--package` and its
resource-feedback ELF receipt with `--feedback-build`. The probe checks the exact
package hash. Use a new `--output work/...` path for the reports.

`tools/test_home_feedback_popup_pool.py` takes the same inputs and runs one
incomplete-initialization case and two initialized cases. In a direct probe run,
`--native-image-manager` enables the original initialization. Historical
reports retain their own source hashes.

`capture_popup_image.py` takes the same inputs and stops before teardown.
`--prepare-cache` calls the original cache preparation API. Inspect
`cache_preparation_completed` in its report before interpreting bitmap data.
For checks on the current composition, use the
[Homebrew regression guide](../../docs/REGRESSION.md#homebrew-entry-and-error-resources).
