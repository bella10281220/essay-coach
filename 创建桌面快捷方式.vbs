' ============================================================
'  ShiBeiJi - create ONE desktop icon (double-click me, once)
'  Only creates:  拾贝集.lnk  (icon = the book cover)
'  The old wrapper file "拾贝集 启动.vbs" on the desktop is
'  removed automatically, so you end up with a single icon.
'  Needs no admin rights.
' ============================================================
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

SHI = ChrW(25342)   ' 拾
BEI = ChrW(36125)   ' 贝
JI  = ChrW(38598)   ' 集
QI  = ChrW(21551)   ' 启
DONG= ChrW(21160)   ' 动
NAME = SHI & BEI & JI

' ---------- 0. locate project folder (same logic as the launcher) ----------
Function HasApp(p)
  HasApp = fso.FileExists(p & "\app.py")
End Function

dir = fso.GetParentFolderName(WScript.ScriptFullName)
base = ""
If HasApp(dir) Then base = dir

If base = "" Then
  On Error Resume Next
  For Each sf In fso.GetFolder(dir).SubFolders
    If HasApp(sf.Path) Then base = sf.Path : Exit For
  Next
  On Error GoTo 0
End If

If base = "" Then
  cands = Array( _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Desktop\essay-coach"), _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach"), _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach-main"), _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Documents\essay-coach"), _
    "C:\essay-coach", "D:\essay-coach" )
  For Each c In cands
    If base = "" And HasApp(c) Then base = c
    If base = "" And fso.FolderExists(c) Then
      On Error Resume Next
      For Each sf In fso.GetFolder(c).SubFolders
        If HasApp(sf.Path) Then base = sf.Path : Exit For
      Next
      On Error GoTo 0
    End If
  Next
End If

If base = "" Then
  MsgBox ChrW(25214) & ChrW(19981) & ChrW(21040) & " app.py" & vbCrLf & vbCrLf & _
    ChrW(35831) & ChrW(25226) & ChrW(26412) & ChrW(25991) & ChrW(20214) & ChrW(25918) & ChrW(21040) & " essay-coach " & ChrW(25991) & ChrW(20214) & ChrW(22841) & ChrW(20869) & ChrW(20877) & ChrW(21452) & ChrW(20987) & ChrW(12290), _
    vbExclamation, "ShiBeiJi"
  WScript.Quit
End If

launcher = base & "\" & NAME & ".vbs"
If Not fso.FileExists(launcher) Then
  MsgBox ChrW(25214) & ChrW(19981) & ChrW(21040) & " " & NAME & ".vbs" & vbCrLf & vbCrLf & _
    ChrW(35831) & ChrW(30830) & ChrW(35748) & ChrW(26032) & ChrW(29256) & ChrW(24050) & ChrW(35299) & ChrW(21387) & ChrW(35206) & ChrW(30422) & ChrW(12290), _
    vbExclamation, "ShiBeiJi"
  WScript.Quit
End If

' ---------- 1. delete the old extra desktop file ----------
desk = sh.SpecialFolders("Desktop")
oldFile = desk & "\" & NAME & " " & QI & DONG & ".vbs"
oldLnk  = desk & "\" & NAME & " - " & ChrW(24555) & ChrW(25463) & ChrW(26041) & ChrW(24335) & ".lnk"
On Error Resume Next
If fso.FileExists(oldFile) Then fso.DeleteFile oldFile, True
If fso.FileExists(oldLnk) Then fso.DeleteFile oldLnk, True
On Error GoTo 0

' ---------- 2. create the single .lnk ----------
lnkPath = desk & "\" & NAME & ".lnk"
ok = False
errMsg = ""
On Error Resume Next
Err.Clear
Set lnk = sh.CreateShortcut(lnkPath)
lnk.TargetPath = sh.ExpandEnvironmentStrings("%WINDIR%") & "\System32\wscript.exe"
lnk.Arguments = """" & launcher & """"
lnk.WorkingDirectory = base
lnk.Description = NAME
lnk.IconLocation = base & "\static\favicon.ico,0"
lnk.WindowStyle = 7
lnk.Save
errMsg = Err.Description
On Error GoTo 0

ok = fso.FileExists(lnkPath)

' fallback: if .lnk failed (rare), copy a plain vbs with the same name
If Not ok Then
  On Error Resume Next
  content = "CreateObject(""WScript.Shell"").Run ""wscript.exe """"" & launcher & """", 0, False"
  Set f = fso.CreateTextFile(desk & "\" & NAME & ".vbs", True)
  f.WriteLine content
  f.Close
  ok = fso.FileExists(desk & "\" & NAME & ".vbs")
  On Error GoTo 0
End If

' ---------- 3. tell the user ----------
If ok Then
  MsgBox ChrW(23436) & ChrW(25104) & ChrW(65281) & vbCrLf & vbCrLf & _
    ChrW(26700) & ChrW(38754) & ChrW(19978) & ChrW(29616) & ChrW(22312) & ChrW(21482) & ChrW(26377) & ChrW(19968) & ChrW(20010) & ChrW(22270) & ChrW(26631) & ChrW(65306) & NAME & vbCrLf & _
    ChrW(21452) & ChrW(20987) & ChrW(23427) & ChrW(23601) & ChrW(20250) & ChrW(33258) & ChrW(21160) & ChrW(21551) & ChrW(21160) & ChrW(24182) & ChrW(25171) & ChrW(24320) & ChrW(32593) & ChrW(39029) & ChrW(12290) & vbCrLf & vbCrLf & _
    ChrW(22914) & ChrW(26524) & ChrW(22270) & ChrW(26631) & ChrW(36824) & ChrW(26159) & ChrW(26087) & ChrW(30340) & ChrW(65292) & ChrW(21491) & ChrW(38190) & ChrW(23646) & ChrW(24615) & " -> " & ChrW(26356) & ChrW(25442) & ChrW(22270) & ChrW(26631) & " -> " & ChrW(27983) & ChrW(35272) & ChrW(21040) & " static\favicon.ico", _
    vbInformation, "ShiBeiJi"
Else
  MsgBox ChrW(21019) & ChrW(24314) & ChrW(22833) & ChrW(36133) & ChrW(65306) & errMsg & vbCrLf & vbCrLf & _
    ChrW(25163) & ChrW(21160) & ChrW(26041) & ChrW(27861) & ChrW(65306) & ChrW(21491) & ChrW(38190) & " " & NAME & ".vbs -> " & ChrW(21457) & ChrW(36865) & ChrW(21040) & " -> " & ChrW(26700) & ChrW(38754) & ChrW(24555) & ChrW(25463) & ChrW(26041) & ChrW(24335), _
    vbExclamation, "ShiBeiJi"
End If
