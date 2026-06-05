# Tales-of-the-Heroes-Twin-Brave Innocence R Demo
An attempt to translate Tales of the Heroes: Twin Brave Innocence R Demo

1.
install newest python via the standalone installer so that you can use "pip" on step 4:
https://www.python.org/

2.
put the demo disc in the root folder of the repo for twin brave. Make sure it is named TB_InnoR_Demo.iso

3.
create a folder in that root folder called 0_disc if there isn't one already

4.
go into powershell and paste and run this:
```powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"```


5.
type "environment variable" in your windows search bar
go into it and click environment variables.
under path, select edit.
paste this code:
C:\Users\patri\.local\bin
(you need to sub in "patri" with your username for the computer file structure.)

click ok and exit this page.

6.
reset pc.

7.
go into the demo repo folder and double click extract.bat

after it is done running,  go into 0_disc and copy the contents of that folder into 
4_builds.

click repack.bat 
