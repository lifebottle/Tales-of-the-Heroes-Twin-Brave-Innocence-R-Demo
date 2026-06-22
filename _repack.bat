::Copy every graphics except PSP_GAME Folder
robocopy "2_translated\graphics" "3_patched\all" *.png /E /XD "PSP_GAME"

::Copy PSP_GAME Graphics folder to 4_builds
robocopy "2_translated\graphics\PSP_GAME" "4_builds\PSP_GAME" *.PNG /E

::repack the ass to the sub file needed and move them to the iso directory
python tools\ass2sub.py "2_translated\subs\trial_toir.ass" "3_patched/trial_toir.sub"
move /Y "3_patched\trial_toir.sub" "4_builds\PSP_GAME\USRDIR\trial_toir.sub"

::repack the eboot with text and asm
"tools/asm/armips.exe" "tools/asm/EbootText.asm"

::repack the menus mlb
python tools\tb_tools\scripts\mlb_repack.py

::repack the skits
python tools\codebase\ScriptRepack.py

::repack the es files
python tools\codebase\battle2_repack.py

::repack everything else
uv run tb-tools bdi --overlay 3_patched/all --bdi 0_disc\PSP_GAME\USRDIR\namco.bdi --output 4_builds/PSP_GAME/USRDIR/namco.bdi

::update the PARAM.SFO title
python tools\sfo_title.py 4_builds\PSP_GAME\PARAM.SFO "Tales of the Heroes TWIN BRAVE (Innocence R Demo Version)"

pause
