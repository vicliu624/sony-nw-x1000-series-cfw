.syntax unified
.arm
.global _start
.type _start,%function
_start:
 mov r0,sp
 bl hb_entry
 swi 0x900001
 b .
.section .note.GNU-stack,"",%progbits
