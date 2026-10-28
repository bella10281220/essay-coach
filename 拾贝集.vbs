' ============================================================
'  ShiBeiJi launcher  -  double-click this file to start
'  1) kills any old instance on port 5000 (fixes "connection error")
'  2) finds python automatically
'  3) starts the server with NO console window
'  4) opens the browser when the server is ready
'  All output goes to 启动日志.txt
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
W "dir = " & dir

' ---------- 1. kill old instance on 5000 ----------
W "step1: free port 5000"
On Error Resume Next
sh.Run "powershell -NoProfile -WindowStyle Hidden -Command ""Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }""", 0, True
On Error GoTo 0
WScript.Sleep 1500

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
  ' search common install locations
  roots = Array(sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python"), _
                sh.ExpandEnvironmentStrings("%PROGRAMFILES%\Python"), _
                sh.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python"), _
                "C:\Python", "C:\")
  For Each rt In roots
    If py = "" And fso.FolderExists(rt) Then
      For Each sub_ In fso.GetFolder(rt).SubFolders
        p = sub_.Path & "\python.exe"
        If fso.FileExists(p) Then py = """" & p & """" : Exit For
      Next
    End If
  Next
End If

If py = "" Then
  ' last resort: ask windows where python.exe is
  On Error Resume Next
  tempF = sh.ExpandEnvironmentStrings("%TEMP%") & "\pywhere.txt"
  sh.Run "cmd /c where python > """ & tempF & """ 2>nul", 0, True
  If fso.FileExists(tempF) Then
    Set tf = fso.OpenTextFile(tempF, 1)
    If Not tf.AtEndOfStream Then py = """" & Trim(tf.ReadLine) & """"
    tf.Close
  End If
  On Error GoTo 0
End If

If py = "" Then
  W "ERROR: python not found"
  MsgBox ChrW(25214) & ChrW(19981) & ChrW(21040) & " Python" & vbCrLf & vbCrLf & _
    ChrW(35831) & ChrW(21040) & " https://www.python.org/downloads/ " & ChrW(19979) & ChrW(36733) & vbCrLf & _
    ChrW(23433) & ChrW(35013) & ChrW(26102) & ChrW(24517) & ChrW(21246) & ChrW(36873) & " Add python.exe to PATH" & vbCrLf & _
    ChrW(28982) & ChrW(21518) & ChrW(37325) & ChrW(26032) & ChrW(21452) & ChrW(20987) & ChrW(26412) & ChrW(25991) & ChrW(20214), vbExclamation, "ShiBeiJi"
  WScript.Quit
End If
W "python = " & py

' ---------- 3. deps ----------
W "step3: check deps"
sh.Run "cmd /c " & py & " -m pip install -q -r requirements.txt >> """ & logPath & """ 2>&1", 0, True

' ---------- 4. start server ----------
W "step4: start server"
sh.Run "cmd /c " & py & " app.py >> """ & logPath & """ 2>&1", 0, False

' ---------- 5. wait and open ----------
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
  W "server ready"
  sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
Else
  W "ERROR: server not ready in 40s"
  sh.Run "cmd /c start notepad.exe """ & logPath & """", 0, False
  MsgBox ChrW(21551) & ChrW(21160) & ChrW(22833) & ChrW(36133) & ChrW(65292) & ChrW(35814) & ChrW(24773) & ChrW(24050) & ChrW(20889) & ChrW(20837) & " " & ChrW(21551) & ChrW(21160) & ChrW(26085) & ChrW(24535) & ".txt", vbExclamation, "ShiBeiJi"
End If
