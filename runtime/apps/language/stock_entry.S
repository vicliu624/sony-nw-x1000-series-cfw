.syntax unified
.arch armv5te
.arm
.text
.global hb_language_getter
.type hb_language_getter,%function
/* Replace only the BL at3a25c, not the generic settings getter. */
hb_language_getter:
 push {r4,r5,r6,lr}
 mov r4,r1
 mov r5,r2
 bl hb_original_getter
 mov r6,r0
 mov r0,r4
 mov r1,r5
 mov r2,r6
 bl hb_language_after_read
 mov r0,r6
 pop {r4,r5,r6,pc}
.size hb_language_getter,.-hb_language_getter
/* Existing generic getter is unmodified; its own frame and return remain. */
.global hb_original_getter
.type hb_original_getter,%function
hb_original_getter:
 ldr pc,=0xb1cf8
.size hb_original_getter,.-hb_original_getter
.section .note.GNU-stack,"",%progbits
