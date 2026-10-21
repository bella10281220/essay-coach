@echo off
chcp 65001 >nul
title 英语作文错题集
cd /d "%~dp0"

echo ============================================
echo   英语作文错题集 正在启动...
echo ============================================

rem ---- 1. 找到可用的 Python（自动尝试 python / py）----
set PYTHON=
python --version >nul 2>&1 && set PYTHON=python
if not defined PYTHON (
  py -3 --version >nul 2>&1 && set PYTHON=py -3
)
if not defined PYTHON (
  echo.
  echo ❌ 找不到 Python。请检查：
  echo    1. 到 https://www.python.org/downloads/ 下载安装
  echo    2. 安装第一屏务必勾选 "Add python.exe to PATH"
  echo    3. 如果双击 python 打开的是微软商店，说明装的是商店版，
  echo       请卸载后重新安装 python.org 的版本
  echo.
  echo 详细日志见同目录的 启动日志.txt
  pause
  exit /b 1
)
echo [1/3] Python 已找到：%PYTHON%

rem ---- 2. 安装依赖（已装则秒过）----
echo [2/3] 检查依赖...
%PYTHON% -m pip install -q -r requirements.txt >> 启动日志.txt 2>&1

rem ---- 3. 启动服务并打开浏览器 ----
echo [3/3] 启动服务：http://127.0.0.1:5000
echo.
echo ★ 使用期间请不要关闭这个窗口；最小化即可。
echo ★ 想要"完全没有窗口"的版本，双击「启动错题集（后台）.vbs」
echo.
start "" http://127.0.0.1:5000
%PYTHON% app.py

rem ---- 如果走到这里说明服务异常退出了，把日志留下 ----
echo.
echo ⚠️ 服务意外退出了。错误详情已写入 启动日志.txt（末尾几行）。
echo    常见原因：5000 端口被占用 / 依赖安装失败。
pause
