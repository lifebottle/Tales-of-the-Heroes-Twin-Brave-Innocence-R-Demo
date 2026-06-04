.headersize 0x8803000

// Change margin from 0x64 to 0x50
.org 0x08920580
li a1, 0x50

// Text speed: default frames-per-char 0x2 -> 0x1 (faster)
.org 0x08920cc4
li v0, 0x1

// Center the title-screen copyright strip
.org 0x08A623D4
.word 0x67


// Line Breaks in single-line chatbox text
// Init pen-Y
.org 0x08988F04
j   tb_nl_init
nop

// Newline dispatch
.org 0x08989020
j   tb_nl_check
nop

// Per-glyph Y store
.org 0x08989088
j   tb_nl_ystore
nop

// Code Cave
.org 0x08A0E820
tb_nl_init:
    li    s6, 0             // (orig) pen-X = 0
    sw    s4, 0x40(sp)      // (orig) save caller s4
    sw    zero, 0x24(sp)    // pen-Y = 0
    j     0x08988F0C
    nop

tb_nl_check:
    li    v0, 0x0A
    beq   a0, v0, tb_nl_break   // char == '\n' ?
    li    v0, 0x14              // [ds] v0 = 0x14 for next compare
    beq   a0, v0, tb_nl_color   // char == 0x14 (orig color-reset code) ?
    move  s0, a0                // [ds] s0 = char (needed by glyph build)
    j     0x0898902C            // normal char: consume + build glyph
    nop
tb_nl_color:
    j     0x089890E4            // original 0x14 handler (far -> use j)
    nop
tb_nl_break:
    lw    v0, 0x20(sp)          // v0 = lineHeight (scaled)
    lw    v1, 0x24(sp)          // v1 = pen-Y
    addu  v1, v1, v0            // pen-Y += lineHeight
    sw    v1, 0x24(sp)
    move  s6, zero             // pen-X = 0
    addiu s3, s3, 0x1          // consume the 0x0A
    j     0x0898909C            // load next char + continue loop
    nop

tb_nl_ystore:
    lw    v1, 0x24(sp)          // v1 = pen-Y     (v0 already = lineHeight here)
    sh    v1, 0xA(s2)          // y0 = pen-Y
    addu  v0, v1, v0            // v0 = pen-Y + lineHeight
    sh    v0, 0xE(s2)          // y1 = pen-Y + lineHeight
    li    v0, -1
    sh    v0, 0x18(s2)         // (orig) glyph end marker
    j     0x08989098
    nop


// Enlarge SCENARIO message text buffer
.org 0x0889BA9C
li a0, 0xA0       // scenario message struct size (was 0x5C)
.org 0x0889BAF0
li a2, 0x7B       // text strncpy limit (was 0x3B); null-terminates

// Grow chat box vertically when the message has '\n'
// Hook - before box draw
.org 0x08897C4C
j   tb_box_fit
nop

// Code Cave
.org 0x08A0E8B0
tb_box_fit:
    move  t0, s1               // t0 = text pointer
    li    t2, 0x14             // default height = one line
tb_box_scan:
    lbu   t1, 0x0(t0)
    beq   t1, zero, tb_box_done
    li    t3, 0x0A             // [ds]
    beq   t1, t3, tb_box_two   // found '\n'
    addiu t0, t0, 0x1          // [ds] advance
    j     tb_box_scan
    nop
tb_box_two:
    li    t2, 0x28             // two-line height = 40px
tb_box_done:
    sw    t2, 0xC(sp)          // stash height (free slot in FUN_08897c08 frame)
    // setSize(left cap @+0x50, width@+0x20, height)
    addiu a0, s0, 0x50
    lw    a1, 0x20(a0)
    lw    a2, 0xC(sp)
    lw    v0, 0x0(a0)
    lw    v0, 0x20(v0)
    jalr  v0
    nop
    // setSize(middle @+0x150, width@+0x20, height)
    addiu a0, s0, 0x150
    lw    a1, 0x20(a0)
    lw    a2, 0xC(sp)
    lw    v0, 0x0(a0)
    lw    v0, 0x20(v0)
    jalr  v0
    nop
    // setSize(right cap @+0x250, width@+0x20, height)
    addiu a0, s0, 0x250
    lw    a1, 0x20(a0)
    lw    a2, 0xC(sp)
    lw    v0, 0x0(a0)
    lw    v0, 0x20(v0)
    jalr  v0
    nop
    // replay overwritten instrs, then continue into the draw call
    lw    a1, 0x0(s0)          // orig 0x08897C4C
    lw    v0, 0x44(a1)         // orig 0x08897C50
    j     0x08897C54
    nop