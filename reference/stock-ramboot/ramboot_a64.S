/* GPL-2.0-only. Position independent, stackless diagnostic entry shim.
 * Writes owned RAM, restores Image header and pets the documented watchdog.
 * x0 = DTB. No flash access or watchdog enable/timeout changes.
 */
.text
.balign 4
.global ramboot_a64
ramboot_a64:
.Lentry:
    adr x20, .Lentry
    sub x20, x20, #512
    mov x19, x0
    mov w9, #5
    mov w10, wzr
    mov w11, wzr
    bl mark
    mrs x10, CurrentEL
    add x12, x20, #2048
    cmp x10, #8
    b.eq setup_el2
    msr vbar_el1, x12
    isb
    mrs x11, sctlr_el1
    b configured
setup_el2:
    msr vbar_el2, x12
    isb
    mrs x11, sctlr_el2
configured:
    bl mark
    /* Read-only coherency diagnostic. VBAR is already installed if this
     * implementation-defined register is trapped by secure firmware. */
    mrs x17, S3_1_C15_C2_1
    str x17, [x20, #440]
    bl clean_dcache_all
    /* Standard read-only PSCI AFFINITY_INFO: CPU1, lowest affinity level. */
    movz x0, #4
    movk x0, #0x8400, lsl #16
    mov x1, #1
    mov x2, xzr
    mov x3, xzr
    smc #0
    str w0, [x20, #500]
    mrs x17, cntvct_el0
    str x17, [x20, #480]
    mrs x17, cntfrq_el0
    str w17, [x20, #488]
    bl watchdog_ping
    /* Check the entire patched Image with caches/MMU still off.
     * Nibble table lives at control+1536, outside code and exception vectors. */
    ldr x12, [x20, #392]
    ldr w9, [x20, #460]
    bl crc32
    mvn w10, w0
    str w10, [x20, #452]
    ldr w11, [x20, #456]
    mov w9, #9
    bl mark
    cmp w10, w11
    b.ne crc_bad
    mov x12, #0x45000000
    ldr w9, [x20, #464]
    bl crc32
    mvn w10, w0
    str w10, [x20, #472]
    ldr w11, [x20, #468]
    mov w9, #11
    bl mark
    cmp w10, w11
    b.ne crc_bad
    mrs x16, cntvct_el0
    ldr x17, [x20, #480]
    sub x16, x16, x17
    mov x17, #1000
    mul x16, x16, x17
    ldr w17, [x20, #488]
    udiv x16, x16, x17
    lsl w16, w16, #8
    ldr w17, [x20, #448]
    orr w16, w16, w17
    str w16, [x20, #448]
    ldr x12, [x20, #392]
    ldr x13, [x20, #400]
    str x13, [x12]
    ldr x13, [x20, #408]
    str x13, [x12, #32]
    dsb sy
    /* The warm handoff reuses stock kernel physical text addresses. Remove
     * stale ARM32 instruction-cache lines before Linux enables its caches. */
    ic iallu
    dsb sy
    isb
    ldr x16, [x20, #416]
    mov x0, x19
    mov x1, xzr
    mov x2, xzr
    mov x3, xzr
    bl watchdog_ping
    /* Execute the Image's original first two calls, with checkpoints. The
     * target addresses are decoded and validated from the supplied Image.
     * x19 (MMU state) and x21 (DTB) retain Linux's original meanings. */
    ldr x16, [x20, #424]
    blr x16
    mov w9, #7
    ldr w10, [x20, #472]
    ldr w11, [x20, #452]
    bl mark
    ldr x16, [x20, #432]
    blr x16
    mov w9, #8
    ldr w10, [x20, #472]
    ldr w11, [x20, #452]
    bl mark
    ldr x16, [x20, #416]
    add x16, x16, #8
    br x16
crc_bad:
    mov w9, #10
    bl mark
    b reset
crc32:
    mov x18, x30
    add x13, x20, #1536
    mov w0, #-1
crc_loop:
    tst w9, #0xfffff
    b.ne crc_no_ping
    bl watchdog_ping
crc_no_ping:
    ldrb w14, [x12], #1
    eor w0, w0, w14
    and w15, w0, #15
    ldr w15, [x13, w15, uxtw #2]
    eor w0, w15, w0, lsr #4
    and w15, w0, #15
    ldr w15, [x13, w15, uxtw #2]
    eor w0, w15, w0, lsr #4
    subs w9, w9, #1
    b.ne crc_loop
    ret x18
watchdog_ping:
    /* Stock DT watchdog base=0x0b017000; KPSS WDT_RST=+4. Same as
     * qcom_wdt_ping(). Does not change enable, bark or bite registers. */
    movz x16, #0x7004
    movk x16, #0xb01, lsl #16
    mov w17, #1
    str w17, [x16]
    dsb sy
    ldr w17, [x16, #4]
    str w17, [x20, #504]
    ret
mark:
    ldr w4, [x20, #304]
1:  add x6, x4, #4064
    /* Relocation is complete here; descriptor tail can hold extra metadata. */
    ldr w17, [x20, #492]
    str w17, [x4, #4000]
    ldr w17, [x20, #496]
    str w17, [x4, #4004]
    movz w17, #0x4558
    movk w17, #0x4d46, lsl #16
    str w17, [x4, #4008]
    ldr w17, [x20, #500]
    str w17, [x4, #4012]
    ldr w17, [x20, #504]
    str w17, [x4, #4016]
    ldr w17, [x20, #508]
    str w17, [x4, #4020]
    ldr x17, [x20, #440]
    str x17, [x4, #4024]
    ldr w17, [x20, #476]
    str w17, [x4, #4060]
    str w9, [x6, #8]
    str w10, [x6, #12]
    str w11, [x6, #16]
    ldr w17, [x20, #448]
    str w17, [x6, #28]
    ldr w4, [x4]
    cbnz w4, 1b
    dsb sy
    ret
exception:
    mrs x10, CurrentEL
    cmp x10, #8
    b.eq exception_el2
    mrs x10, esr_el1
    mrs x11, elr_el1
    mrs x14, far_el1
    b exception_record
exception_el2:
    mrs x10, esr_el2
    mrs x11, elr_el2
    mrs x14, far_el2
exception_record:
    mov w9, #6
    bl mark
    ldr w4, [x20, #304]
2:  add x6, x4, #4064
    str w14, [x6, #28]
    ldr w4, [x4]
    cbnz w4, 2b
    dsb sy
reset:
    movz x0, #9
    movk x0, #0x8400, lsl #16
    smc #0
3:  wfi
    b 3b
/* Physical control page +2048; 16 exception slots, each 128 bytes. */
.org 1024
.space 64 /* CRC nibble table installed by the ARM32 preparation module. */
/* Cortex-A53, legacy CCSIDR (no FEAT_CCIDX). Clean/invalidate each data
 * cache level by set/way before checking the relocated Image. If stale dirty
 * lines overwrite the Image, the subsequent full CRC rejects that handoff.
 * Based on the ARMv8 ARM algorithm also used by U-Boot armv8/cache.S.
 * x19 (DTB) and x20 (control) are preserved; no stack or memory allocation. */
clean_dcache_all:
    mov x18, x30
    dsb sy
    mrs x0, clidr_el1
    ubfx w3, w0, #24, #3
    lsl w3, w3, #1
    mov w10, wzr
    mov w14, wzr
    cbz w3, cache_done
cache_level:
    add w2, w10, w10, lsr #1
    lsr w1, w0, w2
    and w1, w1, #7
    cmp w1, #2
    b.lt cache_next
    msr csselr_el1, x10
    isb
    mrs x1, ccsidr_el1
    and w2, w1, #7
    add w2, w2, #4
    ubfx w4, w1, #3, #10
    clz w5, w4
    ubfx w6, w1, #13, #15
cache_way:
    mov w7, w6
cache_set:
    lsl w9, w4, w5
    lsl w8, w7, w2
    orr w9, w9, w8
    orr w9, w9, w10
    dc cisw, x9
    add w14, w14, #1
    subs w7, w7, #1
    b.ge cache_set
    subs w4, w4, #1
    b.ge cache_way
    dsb sy
cache_next:
    add w10, w10, #2
    cmp w10, w3
    b.lt cache_level
cache_done:
    msr csselr_el1, xzr
    dsb sy
    ic iallu
    dsb sy
    isb
    str w14, [x20, #508]
    ret x18
.org 1536
.rept 16
    b exception
    .space 124
.endr
