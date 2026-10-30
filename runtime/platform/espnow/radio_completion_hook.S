/* Replace original d51c management-free wrapper, preserving original ARM1360.
 * Task3 MAC completion caller LR=3a13 has status/raw at caller SP+8/+12.
 * Other matching tracked releases are pre-MAC rejection (status2, raw0).
 * Publish completion only after original free returns; return its original r0. */
.syntax unified
.thumb
.text
.align 2
.global xnow_radio_completion_entry
.type xnow_radio_completion_entry,%function
.thumb_func
xnow_radio_completion_entry:
 push {r4,r5,r6,lr}
 movs r4,r0
 mov r5,lr
 ldr r3,=0x3a13
 cmp r5,r3
 bne 1f
 ldr r1,[sp,#24]
 ldr r2,[sp,#28]
 b 2f
1:
 movs r1,#2
 movs r2,#0
2:
 bl xnow_radio_tx_observe
 movs r0,r4
 ldr r3,=0x1360
 blx r3
 movs r6,r0
 movs r0,r4
 bl xnow_radio_tx_released
 movs r0,r6
 pop {r4,r5,r6,pc}
.size xnow_radio_completion_entry,.-xnow_radio_completion_entry
.section .note.GNU-stack,"",%progbits
