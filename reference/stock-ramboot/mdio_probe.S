/* Board-specific RAM diagnostic, inserted after MDIO busy wait and mode read.
 * x0=mapped MDIO base, w3=old mode, w20=PHY, w21=register.
 * Preserve x0, x19-x30 and SP. No calls or new MDIO transactions.
 */
.text
.balign 4
.global mdio_probe_start
mdio_probe_start:
    mov w11, w3
    ldr w16, .Lforce
    cbz w16, 1f
    mov w3, w16
1:  and w3, w3, #0xfffffeff
    ldr w9, [x0, #0x4c]
    ldr w17, [x0, #0x50]
    ldr w12, .Lhead
    ldr x13, .Lbias
    movz w10, #0x494f
    movk w10, #0x4d44, lsl #16
2:  add x14, x12, x13
    str w11, [x14, #4036]
    str w20, [x14, #4040]
    str w21, [x14, #4044]
    str w3, [x14, #4048]
    str w9, [x14, #4052]
    str w17, [x14, #4056]
    ldr w8, [x14, #4084]
    add x8, x8, x13
    ldr w8, [x8, #476]
    str w8, [x14, #4060]
    str w10, [x14, #4032]
    add x15, x14, #4032
    dc cvac, x15
    ldr w12, [x14]
    cbnz w12, 2b
    dsb sy
.global mdio_return_branch
mdio_return_branch:
    .word 0 /* Loader patches a direct B back to original mode write path. */
.balign 8
.Lbias: .quad 0xffffff7fc0000000
.global mdio_head_literal
mdio_head_literal:
.Lhead: .word 0
.global mdio_force_literal
mdio_force_literal:
.Lforce: .word 0
