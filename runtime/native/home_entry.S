/* Japanese 1.11 analysis-only leaf adapters. No BL/BLX or new C stack frames.
   All service calls remain inside Sony's original b0464 function. */
.syntax unified
.arch armv5te
.arm
.text
.global hb_home_select
.type hb_home_select, %function
hb_home_select:
    ldr ip, =0x613e4c      /* e5f4 singleton + f6c0 field 0x20 */
    ldr ip, [ip]
    cmp ip, #1
    beq .Lten
    cmp ip, #2
    bne .Lreject
    cmp r2, #9
    blo hb_original_home
    beq .Llaunch
.Lreject:
    mov r0, #0
    bx lr
.Lten:
    cmp r2, #10
    blo hb_original_home
    bne .Lreject
.Llaunch:
    mov r0, #4
    ldr pc, =0xb0464
.size hb_home_select, .-hb_home_select

.global hb_original_home
.type hb_original_home, %function
hb_original_home:
    .word 0xe92d40f0      /* displaced native push {r4-r7,lr} */
    ldr pc, =0x737f0
.size hb_original_home, .-hb_original_home

/* b0464 has already established its original stack frame and saved selector
   in r4, APF context in r6. Other selectors retain the original default. */
.global hb_switch_name
.type hb_switch_name, %function
hb_switch_name:
    cmp r4, #4
    bne .Lexit
    cmp r6, #0
    beq .Lexit
    ldr r1, =hb_frontend_name
    ldr pc, =0xb04f8
.Lexit:
    ldr pc, =0xb04ec
.size hb_switch_name, .-hb_switch_name

.global hb_switch_args
.type hb_switch_args, %function
hb_switch_args:
    cmp r4, #4
    bne .Lexit
    ldr r1, [sp, #12]   /* original lookup result slot */
    mov ip, r1, lsr #16
    cmp ip, #3
    bne .Lwrong_class
    mov r0, r6
    mov r2, #0
    mov r3, #1             /* Native APF quit/relaunch: release session resources. */
    ldr pc, =0xb0554   /* original BL to APF change */
.Lwrong_class:
    mvn r5, #1         /* -2, adapter lookup validation failure */
    ldr pc, =0xb04c4   /* original diagnostic path */
.size hb_switch_args, .-hb_switch_args

.global hb_switch_return
.type hb_switch_return, %function
hb_switch_return:
    cmp r4, #4
    moveq r0, #0       /* Home state unchanged after request/error */
    add sp, sp, #16    /* displaced original epilogue */
    pop {r4, r5, r6, pc}
.size hb_switch_return, .-hb_switch_return
.global hb_code_end
hb_code_end:
.ltorg

.section .rodata
.align 2
.global hb_home_icons_10
hb_home_icons_10:
    .word 54,55,56,57,58,59,60,61,62,63,63
.global hb_home_icons_9
hb_home_icons_9:
    .word 62,54,56,57,58,59,63,61,60,63
.global hb_frontend_name
hb_frontend_name:
    .asciz "/contents/HOMEBREW/launcher/app"
.section .note.GNU-stack,"",%progbits
