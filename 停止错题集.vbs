' Essay Coach - stop background service (only kills the coach process)
CreateObject("WScript.Shell").Run _
  "powershell -NoProfile -Command ""Get-CimInstance Win32_Process | " & _
  "Where-Object { $_.CommandLine -like '*app.py*' } | " & _
  "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }""", 0, False
MsgBox "Essay Coach stopped.", vbInformation, "Essay Coach"
