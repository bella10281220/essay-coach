' ShiBeiJi - put a launcher on the desktop (double-click me)
' Copies a tiny launcher file onto the desktop. Needs no admin rights.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' build launcher filename: 启动错题集（后台）.vbs
Dim codes : codes = Array(25342,36125,38598)
launcherName = ""
For Each c In codes : launcherName = launcherName & ChrW(c) : Next
launcherName = launcherName & ".vbs"
launcher = dir & "\" & launcherName

If Not fso.FileExists(launcher) Then
  MsgBox "Launcher not found in this folder." & vbCrLf & _
         "Please put this file into the project folder and run it again.", vbExclamation, "ShiBeiJi"
  WScript.Quit
End If

deskName = ChrW(25342) & ChrW(36125) & ChrW(38598) & " " & ChrW(21551) & ChrW(21160) & ".vbs"
deskFile = sh.SpecialFolders("Desktop") & "\" & deskName

On Error Resume Next
content = "CreateObject(""WScript.Shell"").Run ""wscript.exe """"" & launcher & """"""""
Set f = fso.CreateTextFile(deskFile, True)
f.WriteLine content
f.Close
okA = fso.FileExists(deskFile)
errA = Err.Description
On Error GoTo 0

okB = False
On Error Resume Next
Set lnk = sh.CreateShortcut(sh.SpecialFolders("Desktop") & "\" & ChrW(25342) & ChrW(36125) & ChrW(38598) & ".lnk")
lnk.TargetPath = "wscript.exe"
lnk.Arguments = """" & launcher & """"
lnk.WorkingDirectory = dir
lnk.IconLocation = "shell32.dll,137"
lnk.Save
okB = fso.FileExists(sh.SpecialFolders("Desktop") & "\" & ChrW(25342) & ChrW(36125) & ChrW(38598) & ".lnk")
On Error GoTo 0

If okA Or okB Then
  msg = "Done!" & vbCrLf & vbCrLf
  If okA Then msg = msg & "Desktop file: " & deskName & vbCrLf
  If okB Then msg = msg & "Shortcut: ShiBeiJi.lnk" & vbCrLf
  msg = msg & vbCrLf & "Double-click it to start (no black window, opens the page automatically)."
  MsgBox msg, vbInformation, "ShiBeiJi"
Else
  MsgBox "Failed: " & errA & vbCrLf & vbCrLf & _
         "Please do it manually: right-click " & launcherName & _
         " -> Send to -> Desktop (create shortcut).", vbExclamation, "ShiBeiJi"
End If
