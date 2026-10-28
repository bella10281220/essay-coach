' ShiBeiJi - silent launcher (no console window)
' - finds python automatically (python / py -3 / common install paths)
' - writes everything to 启动日志.txt
' - waits until the server really answers, then opens the browser
' ASCII only in code; Chinese text via ChrW to avoid encoding problems
Set sh = CreateObject("WScript.Shell")
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

W "=== launcher start === dir=" & dir

' ---------- 1. locate python ----------
cands = Array( _
  "python.exe", _
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe", _
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe", _
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe", _
  "%LOCALAPPDATA%\Programs\Python\Python310\python.exe", _
  "%LOCALAPPDATA%\Programs\Python\Python39\python.exe", _
  "C:\Python313\python.exe", "C:\Python312\python.exe", "C:\Python311\python.exe" _
)

py = ""
For Each c In cands
  path = sh.ExpandEnvironmentStrings(c)
  If InStr(path, "\") > 0 Then
    If fso.FileExists(path) Then py = """" & path & """"
  Else
    rc = -1
    On Error Resume Next
    rc = sh.Run("cmd /c " & path & " --version >nul 2>&1", 0, True)
    On Error GoTo 0
    If rc = 0 Then py = path
  End If
  If py <> "" Then Exit For
Next

If py = "" Then
  rc = -1
  On Error Resume Next
  rc = sh.Run("cmd /c py -3 --version >nul 2>&1", 0, True)
  On Error GoTo 0
  If rc = 0 Then py = "py -3"
End If

If py = "" Then
  W "ERROR: python not found"
  MsgBox ChrW(25214) & ChrW(19981) & ChrW(21040) & " Python" & vbCrLf & vbCrLf & _
    "1. " & ChrW(21040) & " https://www.python.org/downloads/ " & ChrW(19979) & ChrW(36733) & ChrW(23433) & ChrW(35013) & vbCrLf & _
    "2. " & ChrW(23433) & ChrW(35013) & ChrW(31532) & ChrW(19968) & ChrW(24149) & ChrW(21153) & ChrW(24517) & ChrW(21246) & ChrW(36873) & " Add python.exe to PATH" & vbCrLf & _
    "3. " & ChrW(35013) & ChrW(23436) & ChrW(20877) & ChrW(21452) & ChrW(20987) & ChrW(26412) & ChrW(25991) & ChrW(20214), vbExclamation, "ShiBeiJi"
  WScript.Quit
End If
W "python = " & py

' ---------- 2. already running? ----------
already = False
On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP")
http.Open "GET", "http://127.0.0.1:5000/", False
http.Send
If Err.Number = 0 Then If http.status = 200 Then already = True
Err.Clear
On Error GoTo 0

If already Then
  W "server already running, just open browser"
  sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
  WScript.Quit
End If

' ---------- 3. install deps ----------
W "checking dependencies..."
sh.Run "cmd /c " & py & " -m pip install -q -r requirements.txt >> """ & logPath & """ 2>&1", 0, True

' ---------- 4. start server hidden ----------
W "starting server..."
sh.Run "cmd /c " & py & " app.py >> """ & logPath & """ 2>&1", 0, False

' ---------- 5. wait until ready ----------
ready = False
For i = 1 To 60
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
  W "server ready, opening browser"
  sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
Else
  W "ERROR: server did not answer within 60s"
  sh.Run "cmd /c start notepad.exe """ & logPath & """", 0, False
  MsgBox ChrW(21551) & ChrW(21160) & ChrW(22833) & ChrW(36133) & ChrW(65292) & ChrW(35814) & ChrW(24773) & ChrW(35265) & " " & ChrW(21551) & ChrW(21160) & ChrW(26085) & ChrW(24535) & ".txt", vbExclamation, "ShiBeiJi"
End If
