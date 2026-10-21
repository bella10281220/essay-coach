@echo off
chcp 65001 >nul
title 拾贝集 - 在线更新
cd /d "%~dp0"

echo ============================================
echo   拾贝集 - 在线更新
echo ============================================
echo.

set DOWNLOAD_URL=https://api.github.com/repos/bella10281220/essay-coach/zipball/main
set AUTH=
if exist "%~dp0gh-token.txt" set /p AUTH=<"%~dp0gh-token.txt"

echo [1/4] 正在下载最新版本...
if defined AUTH (
  curl -sL -w "%%{http_code}" -H "Authorization: Bearer %AUTH%" -o "%TEMP%\essay-coach-update.zip" "%DOWNLOAD_URL%" > "%TEMP%\essay-coach-http.txt"
) else (
  curl -sL -w "%%{http_code}" -o "%TEMP%\essay-coach-update.zip" "%DOWNLOAD_URL%" > "%TEMP%\essay-coach-http.txt"
)
set /p HTTPCODE=<"%TEMP%\essay-coach-http.txt"
echo       服务器返回码：%HTTPCODE%

if not "%HTTPCODE%"=="200" (
  echo.
  echo ❌ 下载失败（返回码 %HTTPCODE%）。原因对照：
  echo    · 404  → 仓库还是【私密】状态。两个办法二选一：
  echo        办法A：打开 GitHub 仓库页面 → Settings → 拉到最底部 Danger Zone
  echo               → Change visibility → 改成 Public，然后再双击本文件
  echo        办法B：在项目文件夹里新建一个记事本文件，命名为 gh-token.txt，
  echo               里面只粘贴你的 GitHub token（一整行），保存后再试
  echo    · 其他 → 网络问题，请检查能否打开 github.com
  echo.
  pause
  exit /b 1
)

echo [2/4] 备份数据（你的作文不会丢）...
copy /y data\essays.db "%TEMP%\essays.db.bak" >nul

echo [3/4] 覆盖更新代码（数据保留）...
powershell -Command "Expand-Archive -Force '%TEMP%\essay-coach-update.zip' '%TEMP%\essay-coach-update'"
for /d %%d in ("%TEMP%\essay-coach-update\*essay-coach*") do xcopy /e /y /i "%%d" . /exclude:update-exclude.txt >nul

echo [4/4] 恢复数据...
copy /y "%TEMP%\essays.db.bak" data\essays.db >nul

echo.
echo ✅ 更新完成！双击「启动错题集.bat」即可使用新版本。
echo.
pause
