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
On Error Resume Next
sh.CurrentDirectory = dir
On Error GoTo 0

logPath = dir & "\启动日志.txt"

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
  Dim cands(6)
  cands(0) = dir & "\essay-coach"
  cands(1) = sh.ExpandEnvironmentStrings("%USERPROFILE%\Desktop\essay-coach")
  cands(2) = sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach")
  cands(3) = sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach-main")
  cands(4) = sh.ExpandEnvironmentStrings("%USERPROFILE%\Documents\essay-coach")
  cands(5) = "C:\essay-coach"
  cands(6) = "D:\essay-coach"
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
  Dim roots(2)
  roots(0) = sh.ExpandEnvironmentStrings("%USERPROFILE%\Desktop")
  roots(1) = sh.ExpandEnvironmentStrings("%USERPROFILE%\Downloads")
  roots(2) = sh.ExpandEnvironmentStrings("%USERPROFILE%\Documents")
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
  m = "找不到 app.py" & vbCrLf & vbCrLf
  m = m & "请确认你已解压整个文件夹，并从该文件夹内双击 拾贝集.vbs。" & vbCrLf
  m = m & "不要把它拖到桌面单独放置。" & vbCrLf & vbCrLf
  m = m & "正确做法：把 拾贝集.vbs 留在 essay-coach 文件夹里，" & vbCrLf
  m = m & "然后双击 创建桌面快捷方式.vbs 生成桌面图标。"
  MsgBox m, vbExclamation, "拾贝集"
  WScript.Quit
End If

W "project folder = " & base
sh.CurrentDirectory = base
logPath = base & "\启动日志.txt"

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
' also treat "port 5000 is listening" as already-running
If Not already Then
  Err.Clear
  Set ex = sh.Exec("cmd /c netstat -ano | findstr :5000 | findstr LISTENING")
  outTxt = ex.StdOut.ReadAll
  If InStr(outTxt, "LISTENING") > 0 Then already = True
End If
Err.Clear
On Error GoTo 0

If already Then
  W "step1a: port 5000 busy -> wait it becomes ready, then open browser"
  Set h2 = CreateObject("MSXML2.XMLHTTP")
  ok2 = False
  For i = 1 To 25
    Err.Clear
    On Error Resume Next
    h2.Open "GET", "http://127.0.0.1:5000/", False
    h2.Send
    If Err.Number = 0 Then
      If h2.status = 200 Then ok2 = True
    End If
    Err.Clear
    On Error GoTo 0
    If ok2 Then Exit For
    WScript.Sleep 1000
  Next
  If ok2 Then
    W "server already running -> just open browser"
    sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
    WScript.Quit
  End If
  W "port busy but no response -> take it over"
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
  Dim roots2(3)
  roots2(0) = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python")
  roots2(1) = sh.ExpandEnvironmentStrings("%PROGRAMFILES%\Python")
  roots2(2) = sh.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python")
  roots2(3) = "C:\Python"
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
  m = "找不到 Python" & vbCrLf & vbCrLf
  m = m & "请打开 https://www.python.org/downloads/ 下载安装，" & vbCrLf
  m = m & "安装第一步务必勾选 Add python.exe to PATH，" & vbCrLf
  m = m & "装完后重新双击本文件。"
  MsgBox m, vbExclamation, "拾贝集"
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

' read the real port written by app.py (falls back when 5000 is taken)
urlBase = "http://127.0.0.1:5000"
portFile = base & "\data\port.txt"
If fso.FileExists(portFile) Then
  On Error Resume Next
  Set pf = fso.OpenTextFile(portFile, 1, False)
  pv = Trim(pf.ReadAll)
  pf.Close
  On Error GoTo 0
  If Len(pv) > 0 And Len(pv) < 6 Then urlBase = "http://127.0.0.1:" & pv
End If
W "open " & urlBase

If ready Then
  W "server ready -> open browser"
  sh.Run "cmd /c start " & urlBase, 0, False
Else
  W "ERROR: server not ready in 40s"
  sh.Run "cmd /c start notepad.exe """ & logPath & """", 0, False
  m = "启动失败：40 秒内服务没有就绪。"
  m = m & vbCrLf & vbCrLf & "下面会自动打开 启动日志.txt，请把它发给我。"
  MsgBox m, vbExclamation, "拾贝集"
End If
