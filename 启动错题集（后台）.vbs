' Essay Coach - silent background start (no console window)
' Waits until the server is really up before opening the browser.
' Stop the service with stop-essay-coach.vbs
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = Replace(WScript.ScriptFullName, "\" & WScript.ScriptName, "")

' Install dependencies on first run (may take minutes; log for troubleshooting)
sh.Run "cmd /c (python -m pip install -q -r requirements.txt || py -3 -m pip install -q -r requirements.txt) >> start-log.txt 2>&1", 0, True

' Start server silently
sh.Run "cmd /c (python app.py >> start-log.txt 2>&1 || py -3 app.py >> start-log.txt 2>&1)", 0, False

' Poll until the server answers, then open the browser (max 90s)
Set http = CreateObject("MSXML2.XMLHTTP")
ready = False
For i = 1 To 45
  WScript.Sleep 2000
  On Error Resume Next
  http.Open "GET", "http://127.0.0.1:5000/", False
  http.Send
  If Err.Number = 0 Then
    If http.status = 200 Then ready = True
  End If
  On Error GoTo 0
  If ready Then Exit For
Next

If ready Then
  sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
Else
  ' Not ready in 90s: open the log so the user can see why
  sh.Run "cmd /c start notepad.exe start-log.txt", 0, False
End If
