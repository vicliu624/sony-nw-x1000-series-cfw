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
/* Tail branch at ec46c, after original text-manager frame is restored. */
.global hb_language_wording
.type hb_language_wording,%function
hb_language_wording:
 b hb_language_external_load
.size hb_language_wording,.-hb_language_wording
.global hb_language_cleanup_entry
.type hb_language_cleanup_entry,%function
hb_language_cleanup_entry:
 b hb_language_cleanup
.size hb_language_cleanup_entry,.-hb_language_cleanup_entry
.global hb_language_stock_cleanup
.type hb_language_stock_cleanup,%function
hb_language_stock_cleanup:
 push {r4,r5,lr}
 ldr pc,=0xec874
.size hb_language_stock_cleanup,.-hb_language_stock_cleanup
.section .note.GNU-stack,"",%progbits
