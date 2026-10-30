.syntax unified
.arm
.text
.align 2
/* Preserve incoming session/cancel words as C arguments; ordinary getpid
 * callers may supply arbitrary register values and dispatch must ignore them. */
.global getpid
.type getpid,%function
getpid:
 mov r2, lr
 mov r3, r7
 b xw_host_pid_dispatch
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
