# EBook reader

Source: runtime/apps/ebook, including the epub parser/layout subdirectory.
Build with tools/build_ebook_app.py; associated asset/encoding builders are separate.
The app-specific VERSION remains in its source directory.

The native reader handles external TXT and EPUB content with bounded parsing,
layout, image and encoding components. Fonts/resources and reading state belong
on user storage. Do not copy personal books into a version-controlled fixture or
treat text inside sample books as project documentation.

Parser/model checks and safe ARM CLI/build checks are offline evidence. Physical
page interaction, font rendering, USB stop and sleep/wake require app-specific
reports. Keep the original display and storage ownership rules; do not infer this
app is qualified from another app's successful terminal session.
