/* Generic guest continuation stand-ins, not original GUI/APF implementations. */
.syntax unified
.arch armv5te
.arm
.section .parent_pid_stub,"ax",%progbits
    b getpid
.section .parent_resume_stubs,"ax",%progbits
.org 0x464
    bx lr
.org 0x4fc
    bx lr
.org 0x508
    bx lr
.section .parent_switch_stub,"ax",%progbits
    b parent_test_native_switch
.section .note.GNU-stack,"",%progbits
