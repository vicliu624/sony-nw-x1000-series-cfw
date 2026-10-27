.syntax unified
.arm
.global _start
_start:
    bl hb_stat_selftest
    swi 0x900001
1:  b 1b
.section .note.GNU-stack,"",%progbits
