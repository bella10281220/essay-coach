' Create desktop launcher for ShiBeiJi (double-click me)
' Two methods: 1) real .lnk shortcut  2) copy a launcher vbs onto the desktop
' ASCII only inside; Chinese names built with ChrW so nothing garbles
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' launcher vbs in this folder (Chinese name via ChrW)
launcher = dir & "\" & ChrW(21551) & ChrW(21160) & ChrW(38169) & ChrW(39064) & ChrW(38598) & ChrW(65288) & ChrW(21518) & ChrW(21488) & ChrW(65289) & ".vbs"

If Not fso.FileExists(launcher) Then
  MsgBox "Cannot find the launcher vbs in this folder. Please make sure you double-clicked the file inside the project folder.", vbExclamation, "Error"
  WScript.Quit
End If

results = ""
desktop = sh.SpecialFolders("Desktop")

' --- method 1: .lnk shortcut ---
ok1 = False
On Error Resume Next
Set lnk = sh.CreateShortcut(desktop & "\" & ChrW(25342) & ChrW(36125) & ChrW(38598) & ".lnk")
lnk.TargetPath = launcher
lnk.WorkingDirectory = dir
lnk.Description = "ShiBeiJi launcher (no console window)"
lnk.Save
ok1 = fso.FileExists(desktop & "\" & ChrW(25342) & ChrW(36125) & ChrW(38598) & ".lnk")
On Error GoTo 0
If ok1 Then results = results & "1) shortcut created on desktop: OK" & vbCrLf

' --- method 2: copy a launcher vbs file to the desktop (always works) ---
' Chinese path built with ChrW codes
Dim codes : codes = Array(21551,21160,38169,39064,38598,65288,21518,21488,65289)
tgt = dir & "\"
For Each c In codes : tgt = tgt & ChrW(c) : Next
tgt = tgt & ".vbs"
content = "CreateObject(""WScript.Shell"").Run """"" & tgt & """"""
deskFile = desktop & "\" & ChrW(25342) & ChrW(36125) & ChrW(38598) & "-Start.vbs"
On Error Resume Next
Set f2 = fso.CreateTextFile(deskFile, True)
f2.Write content
f2.Close
ok2 = fso.FileExists(deskFile)
On Error GoTo 0
If ok2 Then results = results & "2) launcher file copied to desktop: OK" & vbCrLf

If results = "" Then
  MsgBox "Both methods failed. Please do it manually: right-click the launcher vbs -> Send to -> Desktop (create shortcut).", vbExclamation, "Failed"
Else
  MsgBox "Done!" & vbCrLf & results & vbCrLf & "Look at your desktop now. Double-click it to start (no black window).", vbInformation, "OK"
End If
