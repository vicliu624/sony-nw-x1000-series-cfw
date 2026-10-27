.syntax unified
.arm
.global _start
.type _start,%function
_start:
 bl hb_arm_selftest
 swi 0x900001
 b .
.section .note.GNU-stack,"",%progbits
