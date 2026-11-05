.syntax unified
.file "host_pid.S"
.arm
.text
.align 2
/* Preserve incoming session/cancel words as C arguments; ordinary getpid
 * callers may supply arbitrary register values and dispatch must ignore them. */
.global getpid
.type getpid,%function
getpid:
#ifdef XW_PLAYER_PARENT_TRACE
#ifndef XW_PLAYER_CAPTURE_ARG2
#error Parent observer requires paired argument capture
#endif
 /* Diagnostic six-argument dispatcher: fifth is incoming r2; sixth is the
  * exact entry SP. A capsule's saved register frame must be entry-SP+8.
  * Ordinary builds retain the original four/five-argument implementation. */
 push {r2,r3,ip,lr}
 add ip,sp,#16
 str ip,[sp,#4]
 mov r2,lr
 mov r3,r7
 bl xw_host_pid_dispatch
 pop {r1,r2,r3,pc}
#elif defined(XW_PLAYER_CAPTURE_ARG2)
 /* Optional analysis ABI: preserve the original third native argument as a
  * fifth C argument. Its 8-byte frame preserves incoming alignment. The default four-argument
  * dispatcher may ignore it; a future paired prepare dispatcher can inspect
  * it only after qualifying its callsite. No argument pointer is read here. */
 push {r2, lr}
 mov r2, lr
 mov r3, r7
 bl xw_host_pid_dispatch
 pop {ip, pc}
#else
 mov r2, lr
 mov r3, r7
 b xw_host_pid_dispatch
#endif
.size getpid,.-getpid
.hidden xw_host_pid_dispatch
.global xw_host_getpid_oabi
.hidden xw_host_getpid_oabi
.type xw_host_getpid_oabi,%function
xw_host_getpid_oabi:
 swi 0x900014
 bx lr
.size xw_host_getpid_oabi,.-xw_host_getpid_oabi
.section .note.GNU-stack,"",%progbits
