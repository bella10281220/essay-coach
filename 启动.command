#!/bin/bash
# 英语作文错题集 · 一键启动（Linux / macOS 通用）
# 用法：双击启动（macOS 用 启动.command），或在终端里运行 ./start.sh
set -e
cd "$(dirname "$0")"

echo "📖 英语作文错题集 启动中..."

# 1. 检查 python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 没有找到 python3，请先安装：https://www.python.org/downloads/"
  exit 1
fi

# 2. 安装依赖（已装则秒过）
echo "📦 检查依赖..."
python3 -m pip install -q -r requirements.txt 2>/dev/null || \
  python3 -m pip install -q --user -r requirements.txt || true

# 3. 检查 Ollama（没装也能启动，会以演示模式运行）
if ! curl -s -o /dev/null --max-time 2 http://127.0.0.1:11434/api/tags; then
  echo ""
  echo "⚠️  没检测到 Ollama 服务，将以「演示模式」启动（界面可用，批改为模拟数据）。"
  echo "   启用真正 AI 批改：安装 Ollama（https://ollama.com/download）后运行 ollama pull qwen2.5:7b"
  echo ""
fi

# 4. 启动并自动打开浏览器
URL="http://127.0.0.1:5000"
echo "🚀 启动服务：$URL"
( sleep 2
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  else echo "请手动在浏览器打开: $URL"; fi ) &

python3 app.py
