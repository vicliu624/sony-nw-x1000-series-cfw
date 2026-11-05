.syntax unified
.arm
.text
.align 2
/* Existing capture-arg2 getpid shim carries op/r0/r1/r2 as r0/r1/r2/r7.
 * Preserve the original callee-saved r7 and incoming native return address. */
.macro RF_ENTRY name, operation
.global \name
.type \name,%function
\name:
 push {r7,lr}
 mov r7,r2
 mov r2,r1
 mov r1,r0
 mov r0,#\operation
 bl xw_native_rf_request
 pop {r7,pc}
.size \name,.-\name
.endm
RF_ENTRY xw_native_rf_power_on,1
RF_ENTRY xw_native_rf_search,2
RF_ENTRY xw_native_rf_prepare_connect,3
RF_ENTRY xw_native_rf_connect,4
RF_ENTRY xw_native_rf_prepare_wps,5
RF_ENTRY xw_native_rf_pin,6
RF_ENTRY xw_native_rf_vista_pin,7
RF_ENTRY xw_native_rf_pbc,8
.global xw_native_rf_worker_entry
.type xw_native_rf_worker_entry,%function
xw_native_rf_worker_entry:
 push {r4,lr}
 mov r4,r0
 mov r0,#9
 bl xw_native_rf_request
 mov r0,r4
 pop {r4,lr}
 b xw_native_stock_worker
.size xw_native_rf_worker_entry,.-xw_native_rf_worker_entry
.global xw_native_rf_queue_entry
.type xw_native_rf_queue_entry,%function
xw_native_rf_queue_entry:
 push {r4,r5,r6,r7,r8,lr}
 mov r4,r0
 mov r5,r1
 mov r6,r2
 ldr r7,[r1,#4]
 mov r1,r7
 mov r2,#0
 mov r0,#10
 bl xw_native_rf_request
 mov r0,r4
 mov r1,r5
 mov r2,r6
 pop {r4,r5,r6,r7,r8,lr}
 b xw_native_stock_router
.size xw_native_rf_queue_entry,.-xw_native_rf_queue_entry
RF_ENTRY xw_native_rf_cleanup_poweroff,13
RF_ENTRY xw_native_rf_cleanup_disconnect,14
RF_ENTRY xw_native_rf_cleanup_cancel_connect,15
RF_ENTRY xw_native_rf_cleanup_cancel_wps,16
.global xw_native_rf_dispatch_entry
.type xw_native_rf_dispatch_entry,%function
xw_native_rf_dispatch_entry:
 push {r4,r5,r6,lr}
 mov r4,r0
 ldr r5,[r0,#4]
 bl xw_native_stock_dispatch
 mov r6,r0
 mov r0,#12
 mov r1,r5
 bl xw_native_rf_request
 mov r0,r6
 pop {r4,r5,r6,pc}
.size xw_native_rf_dispatch_entry,.-xw_native_rf_dispatch_entry
.global xw_native_activation_entry
.type xw_native_activation_entry,%function
xw_native_activation_entry:
 push {r4,r5,r6,lr}
 mov r4,r0
 bl xw_native_stock_activation
 mov r6,r0
 mov r0,#18
 mov r1,r4
 mov r2,r6
 bl xw_native_rf_request
 mov r0,r6
 pop {r4,r5,r6,pc}
.size xw_native_activation_entry,.-xw_native_activation_entry
.section .note.GNU-stack,"",%progbits
