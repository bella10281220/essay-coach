@echo off
chcp 65001 >nul
title 拾贝集 - 创建桌面快捷方式
cd /d "%~dp0"

echo 正在为你创建桌面图标「拾贝集」...

powershell -Command ^
"$ws = New-Object -ComObject WScript.Shell;" ^
"$desktop = [Environment]::GetFolderPath('Desktop');" ^
"$lnk = $ws.CreateShortcut(\"$desktop\拾贝集.lnk\");" ^
"$lnk.TargetPath = '%~dp0启动错题集（后台）.vbs';" ^
"$lnk.WorkingDirectory = '%~dp0';" ^
"$lnk.Description = '拾贝集 - 双击启动，无黑窗口';" ^
"$lnk.Save()"

if exist "%USERPROFILE%\Desktop\拾贝集.lnk" (
  echo.
  echo ✅ 完成！你的桌面上现在有一个「拾贝集」图标。
  echo    以后想用的时候：双击桌面图标就行 ——
  echo    不会有黑窗口，启动后自动打开网页。
  echo    （第一次用如果桌面没看到，刷新一下桌面）
) else (
  echo.
  echo ⚠️ 创建失败。也可以手动操作：
  echo    右键「启动错题集（后台）.vbs」→ 发送到 → 桌面快捷方式
)
echo.
pause
