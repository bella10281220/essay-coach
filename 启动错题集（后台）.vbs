' Essay Coach - silent background start (no console window)
' Stop the service with stop-essay-coach.vbs
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = Replace(WScript.ScriptFullName, "\" & WScript.ScriptName, "")

' Install dependencies on first run (skips fast when already installed)
sh.Run "cmd /c (python -m pip install -q -r requirements.txt || py -3 -m pip install -q -r requirements.txt) >> start-log.txt 2>&1", 0, True

' Start server silently
sh.Run "cmd /c python app.py >> start-log.txt 2>&1 || py -3 app.py >> start-log.txt 2>&1", 0, False

' Open browser after 2s
WScript.Sleep 2000
sh.Run "cmd /c start http://127.0.0.1:5000", 0, False
