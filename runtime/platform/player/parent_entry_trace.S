/* Explicit diagnostic capsules only. Not linked into ordinary firmware.
 * A paired observer may inspect the saved frame while this call is active.
 * No pointer survives the call; arguments, LR, volatile registers and flags
 * are restored before executing the displaced original instruction.
 */
.syntax unified
.arch armv5te
.arm
.text
.macro observe stage
    push {r0-r3,r6,r7,ip,lr}
    mrs r2, cpsr
    push {r2,r3}
    add r1, sp, #8
    ldr r0, =(0x48425000+\stage)
    bl parent_trace_getpid
    pop {r2,r3}
    msr cpsr_f, r2
    pop {r0-r3,r6,r7,ip,lr}
.endm
.global parent_trace_launch
.type parent_trace_launch,%function
parent_trace_launch:
    observe 1
    mov r0,#4
    ldr pc,=0xb0464
.global parent_trace_lookup
.type parent_trace_lookup,%function
parent_trace_lookup:
    observe 2
    mov r0,r6
    ldr pc,=0xb04fc
.global parent_trace_lookup_return
.type parent_trace_lookup_return,%function
parent_trace_lookup_return:
    observe 3
    cmp r0,#0
    ldr pc,=0xb0508
.global parent_trace_switch
.type parent_trace_switch,%function
parent_trace_switch:
    observe 4
    push {r4,lr}
    bl parent_trace_original_switch
    observe 5
    pop {r4,pc}
.ltorg
.section .note.GNU-stack,"",%progbits
