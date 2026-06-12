::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_battle.arc --input 3_patched\arc\mlt\mlt_battle --output 3_patched\all\mlt\mlt_battle.arc
::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_keyhelp.arc --input 3_patched\arc\mlt\mlt_keyhelp --output 3_patched\all\mlt\mlt_keyhelp.arc
::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_tutorial.arc --input 3_patched\arc\mlt\mlt_tutorial --output 3_patched\all\mlt\mlt_tutorial.arc
::python tools\tb_tools\scripts\arc_repack.py --original 1_extracted\all\mlt\mlt_intro.arc --input 3_patched\arc\mlt\mlt_intro --output 3_patched\all\mlt\mlt_intro.arc

::python tools\tb_tools\scripts\bdi_repack.py
::copy /Y 3_patched\namco.bdi 4_builds\PSP_GAME\USRDIR\namco.bdi


REM Copy every graphics except PSP_GAME Folder
robocopy "2_translated\graphics" "3_patched\all" *.png /E /XD "PSP_GAME"

REM Copy PSP_GAME Graphics folder to 4_builds
robocopy "2_translated\graphics\PSP_GAME" "4_builds\PSP_GAME" *.PNG /E

::repack the eboot with text
"tools/asm/armips.exe" "tools/asm/EbootText.asm"
::repack the menus mlb
python tools\tb_tools\scripts\mlb_repack.py
::repack the skits
python tools\codebase\ScriptRepack.py
::repack the es files
python tools\codebase\battle2_repack.py
uv run tb-tools bdi --overlay 3_patched/all --bdi 0_disc\PSP_GAME\USRDIR\namco.bdi --output 4_builds/PSP_GAME/USRDIR/namco.bdi
::update the PARAM.SFO title
python tools\sfo_title.py 4_builds\PSP_GAME\PARAM.SFO "Tales of the Heroes TWIN BRAVE (Innocence R Demo Version)"
pause
