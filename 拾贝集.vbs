' ============================================================
'  ShiBeiJi launcher  -  double-click this file to start
'  Works even if this launcher file is copied to the Desktop:
'  it searches for app.py in the current folder and nearby folders.
'  1) free port 5000   2) find python   3) start hidden
'  4) wait until ready 5) open browser
' ============================================================
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir

logPath = dir & "\" & ChrW(21551) & ChrW(21160) & ChrW(26085) & ChrW(24535) & ".txt"

Sub W(s)
  On Error Resume Next
  Set f = fso.OpenTextFile(logPath, 8, True)
  f.WriteLine Now & "  " & s
  f.Close
End Sub

W ""
W "================ launcher ================"
W "launcher dir = " & dir

' ---------- 0. locate the real project folder (has app.py) ----------
Function HasApp(p)
  HasApp = fso.FileExists(p & "\app.py")
End Function

base = ""
' a) same folder
If HasApp(dir) Then base = dir

' b) sub folders (one level, e.g. Desktop\essay-coach)
If base = "" Then
  On Error Resume Next
  For Each sf In fso.GetFolder(dir).SubFolders
    If HasApp(sf.Path) Then base = sf.Path : Exit For
  Next
  On Error GoTo 0
End If

' c) common places
If base = "" Then
  cands = Array( _
    dir & "\essay-coach", _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Desktop\essay-coach"), _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach"), _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach-main"), _
    sh.ExpandEnvironmentStrings("%USERPROFILE%\Documents\essay-coach"), _
    "C:\essay-coach", "D:\essay-coach" _
  )
  For Each c In cands
    If HasApp(c) Then base = c : Exit For
    ' also allow one extra level: xxx\essay-coach-main
    If base = "" And fso.FolderExists(c) Then
      On Error Resume Next
      For Each sf In fso.GetFolder(c).SubFolders
        If HasApp(sf.Path) Then base = sf.Path : Exit For
      Next
      On Error GoTo 0
    End If
  Next
End If

' d) deep search on Desktop / Downloads (max 2 levels)
If base = "" Then
  roots = Array(sh.ExpandEnvironmentStrings("%USERPROFILE%\Desktop"), _
                sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads"), _
                sh.ExpandEnvironmentStrings("%USERPROFILE%\Documents"))
  For Each rt In roots
    If base = "" And fso.FolderExists(rt) Then
      On Error Resume Next
      For Each l1 In fso.GetFolder(rt).SubFolders
        If HasApp(l1.Path) Then base = l1.Path : Exit For
        If base = "" Then
          For Each l2 In l1.SubFolders
            If HasApp(l2.Path) Then base = l2.Path : Exit For
          Next
        End If
      Next
      On Error GoTo 0
    End If
  Next
End If

If base = "" Then
  W "ERROR: app.py not found"
  MsgBox ChrW(25214) & ChrW(19981) & ChrW(21040) & " app.py" & vbCrLf & vbCrLf & _
    ChrW(35831) & ChrW(30830) & ChrW(35748) & ChrW(20320) & ChrW(24050) & ChrW(35299) & ChrW(21387) & ChrW(32553) & ChrW(21253) & ChrW(21040) & ChrW(26576) & ChrW(20010) & ChrW(25991) & ChrW(20214) & ChrW(22841) & ChrW(65292) & vbCrLf & _
    ChrW(24182) & ChrW(20174) & ChrW(35813) & ChrW(25991) & ChrW(20214) & ChrW(22841) & ChrW(20869) & ChrW(21452) & ChrW(20987) & " " & ChrW(25342) & ChrW(36125) & ChrW(38598) & ".vbs" & vbCrLf & vbCrLf & _
    ChrW(19981) & ChrW(35201) & ChrW(25226) & ChrW(23427) & ChrW(25302) & ChrW(21040) & ChrW(26700) & ChrW(38754) & ChrW(21333) & ChrW(29420) & ChrW(25918) & ChrW(32622) & ChrW(12290), vbExclamation, "ShiBeiJi"
  WScript.Quit
End If

W "project folder = " & base
sh.CurrentDirectory = base
logPath = base & "\" & ChrW(21551) & ChrW(21160) & ChrW(26085) & ChrW(24535) & ".txt"

' ---------- 1. already running? ----------
W "step1: check if server already running"
already = False
On Error Resume Next
Set probe = CreateObject("MSXML2.XMLHTTP")
Err.Clear
probe.Open "GET", "http://127.0.0.1:5000/", False
probe.Send
If Err.Number = 0 Then
  If probe.status = 200 Then already = True
End If
Err.Clear
On Error GoTo 0

If already Then
  W "server already running -> just open browser"
  sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
  WScript.Quit
End If

W "step1b: free port 5000"
On Error Resume Next
sh.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do taskkill /F /PID %a >nul 2>&1", 0, True
On Error GoTo 0
WScript.Sleep 1200

' ---------- 2. find python ----------
W "step2: locate python"
py = ""
rc = -1
On Error Resume Next
rc = sh.Run("cmd /c python --version >nul 2>&1", 0, True)
On Error GoTo 0
If rc = 0 Then py = "python"

If py = "" Then
  On Error Resume Next
  rc = sh.Run("cmd /c py -3 --version >nul 2>&1", 0, True)
  On Error GoTo 0
  If rc = 0 Then py = "py -3"
End If

If py = "" Then
  roots2 = Array(sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python"), _
                 sh.ExpandEnvironmentStrings("%PROGRAMFILES%\Python"), _
                 sh.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python"), _
                 "C:\Python")
  For Each rt In roots2
    If py = "" And fso.FolderExists(rt) Then
      On Error Resume Next
      For Each sf In fso.GetFolder(rt).SubFolders
        If fso.FileExists(sf.Path & "\python.exe") Then py = """" & sf.Path & "\python.exe""" : Exit For
      Next
      On Error GoTo 0
    End If
  Next
End If

If py = "" Then
  W "ERROR: python not found"
  MsgBox ChrW(25214) & ChrW(19981) & ChrW(21040) & " Python" & vbCrLf & vbCrLf & _
    ChrW(35831) & ChrW(21040) & " https://www.python.org/downloads/ " & ChrW(19979) & ChrW(36733) & ChrW(23433) & ChrW(35013) & vbCrLf & _
    ChrW(23433) & ChrW(35013) & ChrW(26102) & ChrW(24517) & ChrW(21246) & ChrW(36873) & " Add python.exe to PATH" & vbCrLf & _
    ChrW(28982) & ChrW(21518) & ChrW(37325) & ChrW(26032) & ChrW(21452) & ChrW(20987) & ChrW(26412) & ChrW(25991) & ChrW(20214), vbExclamation, "ShiBeiJi"
  WScript.Quit
End If
W "python = " & py

' ---------- 3. deps ----------
W "step3: check deps"
sh.Run "cmd /c cd /d """ & base & """ && " & py & " -m pip install -q -r requirements.txt >> """ & logPath & """ 2>&1", 0, True

' ---------- 4. start ----------
W "step4: start server"
sh.Run "cmd /c cd /d """ & base & """ && " & py & " app.py >> """ & logPath & """ 2>&1", 0, False

' ---------- 5. wait ----------
W "step5: wait for server"
ready = False
Set http = CreateObject("MSXML2.XMLHTTP")
For i = 1 To 40
  WScript.Sleep 1000
  On Error Resume Next
  Err.Clear
  http.Open "GET", "http://127.0.0.1:5000/", False
  http.Send
  If Err.Number = 0 Then
    If http.status = 200 Then ready = True
  End If
  Err.Clear
  On Error GoTo 0
  If ready Then Exit For
Next

If ready Then
  W "server ready -> open browser"
  sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
Else
  W "ERROR: server not ready in 40s"
  sh.Run "cmd /c start notepad.exe """ & logPath & """", 0, False
  MsgBox ChrW(21551) & ChrW(21160) & ChrW(22833) & ChrW(36133) & ChrW(65292) & ChrW(35814) & ChrW(24773) & ChrW(35265) & " " & ChrW(21551) & ChrW(21160) & ChrW(26085) & ChrW(24535) & ".txt", vbExclamation, "ShiBeiJi"
End If
