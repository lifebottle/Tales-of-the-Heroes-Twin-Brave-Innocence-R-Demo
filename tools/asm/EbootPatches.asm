.headersize 0x8803000

// Change margin from 0x64 to 0x50
.org 0x08920580
li a1, 0x50

// Text speed: default frames-per-char 0x2 -> 0x1 (faster)
.org 0x08920cc4
li v0, 0x1

// Map-name slice table
// Each value is the right-edge X cut of a glyph in mapname%d.ppt.
// A trailing 0 ends the row (the last glyph then extends to the texture edge).
.org 0x08a2b450
.halfword 28,49,77,102,123,155,0,0,0,0       // map0
.halfword 85,161,0,0,0,0,0,0,0,0             // map1
.halfword 31,60,86,115,139,169,197,225,0,0   // map2
.halfword 72,0,0,0,0,0,0,0,0,0               // map3
.halfword 30,60,91,111,139,167,0,0,0,0       // map4
.halfword 27,51,75,101,126,159,192,225,0,0   // map5
.halfword 33,66,99,127,151,184,0,0,0,0       // map6
.halfword 34,66,100,128,0,0,0,0,0,0          // map7

// ---- Slow down the map-name reveal ----
.org 0x088967c4
sll v1, s0, 0x4
.org 0x088967e8
sll v1, s0, 0x4
.org 0x088967ec
sll v0, a3, 0x4
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
    li    t2, 0x20             // two-line height = 40px
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


// PMF movie subtitles load EUC-JP .sub file
// Hook A - reset frame counter at movie start
.org 0x0898B768
j   mv_reset
nop

// Hook B - per-present draw
.org 0x0899AFD0
j   mv_sub_draw
nop

// ---- code cave (unreferenced zero pad @ 0x08A29BF5+, ~600 bytes) ----
.org 0x08A29C00
mv_frame_ctr:
    .word 0
mv_sub_buf:
    .word 0                     // loaded .sub buffer (0 = not loaded yet)
mv_reset:
    addiu sp, sp, -0x180        // replay original prologue
    sw    s7, 0x16c(sp)         // replay
    la    t0, mv_frame_ctr
    sw    zero, 0x0(t0)         // frame counter = 0
    j     0x0898B770
    nop
mv_sub_draw:
    addiu sp, sp, -0x40
    sw    s2, 0x38(sp)          
    sw    s3, 0x34(sp)
    sw    s4, 0x30(sp)
    sw    s5, 0x2c(sp)
    sw    s6, 0x28(sp)
    sw    s7, 0x24(sp)
    //load the .sub file
    la    t9, mv_sub_buf
    lw    t8, 0x0(t9)
    bne   t8, zero, mv_after_load
    nop
    jal   0x08804534           
    li    a0, 0x2000
    beq   v0, zero, mv_after_load   
    nop
    move  s6, v0
    la    t9, mv_sub_buf
    sw    s6, 0x0(t9)           
    sw    zero, 0x0(s6)         
    la    a0, mv_sub_path
    li    a1, 0x1              
    jal   0x08a0b654           
    li    a2, 0x1ff
    bltz  v0, mv_after_load     
    move  s7, v0              
    move  a0, s7
    move  a1, s6
    jal   0x08a0b614           
    li    a2, 0x2000
    move  a0, s7
    jal   0x08a0b61c           
    nop
mv_after_load:
    la    t9, mv_frame_ctr
    lw    t8, 0x0(t9)
    addiu t8, t8, 0x1
    sw    t8, 0x0(t9)           // current frame
    la    t9, mv_sub_buf
    lw    s6, 0x0(t9)
    beq   s6, zero, mv_none
    nop
    lw    t0, 0x0(s6)           // cue count
    addiu t1, s6, 0x4          // first cue entry
    sw    t0, 0x1c(sp)          // cues remaining
    sw    t1, 0x18(sp)          // current cue entry ptr
mv_cue_loop:
    lw    t0, 0x1c(sp)
    blez  t0, mv_none
    nop
    lw    t1, 0x18(sp)
    la    t9, mv_frame_ctr
    lw    t8, 0x0(t9)           // frame
    lw    t2, 0x0(t1)           // start
    lw    t3, 0x4(t1)           // end
    sltu  v0, t8, t2            // frame
    bne   v0, zero, mv_cue_next
    nop
    sltu  v0, t8, t3            // frame 
    beq   v0, zero, mv_cue_next  // frame 
    nop
    la    t9, mv_sub_buf
    lw    s6, 0x0(t9)           // buffer base
    lw    s7, 0x8(t1)           // penY
    lw    t4, 0xc(t1)           // textOff
    lw    s4, 0x10(t1)          // textLen
    addu  s2, s6, t4           // text ptr
    addu  s4, s2, s4           // text end ptr
    jal   0x088056cc
    nop
    move  s5, v0              // s5 = font ctx
mv_line:
    sltu  v0, s2, s4
    beq   v0, zero, mv_cue_next  // cue done -> next cue
    nop
    li    s3, 0               // width accumulator
    move  s6, s2              // scan = line start
mv_meas:
    sltu  v0, s6, s4
    beq   v0, zero, mv_meas_done
    nop
    lbu   t0, 0x0(s6)
    li    t1, 0xa
    beq   t0, t1, mv_meas_done  
    nop
    sltiu v0, t0, 0x80
    bne   v0, zero, mv_meas_ascii
    nop
    lbu   t1, 0x1(s6)          // EUC-JP trail
    sll   a0, t0, 0x8
    or    a0, a0, t1
    jal   0x089992e0
    nop
    move  a1, v0
    addiu s6, s6, 0x2
    j     mv_meas_adv
    nop
mv_meas_ascii:
    move  a1, t0
    addiu s6, s6, 0x1
mv_meas_adv:
    jal   0x08984f00          // advance width
    move  a0, s5             
    sll   t0, v0, 1
    addu  v0, v0, t0          
    srl   v0, v0, 2          
    addu  s3, s3, v0
    j     mv_meas
    nop
mv_meas_done:
    li    v0, 0x1e0           // 480 (visible width)
    subu  v0, v0, s3
    bgez  v0, mv_cx_ok
    nop
    li    v0, 0               // line wider than screen -> start at left edge
mv_cx_ok:
    sra   s3, v0, 1           // s3 = centered penX
mv_render:
    sltu  v0, s2, s4
    beq   v0, zero, mv_cue_next  
    nop
    lbu   t0, 0x0(s2)
    li    t1, 0xa
    beq   t0, t1, mv_line_break  
    nop
    sltiu v0, t0, 0x80
    bne   v0, zero, mv_r_ascii
    nop
    lbu   t1, 0x1(s2)          
    sll   a0, t0, 0x8
    or    a0, a0, t1
    jal   0x089992e0
    nop
    move  t0, v0
    addiu s2, s2, 0x2
    j     mv_r_glyph
    nop
mv_r_ascii:
    addiu s2, s2, 0x1
mv_r_glyph:
    sh    t0, 0x14(sp)         // charcode -> slotStruct+4
    addiu a0, sp, 0x10
    jal   0x08985264          // rasterize glyph -> temp buf
    move  a1, zero
    lw    t0, -0x83c(s0)
    lui   t1, 0x4000
    or    t0, t0, t1          // uncached
    sll   t1, s7, 0xb         // penY*2048
    addu  t0, t0, t1
    sll   t1, s3, 2          // penX*4
    addu  s6, t0, t1          // s6 = base dst
    addiu a0, s6, -2052       // (-1,-1)
    jal   mv_blit
    li    a1, 0
    addiu a0, s6, -2048       // ( 0,-1)
    jal   mv_blit
    li    a1, 0
    addiu a0, s6, -2044       // (+1,-1)
    jal   mv_blit
    li    a1, 0
    addiu a0, s6, -4          // (-1, 0)
    jal   mv_blit
    li    a1, 0
    addiu a0, s6, 4           // (+1, 0)
    jal   mv_blit
    li    a1, 0
    addiu a0, s6, 2044        // (-1,+1)
    jal   mv_blit
    li    a1, 0
    addiu a0, s6, 2048        // ( 0,+1)
    jal   mv_blit
    li    a1, 0
    addiu a0, s6, 2052        // (+1,+1)
    jal   mv_blit
    li    a1, 0
    move  a0, s6              // centre
    jal   mv_blit
    li    a1, 0xff            
    lhu   a1, 0x14(sp)        
    jal   0x08984f00
    move  a0, s5             
    sll   t0, v0, 1
    addu  v0, v0, t0         
    srl   v0, v0, 2          // *3/4 (0.75x scale)
    addu  s3, s3, v0         
    j     mv_render          
    nop
mv_line_break:
    addiu s2, s2, 0x1          
    addiu s7, s7, 0xf          
    j     mv_line              
    nop
mv_cue_next:
    lw    t1, 0x18(sp)
    addiu t1, t1, 0x14         
    sw    t1, 0x18(sp)
    lw    t0, 0x1c(sp)
    addiu t0, t0, -0x1         
    sw    t0, 0x1c(sp)
    j     mv_cue_loop
    nop
mv_none:
    lw    s2, 0x38(sp)
    lw    s3, 0x34(sp)
    lw    s4, 0x30(sp)
    lw    s5, 0x2c(sp)
    lw    s6, 0x28(sp)
    lw    s7, 0x24(sp)
    addiu sp, sp, 0x40
    addiu s1, s0, -0x83c       
    lw    a0, -0x83c(s0)       
    j     0x0899AFD8
    nop
mv_blit:
    lw    t1, -0x1bbc(s0)     
    la    t2, mv_dn_map       
    li    t4, 0               
mv_b_row:
    addu  t5, t2, t4
    lbu   t5, 0x0(t5)         
    sll   t6, t5, 3
    sll   t7, t5, 1
    addu  t5, t6, t7          
    addu  t5, t1, t5          
    sll   t6, t4, 0xb         
    addu  t6, a0, t6          
    li    t3, 0               
mv_b_col:
    addu  t7, t2, t3
    lbu   t7, 0x0(t7)         
    srl   t8, t7, 1
    addu  t8, t5, t8          
    lbu   t8, 0x0(t8)
    andi  t9, t7, 1
    beq   t9, zero, mv_b_lo
    nop
    srl   t8, t8, 4           
    j     mv_b_cov
    nop
mv_b_lo:
    andi  t8, t8, 0xf         
mv_b_cov:
    beq   t8, zero, mv_b_skip  
    nop
    sll   v0, t3, 2
    addu  v0, t6, v0         // dst pixel addr
    lw    v1, 0x0(v0)
    andi  t9, v1, 0xff       
    subu  a2, a1, t9
    mult  a2, t8
    mflo  a2
    sra   a2, a2, 4
    addu  t9, t9, a2
    andi  a3, t9, 0xff       
    srl   t9, v1, 8
    andi  t9, t9, 0xff       
    subu  a2, a1, t9
    mult  a2, t8
    mflo  a2
    sra   a2, a2, 4
    addu  t9, t9, a2
    andi  t9, t9, 0xff
    sll   t9, t9, 8
    or    a3, a3, t9
    srl   t9, v1, 0x10
    andi  t9, t9, 0xff       
    subu  a2, a1, t9
    mult  a2, t8
    mflo  a2
    sra   a2, a2, 4
    addu  t9, t9, a2
    andi  t9, t9, 0xff
    sll   t9, t9, 0x10
    or    a3, a3, t9
    lui   t9, 0xff00
    or    a3, a3, t9         
    sw    a3, 0x0(v0)
mv_b_skip:
    addiu t3, t3, 0x1
    sltiu v0, t3, 15
    bne   v0, zero, mv_b_col
    nop
    addiu t4, t4, 0x1
    sltiu v0, t4, 15
    bne   v0, zero, mv_b_row
    nop
    jr    ra
    nop

mv_dn_map:
    .db 0,1,2,4,5,6,8,9,10,12,13,14,16,17,18
    .align 4

mv_sub_path:
    .db "disc0:/PSP_GAME/USRDIR/trial_toir.sub", 0
    .align 4