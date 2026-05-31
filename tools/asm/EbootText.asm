.open "1_extracted/EBOOT.BIN","4_builds\PSP_GAME\SYSDIR\EBOOT.BIN",0x00
.psp

//Title Name
.orga 0x250ED8
.asciiz "Tales of the Heroes: Twin Brave"

.orga 0x250FA0
.asciiz "New Save File"


//Result Screen Names?
.orga 0x230600
.asciiz "None"

.orga 0x23060C
.asciiz "Ruca"

.orga 0x230614
.asciiz "Spada"

.orga 0x230620
.asciiz "Emil"

.orga 0x230628
.asciiz "Marta"

.orga 0x230630
.asciiz "Yuri"

.orga 0x230638
.asciiz "Flynn"

.orga 0x230640
.asciiz "Max"


//Skit Names
.orga 0x2438C0
.asciiz "???"

.orga 0x2438D0
.asciiz "Ruca"

.orga 0x2438D8
.asciiz "Spada"

.orga 0x2438E4
.asciiz "Emil"

.orga 0x2438EC
.asciiz "Marta"

.orga 0x2438F4
.asciiz "Yuri"

.orga 0x2438FC
.asciiz "Flynn"

//Weapon Names
.orga 0x237704
.asciiz "Akabane Swords"

.orga 0x23719C
.asciiz "Broadsword"

//Text on the main selection window
.orga 0x242018
.asciiz "???"

.orga 0x242020
.asciiz "Please Select an Option."

.orga 0x24203C
.asciiz "How to Play"

.orga 0x24204C
.asciiz "Learn how to play the game."

.orga 0x242068
.asciiz "Story / Spada"

.orga 0x242080
.asciiz "A story with Spada as the MC."

.orga 0x2420A0
.asciiz "The hotheaded Spada starts a quarrel!"

.orga 0x2420CC
.asciiz "Special / Ruca"

.orga 0x2420E0
.asciiz "A demo-only special story. Play out"

.orga 0x242108
.asciiz "Ruca's tussle with others from Tales."

.close
