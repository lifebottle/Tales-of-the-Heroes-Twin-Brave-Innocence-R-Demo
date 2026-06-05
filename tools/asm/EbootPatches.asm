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
.halfword 31,58,82,115,0,0,0,0,0,0           // map3
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
