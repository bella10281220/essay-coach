' ============================================================
'  ShiBeiJi - 创建桌面图标（双击我一次就行）
'  只创建 1 个：拾贝集.lnk（图标 = 书籍封面）
'  同时删掉桌面上旧的「拾贝集 启动.vbs」，最终只留一个图标
'  本文件保存为 GBK 编码，Windows 中文系统可直接识别中文
' ============================================================

' ---------- 文件系统 + 外壳对象 ----------
Set fso = CreateObject("Scripting.FileSystemObject")
Set shl = CreateObject("WScript.Shell")

' ---------- 定位项目目录（含 app.py 的文件夹）----------
Function HasApp(p)
  HasApp = fso.FileExists(p & "\app.py")
End Function

scriptPath = WScript.ScriptFullName
dir  = fso.GetParentFolderName(scriptPath)
base = ""
If HasApp(dir) Then base = dir

' a) 同目录的子文件夹（例如 桌面\essay-coach）
If base = "" Then
  On Error Resume Next
  For Each sf In fso.GetFolder(dir).SubFolders
    If HasApp(sf.Path) Then base = sf.Path : Exit For
  Next
  On Error GoTo 0
End If

' b) 常见位置
If base = "" Then
  Dim cands(5)
  cands(0) = shl.ExpandEnvironmentStrings("%USERPROFILE%\Desktop\essay-coach")
  cands(1) = shl.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach")
  cands(2) = shl.ExpandEnvironmentStrings("%USERPROFILE%\Downloads\essay-coach-main")
  cands(3) = shl.ExpandEnvironmentStrings("%USERPROFILE%\Documents\essay-coach")
  cands(4) = "C:\essay-coach"
  cands(5) = "D:\essay-coach"
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
  msg = "找不到 app.py" & vbCrLf & vbCrLf
  msg = msg & "请把本文件放到 essay-coach 文件夹里再双击。" & vbCrLf
  msg = msg & "（不要把它单独拖到桌面上）"
  MsgBox msg, vbExclamation, "拾贝集"
  WScript.Quit
End If

launcher = base & "\拾贝集.vbs"
If Not fso.FileExists(launcher) Then
  msg = "找不到 拾贝集.vbs" & vbCrLf & vbCrLf
  msg = msg & "请确认新版安装包已解压覆盖到：" & vbCrLf & base
  MsgBox msg, vbExclamation, "拾贝集"
  WScript.Quit
End If

' ---------- 1. 清掉桌面上旧的多余图标 ----------
desk = shl.SpecialFolders("Desktop")

On Error Resume Next
If fso.FileExists(desk & "\拾贝集 启动.vbs") Then fso.DeleteFile desk & "\拾贝集 启动.vbs", True
If fso.FileExists(desk & "\拾贝集 - 快捷方式.lnk") Then fso.DeleteFile desk & "\拾贝集 - 快捷方式.lnk", True
On Error GoTo 0

' ---------- 2. 创建唯一的 .lnk ----------
lnkPath = desk & "\拾贝集.lnk"
ok      = False
errMsg  = ""

On Error Resume Next
Err.Clear
Set lnk = shl.CreateShortcut(lnkPath)
lnk.TargetPath       = shl.ExpandEnvironmentStrings("%WINDIR%") & "\System32\wscript.exe"
lnk.Arguments        = Chr(34) & launcher & Chr(34)
lnk.WorkingDirectory = base
lnk.Description      = "拾贝集"
lnk.IconLocation     = base & "\static\favicon.ico,0"
lnk.WindowStyle      = 7
lnk.Save
errMsg = Err.Description
On Error GoTo 0

ok = fso.FileExists(lnkPath)

' ---------- 3. 告诉用户 ----------
If ok Then
  msg = "完成！" & vbCrLf & vbCrLf
  msg = msg & "桌面上现在只有 1 个图标：拾贝集" & vbCrLf
  msg = msg & "双击它就会自动启动并打开网页（全程没有黑窗口）。" & vbCrLf & vbCrLf
  msg = msg & "如果图标还是旧的：右键 → 属性 → 更改图标 → 浏览到" & vbCrLf
  msg = msg & base & "\static\favicon.ico"
  MsgBox msg, vbInformation, "拾贝集"
Else
  msg = "创建失败：" & errMsg & vbCrLf & vbCrLf
  msg = msg & "手动方法：右键 拾贝集.vbs → 发送到 → 桌面快捷方式"
  MsgBox msg, vbExclamation, "拾贝集"
End If
