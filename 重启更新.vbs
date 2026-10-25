' Auto-restart helper after in-app update (called by the server itself)
' 1) kill whatever still listens on port 5000
' 2) run the silent launcher vbs (it polls until server is up, then opens the browser)
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)

' kill any process still on port 5000 (ignore errors)
sh.Run "powershell -NoProfile -Command ""Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }""", 0, True

WScript.Sleep 2000

' run the silent launcher (Chinese filename via ChrW)
codes = Array(21551,21160,38169,39064,38598,65288,21518,21488,65289)
tgt = dir & "\"
For Each c In codes : tgt = tgt & ChrW(c) : Next
tgt = tgt & ".vbs"
sh.Run """" & tgt & """", 1, False
