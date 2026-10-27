/* Japanese 1.11 analysis-only leaf adapters. No BL/BLX or new C stack frames.
   Calls reuse Sony b0464's established frame and the original libc PLT. */
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
    beq hb_feedback
    ldr r0, =hb_frontend_name
    mov r1, #0             /* O_RDONLY */
    adr lr, .Lopened
    ldr pc, =0xe09c        /* original open@plt */
.Lopened:
    cmp r0, #0
    blt hb_feedback
    mov r5, r0
    mov r0, r5
    mov r1, sp
    mov r2, #16
    adr lr, .Lident
    ldr pc, =0xe48c
.Lident:
    cmp r0, #16
    bne .Lbad_header
    ldr r0, [sp]
    ldr ip, =0x464c457f
    cmp r0, ip
    bne .Lbad_header
    ldr r0, [sp, #4]
    bic r0, r0, #0xff000000 /* ignore OSABI byte */
    ldr ip, =0x00010101     /* ELF32, little endian, version 1 */
    cmp r0, ip
    bne .Lbad_header
    mov r0, r5
    mov r1, sp
    mov r2, #16
    adr lr, .Lmachine
    ldr pc, =0xe48c
.Lmachine:
    cmp r0, #16
    bne .Lbad_header
    ldr r0, [sp]
    ldr ip, =0x00280002     /* ET_EXEC, EM_ARM */
    cmp r0, ip
    bne .Lbad_header
    ldr r0, [sp, #4]
    cmp r0, #1
    bne .Lbad_header
    mov r0, r5
    mov r1, sp
    mov r2, #16
    adr lr, .Lsizes
    ldr pc, =0xe48c
.Lsizes:
    cmp r0, #16
    bne .Lbad_header
    ldrh r0, [sp, #8]      /* e_ehsize */
    cmp r0, #52
    bne .Lbad_header
    ldrh r0, [sp, #10]     /* e_phentsize */
    cmp r0, #32
    bne .Lbad_header
    ldrh r0, [sp, #12]     /* e_phnum */
    cmp r0, #0
    beq .Lbad_header
    mov r0, r5
    mov r1, sp
    mov r2, #4
    adr lr, .Llast_header
    ldr pc, =0xe48c
.Llast_header:
    cmp r0, #4
    bne .Lbad_header
    mov r0, r5
    adr lr, .Lclosed
    ldr pc, =0xd6f4
.Lclosed:
    cmp r0, #0
    bne hb_feedback
    mov r0, #0
    str r0, [sp]
    str r0, [sp, #4]
    str r0, [sp, #8]
    mov r0, #1
    str r0, [sp, #12]      /* restore original APF lookup local */
    ldr r1, =hb_frontend_name
    ldr pc, =0xb04f8
.Lbad_header:
    mov r0, r5
    adr lr, .Lbad_closed
    ldr pc, =0xd6f4
.Lbad_closed:
    b hb_feedback
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
    bne hb_feedback_epilogue
    cmp r5, #0
    bne hb_feedback
    mov r0, #0
hb_feedback_epilogue:
    add sp, sp, #16    /* displaced original epilogue */
    pop {r4, r5, r6, pc}
.size hb_switch_return, .-hb_switch_return
/* This variant is not promoted into the diagnostic UPG. The existing
   switcher owns the frame. Queue arguments use its 16-byte local area. */
.global hb_feedback
hb_feedback:
    ldr r0, =0x2010e
    mov r1, #0
    ldr r2, =745
    mov r3, #0
    str r3, [sp]
    adr lr, hb_feedback_done
    ldr pc, =0xa57f0
hb_feedback_done:
    mov r0, #0
    b hb_feedback_epilogue

/* Preserve the stock descriptor base for every existing message ID.
   The original arithmetic adds 48 * index after this adapter. */
.global hb_message_index
hb_message_index:
    ldr ip, =745
    cmp r0, ip
    moveq r0, #22          /* existing no-video popup interaction rules */
    bxeq lr
    cmp r0, #181          /* displaced original instruction, flags matter */
    ldr pc, =0x28114
.global hb_message_descriptor
hb_message_descriptor:
    ldr ip, =745
    cmp r5, ip
    ldreq r4, =hb_error_descriptor - (22 * 48)
    ldrne r4, =0x4eb99c
    ldr pc, =0x281e4
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

.section .rodata
.align 2
.global hb_error_descriptor
hb_error_descriptor:
    .word 745,0,1,0,0,hb_error_text,0,0,0,0,0,2
.global hb_error_text
hb_error_text:
    .hword 72,111,109,101,98,114,101,119,32,117,110,97,118,97,105,108,97,98,108,101,46,10,67,104,101,99,107,32,72,79,77,69,66,82,69,87,32,102,111,108,100,101,114,46,0
