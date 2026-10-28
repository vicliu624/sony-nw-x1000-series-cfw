# SDK preview artwork

sdk-counter.png and sdk-canvas.png are actual PC-side C framebuffer renders from
the maintained SDK examples, using synthetic touch/timing and isolated PC files.
They are not photographs or evidence of physical device qualification.

Regenerate from Linux/WSL with the SDK host dependencies:

```sh
python tools/render_sdk_gallery.py
```

The tool creates temporary output under work/sdk-gallery, then replaces only the
two public website images and their sdk-previews.json provenance manifest.
The manifest records image/source hashes and the exact synthetic event script.
No identity, account, original Sony binary, ROM or personal state is used.
