#!/bin/bash
# 一键更新错题集（保留你的所有数据）
# 用法：./update.sh  或双击（macOS: 更新.command）
# 项目代码从 DOWNLOAD_URL 下载；把项目传到 GitHub 后改成你的仓库 zip 地址即可
cd "$(dirname "$0")"

GH_TOKEN_FILE="$(dirname "$0")/gh-token.txt"
DOWNLOAD_URL="${DOWNLOAD_URL:-https://api.github.com/repos/bella10281220/essay-coach/zipball/main}"
AUTH=()
[ -f "$GH_TOKEN_FILE" ] && AUTH=(-H "Authorization: Bearer $(cat "$GH_TOKEN_FILE" | tr -d '[:space:]')")
DB="data/essays.db"

echo "📥 正在下载最新版本..."
curl -fL "${AUTH[@]}" -o /tmp/essay-coach-update.zip "$DOWNLOAD_URL" || { echo "❌ 下载失败，检查网络或 DOWNLOAD_URL"; exit 1; }

echo "💾 备份数据..."
cp "$DB" /tmp/essays.db.bak 2>/dev/null

echo "📦 更新代码（数据保留）..."
unzip -oq /tmp/essay-coach-update.zip -d /tmp/essay-coach-update
rsync -a --exclude "data/" --exclude "*.db" \
  --exclude-from "rsync-exclude.txt" /tmp/essay-coach-update/bella10281220-essay-coach-*/ ./

echo "🔁 恢复数据..."
cp /tmp/essays.db.bak "$DB" 2>/dev/null

echo "✅ 更新完成！双击启动文件即可使用新版本。"
