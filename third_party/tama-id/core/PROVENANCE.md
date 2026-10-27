The tc_* sources are unmodified copies from mameise/Paramix-Studio,
commit 3676ecd5c49e9e40b118d59dde43cd0bc30fc4e6, emu/src/core.
https://github.com/mameise/Paramix-Studio/tree/3676ecd5c49e9e40b118d59dde43cd0bc30fc4e6/emu/src/core

The interpreter derives from maragotchi/tamaemu under GPL-3.0.
The included LICENSE is the upstream GPL version 3 text.
tc_jit.c is retained as source but is NOT compiled/enabled on ARMv5.
Compile only the color core with cpu_reset/cpu_step symbol prefixes to
coexist with the P1 TamaLIB core. TC_HOST selects normal C memory functions;
it does not make the ARM binary depend on a desktop OS runtime.

A918 platform, model profile overrides, storage serialization, rendering,
time budget, and controls are in games/src/color* and app.c.
The original iD profile follows maragotchi/tamaemu device.c at commit
79e19b65a1c970b9e1cd0b58ee6e929507257234 (4MiB, bottom boot, sleep 0xEFC,
18.432 MHz OSC3, debug strap low, no GPIO IR). No IR connection is implemented.
