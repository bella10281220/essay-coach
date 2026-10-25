@echo off
chcp 65001 >nul
title 拾贝集 - 在线更新
cd /d "%~dp0"

set LOG=更新日志.txt
echo ====== 更新开始 %date% %time% ====== > "%LOG%"

echo [1/4] 正在下载最新版本（详见 更新日志.txt）...
powershell -NoProfile -Command ^
 "$ErrorActionPreference='Stop';" ^
 "$h=@{};" ^
 "if (Test-Path 'gh-token.txt') { $h['Authorization']='Bearer '+((Get-Content 'gh-token.txt' -Raw).Trim()) };" ^
 "try { Invoke-WebRequest -Uri 'https://api.github.com/repos/bella10281220/essay-coach/zipball/main' -OutFile \"$env:TEMP\essay-coach-update.zip\" -Headers $h -UseBasicParsing; 'download ok' | Out-File '%LOG%' -Append }" ^
 "catch { $_.Exception.Message | Out-File '%LOG%' -Append; exit 1 }"
if errorlevel 1 (
  echo.
  echo ❌ 下载失败！详细原因已写入 更新日志.txt
  echo    现在帮你打开手动下载页面：把下载的 zip 解压覆盖到本文件夹即可（不会覆盖你的文章数据）。
  start "" "https://github.com/bella10281220/essay-coach/archive/refs/heads/main.zip"
  echo.
  pause
  exit /b 1
)

echo [2/4] 备份数据（你的作文不会丢）...
copy /y data\essays.db "%TEMP%\essays.db.bak" >nul 2>&1

echo [3/4] 覆盖更新代码（数据保留）...
powershell -NoProfile -Command ^
 "$ErrorActionPreference='Stop';" ^
 "Expand-Archive -Force \"$env:TEMP\essay-coach-update.zip\" \"$env:TEMP\essay-coach-update\";" ^
 "$d = Get-ChildItem \"$env:TEMP\essay-coach-update\" | Select-Object -First 1;" ^
 "Copy-Item (Join-Path $d.FullName '*') -Destination '.' -Recurse -Force -Exclude 'data','essays.db','gh-token.txt','更新日志.txt';" ^
 "'extract ok' | Out-File '%LOG%' -Append"

echo [4/4] 恢复数据检查...
if exist data\essays.db (
  echo       ✅ 你的文章数据完好
) else (
  copy /y "%TEMP%\essays.db.bak" data\essays.db >nul 2>&1
)

echo.
echo ✅ 更新完成！关掉旧的启动窗口，重新双击桌面「拾贝集」图标即可。
echo    页脚显示「拾贝集 v2.6」说明已更新到最新。
echo.
pause
