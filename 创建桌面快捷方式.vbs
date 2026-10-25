' Create desktop shortcut for ShiBeiJi (double-click me)
' ASCII only; Chinese names built with ChrW so nothing garbles
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' target = this folder + launcher vbs (Chinese filename via ChrW)
target = dir & "\" & ChrW(21551) & ChrW(21160) & ChrW(38169) & ChrW(39064) & ChrW(38598) & ChrW(65288) & ChrW(21518) & ChrW(21488) & ChrW(65289) & ".vbs"

If Not fso.FileExists(target) Then
  ' fallback: try ASCII copy of launcher name variants
  alt = dir & "\start-bg.vbs"
  If fso.FileExists(alt) Then target = alt
End If

desktop = sh.SpecialFolders("Desktop")
name = ChrW(25342) & ChrW(36125) & ChrW(38598) ' ShiBeiJi
lnkPath = desktop & "\" & name & ".lnk"

Set lnk = sh.CreateShortcut(lnkPath)
lnk.TargetPath = target
lnk.WorkingDirectory = dir
lnk.Description = "ShiBeiJi - double click to start (no console window)"
lnk.Save

If fso.FileExists(lnkPath) Then
  MsgBox "OK! Your desktop now has a shortcut: " & name & vbCrLf & "Double-click it to start. No black window, opens the page automatically.", vbInformation, "Done"
Else
  MsgBox "Failed to create the shortcut. Please right-click the launcher vbs and choose Send to -> Desktop (create shortcut).", vbExclamation, "Error"
End If
