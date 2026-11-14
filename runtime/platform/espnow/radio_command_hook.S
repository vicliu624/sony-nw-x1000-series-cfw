.syntax unified
.arch armv5te
.thumb
#if defined(XNOW_RADIO_FRAME_TRANSACTIONS) || defined(XNOW_RADIO_INPLACE_WORD_COMMAND)
/* Reuse only the replaced stock command0x86 case, before the next case88f2. */
.section .word_hook,"ax",%progbits
#else
.section .text.xnow_word_command,"ax",%progbits
#endif
.align 2
.global xnow_radio_word_command_entry
.thumb_func
xnow_radio_word_command_entry:
    /* Original8078 has128-byte prologue; keep its SP aligned and unchanged.
     * r4=command body, r5=command header, r6=result, r7=dispatch context.
     * Original9a46 overwrites r0-r3 before use. Preserve r4/r5/r7 and SP;
     * the bulk profile publishes its command result through r6. */
    push {r0-r3,r7,lr}
    movs r0,r4
#if defined(XNOW_RADIO_FRAME_TRANSACTIONS) || defined(XNOW_RADIO_INPLACE_WORD_COMMAND)
    ldr r3,=xnow_radio_word_io
    blx r3
#else
    bl xnow_radio_word_io
#endif
#ifdef XNOW_RADIO_BULK_COMMANDS
    movs r6,r0
#endif
    pop {r0-r3,r7}
    pop {r3}
    mov lr,r3
#if defined(XNOW_RADIO_FRAME_TRANSACTIONS) || defined(XNOW_RADIO_INPLACE_WORD_COMMAND)
    b 0x82e8
#else
    ldr r3,=0x82e9
    bx r3
#endif
.ltorg
.section .note.GNU-stack,"",%progbits
