::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_battle.arc --input 3_patched\arc\mlt\mlt_battle --output 3_patched\all\mlt\mlt_battle.arc
::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_keyhelp.arc --input 3_patched\arc\mlt\mlt_keyhelp --output 3_patched\all\mlt\mlt_keyhelp.arc
::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_tutorial.arc --input 3_patched\arc\mlt\mlt_tutorial --output 3_patched\all\mlt\mlt_tutorial.arc
::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_intro.arc --input 3_patched\arc\mlt\mlt_intro --output 3_patched\all\mlt\mlt_intro.arc

::python tools\tb_tools\scripts\bdi_repack.py
::copy /Y 3_patched\namco.bdi 4_builds\PSP_GAME\USRDIR\namco.bdi


REM Copy every graphics except PSP_GAME Folder
robocopy "2_translated\graphics" "3_patched\all" *.png /E /XD "2_translated\graphics\PSP_GAME"

REM Copy PSP_GAME Graphics folder to 4_builds
robocopy "2_translated\graphics\PSP_GAME" "4_builds\PSP_GAME" *.PNG /E

"tools/asm/armips.exe" "tools/asm/EbootText.asm"
python tools\tb_tools\scripts\mlb_repack.py
python tools\codebase\ScriptRepack.py
uv run tb-tools bdi --overlay 3_patched/all --bdi 0_disc\PSP_GAME\USRDIR\namco.bdi --output 4_builds/PSP_GAME/USRDIR/namco.bdi
pause