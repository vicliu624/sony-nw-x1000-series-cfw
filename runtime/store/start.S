.syntax unified
.arm
.global _start
.type _start,%function
_start:
    mov r4, sp
    bic sp, sp, #7
    mov r0, r4
    bl hb_store_start
    b .
.section .note.GNU-stack,"",%progbits
