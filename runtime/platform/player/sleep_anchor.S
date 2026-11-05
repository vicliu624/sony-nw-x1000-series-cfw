.syntax unified
.arm
.text
.align 2
.global xw_native_sleep_ack
.type xw_native_sleep_ack,%function
xw_native_sleep_ack:
 push {r1,r2,r3,lr}
 sub r0,lr,#4
 bl xw_native_sleep_request
 ldr r1,=0x58575052
 cmp r0,r1
 pop {r1,r2,r3,lr}
 moveq r0,#0
 bxeq lr
 ldr pc,=0xb03e8
.size xw_native_sleep_ack,.-xw_native_sleep_ack
.ltorg
#ifdef XW_SLEEP_RESTORE_ANCHOR
.space 20
.global xw_native_sleep_restore
.type xw_native_sleep_restore,%function
xw_native_sleep_restore:
 push {r4,lr}
 bl xw_native_stock_restore
 mov r4,r0
 mov r1,r0
 mov r0,#19
 bl xw_native_sleep_request
 mov r0,r4
 pop {r4,pc}
.size xw_native_sleep_restore,.-xw_native_sleep_restore
#endif
