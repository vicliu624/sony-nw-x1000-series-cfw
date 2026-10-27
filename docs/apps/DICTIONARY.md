# Offline dictionary

Source: runtime/apps/dictionary. Builder: tools/build_dictionary_app.py; data is
prepared separately with tools/build_dictionary_data.py. The application has its
own VERSION file. Native input, lookup and UI are separate from dictionary assets.

Preserve source/data provenance and licenses. Dictionaries, fonts and user state
belong on visible storage. Multilingual entries are product data, not English-only
documentation. Do not remove Sony input dictionaries merely because this separate
application exists; their original dependencies are different.

Current builds/checks establish native implementation and bounded offline behavior.
Hardware lifecycle and physical input/rendering remain separately qualified.
