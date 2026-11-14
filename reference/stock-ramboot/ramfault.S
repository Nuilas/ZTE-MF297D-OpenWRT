/* GPL-2.0-only. Diagnostic replacement for this Image's fatal die() only.
 * x1 points to Linux 6.18 arm64 pt_regs. No stack, allocation or flash access.
 * Save ESR, PC low word and actual opcode to our DT-reserved trace pages,
 * then invoke standard PSCI reset. It never runs on a healthy kernel path.
 */
.text
.balign 4
.global mf_fault_start
mf_fault_start:
    mrs x10, esr_el1
    ldr x11, [x1, #256]
    mov w14, #-1
    ldr x12, .Limage_base
    cmp x11, x12
    b.lo .Lno_opcode
    ldr x13, .Limage_end
    cmp x11, x13
    b.hs .Lno_opcode
    ldr w14, [x11]
.Lno_opcode:
    ldr w4, .Lhead
    ldr x15, .Llinear_bias
    mov w9, #12
.Lrecord:
    add x5, x4, x15
    add x6, x5, #4064
    str w9, [x6, #8]
    str w10, [x6, #12]
    str w11, [x6, #16]
    str w14, [x6, #28]
    ldr w4, [x5]
    cbnz w4, .Lrecord
    dsb sy
    movz x0, #9
    movk x0, #0x8400, lsl #16
    smc #0
.Lwait:
    wfi
    b .Lwait
.balign 8
.Limage_base: .quad 0xffffffc080000000
.Limage_end: .quad 0xffffffc0816b0000
.Llinear_bias: .quad 0xffffff7fc0000000
.global mf_fault_head_literal
mf_fault_head_literal:
.Lhead: .word 0
