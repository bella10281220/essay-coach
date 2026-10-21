@echo off
chcp 65001 >nul
title 英语作文错题集 - 更新
cd /d "%~dp0"

echo 📥 正在下载最新版本...
rem 把下面的网址改成你自己的最新版 zip 地址（如 GitHub 仓库的链接）
set DOWNLOAD_URL=https://example.com/essay-coach-latest.zip
curl -fL -o "%TEMP%\essay-coach-update.zip" "%DOWNLOAD_URL%"
if errorlevel 1 (
  echo ❌ 下载失败，检查网络或 DOWNLOAD_URL 是否已配置
  pause & exit /b 1
)

echo 💾 备份数据...
copy data\essays.db "%TEMP%\essays.db.bak" >nul

echo 📦 更新代码（数据保留）...
powershell -Command "Expand-Archive -Force '%TEMP%\essay-coach-update.zip' '%TEMP%\essay-coach-update'"
xcopy /e /y /i "%TEMP%\essay-coach-update\essay-coach" . /exclude:update-exclude.txt >nul

echo 🔁 恢复数据...
copy /y "%TEMP%\essays.db.bak" data\essays.db >nul

echo ✅ 更新完成！双击启动文件即可使用新版本。
pause
