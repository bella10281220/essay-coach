#!/usr/bin/env python3
"""英语作文错题集 · 本地 AI 批改
数据全部保存在本地 SQLite，AI 批改调用本机 Ollama 模型（免费）。
启动: python3 app.py  → 浏览器打开 http://127.0.0.1:5000
"""
import difflib
import os
import socket
import sys
import threading

# Windows 控制台默认 GBK，任何 print 到 emoji / 生僻字符都会抛
# UnicodeEncodeError 把整个服务直接崩掉（这是"双击没反应"的真正原因）。
# 放在文件最顶部，保证在任何 print 之前完成重配置。
try:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
except Exception:  # noqa: BLE001
    pass


def log(*args):
    """安全打印：绝不因为编码问题抛异常。"""
    try:
        print(*args, flush=True)
    except Exception:  # noqa: BLE001
        try:
            print(" ".join(str(a) for a in args).encode("ascii", "ignore").decode("ascii"), flush=True)
        except Exception:  # noqa: BLE001
            pass


VERSION = "3.5"   # 页脚显示，用于确认正在运行的是新版本


def pick_port(default=5000, span=20):
    """端口被占用时自动向后找空闲端口，避免"旧进程没退干净"导致启动失败。"""
    for p in range(default, default + span):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
            return p
        except OSError:
            continue
    return default

import html as html_mod
import json
import os
import re
import sys
import sqlite3
import time

import requests
from flask import Flask, g, jsonify, redirect, render_template, request, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "essays.db")

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

# 常用 OpenAI 兼容 API 预设（base_url + 默认模型）
API_PRESETS = {
    "openai":   {"base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "deepseek": {"base": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "moonshot": {"base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "zhipu":    {"base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "siliconflow": {"base": "https://api.siliconflow.cn/v1", "model": "Qwen/Qwen2.5-7B-Instruct"},
}

app = Flask(__name__)


@app.context_processor
def inject_version():
    return {"version": VERSION}
app.jinja_env.filters["timefmt"] = lambda ts: time.strftime(
    "%Y-%m-%d %H:%M", time.localtime(ts))

# ---------------------------------------------------------------- 数据库

def db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute(
            """CREATE TABLE IF NOT EXISTS essays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                wanted TEXT DEFAULT '',        -- 我想表达但不会说的意思
                correction TEXT DEFAULT '',    -- 批改结果 JSON
                created_at REAL NOT NULL,
                corrected INTEGER DEFAULT 0
            )"""
        )
        g.db.execute(
            """CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                essay_ids TEXT NOT NULL,       -- 参与回顾的作文 id 列表
                report TEXT NOT NULL,          -- 回顾报告 JSON
                created_at REAL NOT NULL
            )"""
        )
        g.db.execute(
            """CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            )"""
        )
        g.db.execute(
            """CREATE TABLE IF NOT EXISTS qa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                essay_id INTEGER NOT NULL,
                skey TEXT NOT NULL,            -- 追问针对的句子（原句）
                q TEXT NOT NULL,               -- 学生的追问
                a TEXT NOT NULL,               -- AI 的回答
                created_at REAL NOT NULL
            )"""
        )
        g.db.execute(
            """CREATE TABLE IF NOT EXISTS phrases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chinese TEXT NOT NULL,          -- 我想表达的中文
                english TEXT NOT NULL,          -- AI 给的地道英文
                note TEXT DEFAULT '',           -- 讲解
                created_at REAL NOT NULL
            )"""
        )
        g.db.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('review_interval','10')"
        )
        g.db.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('model','qwen2.5:7b')"
        )
        g.db.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('provider','ollama')"
        )
        g.db.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('api_base','')"
        )
        g.db.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('api_key','')"
        )
        g.db.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('api_model','')"
        )
        # 旧库迁移：新增"外部导入"字段
        for col_sql in ("ALTER TABLE essays ADD COLUMN imported INTEGER DEFAULT 0",
                        "ALTER TABLE essays ADD COLUMN raw_import TEXT DEFAULT ''"):
            try:
                g.db.execute(col_sql)
            except sqlite3.OperationalError:
                pass  # 字段已存在
        g.db.commit()
    return g.db


@app.teardown_appcontext
def close_db(_):
    db_ = g.pop("db", None)
    if db_:
        db_.close()


def get_setting(key, default=""):
    row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db().execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    db().commit()


# ---------------------------------------------------------------- Ollama 调用

_AI_ERROR = {"msg": ""}


def call_ai(messages, timeout=600):
    """统一 AI 调用入口。
    provider=ollama → 本机 Ollama（免费）
    provider=api    → OpenAI 兼容 API（GPT/DeepSeek/Kimi/智谱等）
    失败返回 None（调用方进入演示模式兜底），失败原因记录在 _AI_ERROR
    """
    _AI_ERROR["msg"] = ""
    try:
        if get_setting("provider", "ollama") == "api":
            return call_openai_api(messages, timeout)
        return call_ollama(messages, timeout)
    except Exception as e:  # noqa: BLE001
        _AI_ERROR["msg"] = f"{type(e).__name__}: {e}"[:300]
        log("[AI 调用失败]", type(e).__name__, e)
        return None


def call_ollama(messages, timeout=600):
    """调用本地 Ollama"""
    model = get_setting("model", "qwen2.5:7b")
    r = requests.post(
        OLLAMA_URL,
        json={"model": model, "messages": messages, "stream": False,
              "options": {"temperature": 0.3}},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def call_openai_api(messages, timeout=300):
    """调用 OpenAI 兼容 API（openai / deepseek / moonshot / zhipu / siliconflow 等）"""
    base = get_setting("api_base", "").rstrip("/")
    key = get_setting("api_key", "")
    model = get_setting("api_model", "") or "gpt-4o-mini"
    if not base or not key:
        log("[API not configured] set api_base and api_key in settings")
        return None
    r = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": messages, "temperature": 0.3},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def extract_json(text):
    """从模型输出中提取 JSON（容忍 ```json 代码块等）"""
    if not text:
        return None
    text = re.sub(r"```(json)?|```", "", text).strip()
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- 批改 prompt

CORRECT_PROMPT = """你是一位专业耐心的英语写作老师。学生正在用"错题集"的方式练习英语写作，请批改下面这篇作文。

要求：
1. 逐句批改。每个句子标记类型：
   - "error"：语法/拼写/用词错误，必须修正。**铁律：只修改真正错的部分**。学生的时态、句式、语序、结构必须原样保留——禁止把一般过去时改成完成时、禁止主动被动互换、禁止拆句/合句/调换从句位置。哪怕学生的句式很罕见，也只在错点上做最小修补。**例外**：如果整个句子的语法结构本身就是错误且无法在小修补内成立的（如主谓结构完全混乱、时态框架自相矛盾），允许整句重写，但重写时必须保留学生的原意和尽量保留其用词，并在 note 里说明"这句结构问题太多，所以整句重写"。
   - "optimize"：语法正确但有更地道自然的表达，给出优化建议。**同样不许改变句式结构**，只替换或补充个别词汇。
   - "complex_kept"：学生尝试的复杂句（长句、从句、倒装、非谓语等），即使有小错误也要**重点保留其结构**，只做最小限度的改造，绝不简化；如果没有错误请直接保留并表扬。
   - "good"：写得好的句子。
2. **词汇洁癖（极重要）**：学生在一篇文章里用了近义表达的变化（如 happy / glad / delighted / "my mood is as bright as sunshine"），这是优点，必须原样保留，**严禁全部统一成同一个词**。修改用词时先看上下文：如果该词在这里是正确且合适的，一个字都不要动；只有真的用错或明显不合适才换，且替换词要与上下文语境匹配，避免与文中其他句子重复用词。note 里如果要建议别的说法，用"也可以说…"的口吻，不要替学生改掉原文。
3. 指出可优化的词汇和表达，放入 vocab 列表（错的或可优化的词要明确指出）。
4. 给出两个改写版本：
   - version_current：贴合学生当前水平的改写（用词和句式接近学生自己能写出的程度，方便他今天就能模仿）。
   - version_current：贴合学生当前水平的改写（用词和句式接近学生自己能写出的程度，方便他今天就能模仿；同样遵守"最小改动"铁律）。
   - version_advanced：进阶版本（更高级的词汇、从句和衔接，供学生学习目标）。
5. 如果学生提供了 wanted（他想表达但不知道英文怎么说的意思），在 wanted_phrases 里给出对应的地道英文表达和简短讲解；没提供就给空数组。
5. 给出总体评价 summary 和 1-10 分的 score。注意：error_count 按**句子**计数——一句话里错几个词都只算 1 个错误句；optimize_count 同理（有优化建议的句子数）。
7. version_advanced 之外，给出 version_advanced_notes：列出进阶版相对当前水平版的关键差异（2-5 条），说明每处改动为什么更好。

只输出 JSON，格式如下（不要输出其他任何文字）：
{
 "summary": "...", "score": 0, "error_count": 0, "optimize_count": 0,
 "sentences": [
   {"original": "学生原句", "type": "error|optimize|complex_kept|good",
    "revised": "改后句子", "note": "中文讲解，说明错在哪/为什么这样改/复杂结构保留了什么"}
 ],
 "vocab": [{"original": "原词/表达", "suggestion": "建议", "note": "中文说明"}],
 "wanted_phrases": [{"chinese": "学生想表达的意思", "english": "地道英文", "note": "简短讲解"}],
 "version_current": "贴合当前水平的整篇改写",
 "version_advanced": "进阶版本整篇改写",
 "version_advanced_notes": [{"change": "原表达 → 进阶表达", "why": "为什么这样更好"}]
}
"""


REVIEW_PROMPT = """你是一位英语写作教练。学生把一批作文的批改结果交给你，请写一份回顾报告：指出这些作文里**细小的进步和变化**（哪怕很微小，比如某个语法错误不再出现、开始使用从句、连接词变丰富了），也指出反复出现的顽固错误和下一步最值得练的 1-3 个点。语气鼓励但具体，用中文。

只输出 JSON：
{
 "progress": ["进步点1（引用具体例子）", "..."],
 "recurring": ["顽固错误1（出现次数/例子）", "..."],
 "next_steps": ["下一步建议1", "..."],
 "comment": "总体寄语"
}
"""

DEMO_CORRECTION = {
    "summary": "（演示模式：未检测到本机 Ollama，这是一份模拟批改，用于体验界面功能。）整体结构清晰，有两个语法错误和几处可以更地道的表达，你的复杂句尝试值得肯定。",
    "score": 7,
    "error_count": 2,
    "optimize_count": 2,
    "sentences": [
        {"original": "Yesterday I have went to the library with my friend.",
         "type": "error",
         "revised": "Yesterday I went to the library with my friend.",
         "note": "yesterday 表明是过去时间，要用一般过去时 went，并删掉多余的 have。只改了时态，句子结构原样保留。"},
        {"original": "The book which I borrowed it was very interesting.",
         "type": "error",
         "revised": "The book which I borrowed was very interesting.",
         "note": "定语从句中 which 已经充当 borrowed 的宾语，不能再重复 it。这个复杂句结构很好，保留 which 引导的定语从句，只删掉多余的 it。"},
        {"original": "It is very good for study.",
         "type": "optimize",
         "revised": "It is really helpful for my studies.",
         "note": "very good 太笼统，helpful for my studies 更具体自然。"},
        {"original": "Not only did I read books, but also I met an old classmate there.",
         "type": "complex_kept",
         "revised": "Not only did I read books, but I also met an old classmate there.",
         "note": "Not only 倒装句很棒！结构完全保留，只把 but also I 调整为更地道的 but I also。"},
        {"original": "I love reading in quiet places.",
         "type": "good",
         "revised": "I love reading in quiet places.",
         "note": "简洁准确，没有问题。"},
    ],
    "vocab": [
        {"original": "very good", "suggestion": "beneficial / rewarding", "note": "表达更具体，避免笼统的 good。"},
        {"original": "interesting", "suggestion": "fascinating / a page-turner", "note": "想要更生动可以使用更高级的词。"},
    ],
    "wanted_phrases": [
        {"chinese": "书看得很入迷，忘了时间",
         "english": "I was so absorbed in the book that I lost track of time.",
         "note": "be absorbed in 表示沉浸其中；lose track of time 表示忘了时间。"},
        {"chinese": "收获颇丰",
         "english": "It was a truly rewarding experience.",
         "note": "rewarding 形容有收获的经历，比 helpful 更地道。"},
    ],
    "version_current": "Yesterday I went to the library with my friend. The book which I borrowed was very interesting, and it is really helpful for my studies. Not only did I read books, but I also met an old classmate there. I love reading in quiet places.",
    "version_advanced": "Yesterday I paid a visit to the library with a friend of mine. The book I had borrowed proved fascinating — so much so that it became genuinely helpful to my studies. Not only did I immerse myself in reading, but I also unexpectedly ran into an old classmate there. Quiet places, for me, are where reading truly comes alive.",
}

DEMO_REVIEW = {
    "progress": [
        "时态意识提升：前几篇常出现 I have went 这类时态混用，最近 3 篇基本都正确使用了过去时。",
        "开始尝试倒装句和定语从句（如 Not only did I... / which I borrowed），句式丰富度在提高。",
    ],
    "recurring": [
        "定语从句里容易重复代词（which ... it），已出现 2 次。",
        "very good / very interesting 等笼统表达使用频率偏高，可以多积累具体形容词。",
    ],
    "next_steps": [
        "专项练习：写 5 个包含 which/that 引导定语从句的句子，注意从句内不再多加代词。",
        "每次作文刻意用 2 个替换 very + 形容词的具体词汇。",
    ],
    "comment": "（演示模式报告）短短几篇已经能看到肉眼可见的小进步，坚持写下去，进步会越积越多。",
}


# ---------------------------------------------------------------- 路由

@app.route("/")
def index():
    essays = db().execute(
        "SELECT id, title, created_at, corrected, "
        "  CASE WHEN corrected=1 THEN json_extract(correction,'$.score') END AS score, "
        "  CASE WHEN corrected=1 THEN json_extract(correction,'$.error_count') END AS errors, "
        "  CASE WHEN corrected=1 THEN json_extract(correction,'$.optimize_count') END AS opts "
        "FROM essays ORDER BY id DESC"
    ).fetchall()
    interval = int(get_setting("review_interval", "10"))
    total = len(essays)
    reviewed = db().execute("SELECT COUNT(*) c FROM reviews").fetchone()["c"]
    return render_template(
        "index.html", essays=essays, interval=interval, total=total,
        reviews_count=reviewed, model=get_setting("model", "qwen2.5:7b"),
        provider=get_setting("provider", "ollama"),
        api_base=get_setting("api_base", ""),
        api_key=get_setting("api_key", ""),
        api_model=get_setting("api_model", ""),
        presets=API_PRESETS,
        bookmarklet=make_bookmarklet("new"), bookmarklet_paste=make_bookmarklet_paste(),
        bookmarklet_import=make_bookmarklet("imported"),
    )


@app.route("/api/ai_status")
def ai_status():
    """检测 AI 连接状态：Ollama 是否在线 + 已下载的模型列表；API 是否可用"""
    out = {"provider": get_setting("provider", "ollama"),
           "ollama": {"ok": False, "models": []},
           "api": {"ok": False, "configured": False}}
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        r.raise_for_status()
        out["ollama"]["ok"] = True
        out["ollama"]["models"] = [m["name"] for m in r.json().get("models", [])]
    except Exception as e:  # noqa: BLE001
        out["ollama"]["error"] = ("Ollama 服务未运行或未安装。"
                                  "请到 https://ollama.com/download 安装并启动。")
    base = get_setting("api_base", "")
    key = get_setting("api_key", "")
    model = get_setting("api_model", "")
    if base and key:
        out["api"]["configured"] = True
        try:
            r = requests.post(
                f"{base.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model or "gpt-4o-mini",
                      "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 5},
                timeout=20)
            r.raise_for_status()
            out["api"]["ok"] = True
            out["api"]["model"] = model
        except requests.HTTPError as e:  # noqa: PERF203
            code = e.response.status_code
            hint = {401: "API Key 无效", 403: "该 Key 无权限",
                    404: "地址或模型名不对（检查是否以 /v1 结尾、模型名拼写）",
                    429: "额度不足或被限速"}.get(code, f"HTTP {code}")
            out["api"]["error"] = hint
        except Exception as e:  # noqa: BLE001
            out["api"]["error"] = f"连不上：{str(e)[:150]}"
    else:
        out["api"]["error"] = "尚未配置（填好 API 地址和 Key 后才能测试）"
    return jsonify(out)


PHRASE_PATTERNS = [
    # "take up 是一个短语动词" / "pay attention to 表示……"
    re.compile(r"([A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){0,4})\s*"
               r"(?:是|是一个|表示|意思是|指的是|为|：|:)"),
    # "句型：某件事 + takes + 时间"
    re.compile(r"句型\s*[:：]\s*([^\n]{2,60})"),
    # "XX 短语 / XX 搭配"
    re.compile(r"([A-Za-z][A-Za-z'\- ]{2,30})\s*(?:短语|搭配|固定表达|短语动词)"),
]

def extract_phrases_from_notes(c):
    """从逐句讲解里挖出短语/句型，返回 vocab 结构"""
    found, seen = [], set()
    for sn in c.get("sentences", []):
        note = sn.get("note") or ""
        if not note:
            continue
        # 按行/句拆开逐条匹配
        chunks = re.split(r"[\n。；;！!？?]", note)
        for ch in chunks:
            ch = ch.strip()
            if not ch or len(ch) < 4:
                continue
            for pat in PHRASE_PATTERNS:
                for m in pat.finditer(ch):
                    eng = (m.group(1) or "").strip(" ，,。.")
                    if not eng or len(eng) < 3:
                        continue
                    if not re.search(r"[A-Za-z]", eng):
                        continue
                    # 过滤掉纯语法术语
                    if eng.lower() in ("english", "i", "you", "it", "this", "that"):
                        continue
                    key = eng.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    # 说明取整句中文
                    zh = ch if re.search(r"[\u4e00-\u9fff]", ch) else ""
                    found.append({"original": eng[:80],
                                  "suggestion": zh[:80] or "(见原句讲解)",
                                  "note": zh[:200]})
    return found


def clean_book_text(c, fallback_content=""):
    """书架正文：只留干净的修改后文章，去掉 AI 的说明/编号/理由混杂内容"""
    cand = (c or {}).get("version_current") or ""
    cand = cand.strip()
    if not cand:
        return (fallback_content or "").strip()

    lines = []
    for ln in cand.splitlines():
        t = ln.strip()
        if not t:
            lines.append("")
            continue
        # 剔除明显是"讲解"的行
        if re.match(r"^([①-⑳]|\d+[.、)）]|[-•*]\s|#)", t):
            continue
        if re.search(r"(错误|语法|用词|修改|建议|说明|理由|保留|注意|表示|例如|例句|优化|类｜|批改|版本|整理)", t) and \
           len(re.findall(r"[\u4e00-\u9fff]", t)) > 3:
            continue
        # 中文占比过高的行（讲解）也剔除
        zh = len(re.findall(r"[\u4e00-\u9fff]", t))
        if zh > max(4, len(t) * 0.25):
            continue
        lines.append(t)
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text or cand


@app.route("/shelf")
def shelf():
    """书架：改好的文章像书一样摆着，点开阅读"""
    books = []
    for e in db().execute(
            "SELECT * FROM essays WHERE corrected=1 ORDER BY id DESC").fetchall():
        c = json.loads(e["correction"]) if e["correction"] else {}
        books.append({
            "id": e["id"], "title": c.get("book_title") or e["title"],
            "date": time.strftime("%Y-%m-%d", time.localtime(e["created_at"])),
            "score": c.get("score"),
            "text": clean_book_text(c, e["content"]),
            "advanced": (c.get("version_advanced") or "").strip(),
        })
    return render_template("shelf.html", books=books)


@app.route("/rename/<int:essay_id>", methods=["POST"])
def rename(essay_id):
    """书架改名"""
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()[:40]
    if not name:
        return jsonify({"error": "书名不能为空"}), 400
    e = db().execute("SELECT correction FROM essays WHERE id=?", (essay_id,)).fetchone()
    if not e:
        return jsonify({"error": "不存在"}), 404
    db().execute("UPDATE essays SET title=? WHERE id=?", (name, essay_id))
    if e["correction"]:
        c = json.loads(e["correction"])
        c["book_title"] = name
        db().execute("UPDATE essays SET correction=? WHERE id=?",
                     (json.dumps(c, ensure_ascii=False), essay_id))
    db().commit()
    return jsonify({"ok": True, "name": name})


@app.route("/write")
def write_page():
    """写作文页：表单 + 错题本翻页浏览"""
    return render_template("write.html", essays=_essay_list(),
                           interval=int(get_setting("review_interval", "10")),
                           error=None, form_title="", form_content="", form_wanted="")


@app.route("/new", methods=["POST"])
def new_essay():
    title = request.form.get("title", "").strip()
    if not title:
        n = db().execute("SELECT COUNT(*) c FROM essays").fetchone()["c"] + 1
        title = f"第{n}篇 · {time.strftime('%Y-%m-%d')}"
    content = request.form.get("content", "").strip()
    wanted = request.form.get("wanted", "").strip()
    if not content:
        return render_template("write.html",
                               essays=_essay_list(),
                               interval=int(get_setting("review_interval", "10")),
                               error="作文正文不能为空——请把英语作文写在「英语作文正文」那个大输入框里，"
                                     "标题和「我想说」栏才是可选的。",
                               form_title=title, form_content="", form_wanted=wanted), 400
    cur = db().execute(
        "INSERT INTO essays(title, content, wanted, created_at) VALUES(?,?,?,?)",
        (title, content, wanted, time.time()),
    )
    db().commit()
    return redirect(url_for("essay", essay_id=cur.lastrowid))


def _essay_list():
    return db().execute(
        "SELECT id, title, created_at, corrected, imported, "
        "  CASE WHEN corrected=1 THEN json_extract(correction,'$.score') END AS score, "
        "  CASE WHEN corrected=1 THEN json_extract(correction,'$.error_count') END AS errors, "
        "  CASE WHEN corrected=1 THEN json_extract(correction,'$.optimize_count') END AS opts "
        "FROM essays ORDER BY id DESC"
    ).fetchall()


@app.route("/essay/<int:essay_id>")
def essay(essay_id):
    e = db().execute("SELECT * FROM essays WHERE id=?", (essay_id,)).fetchone()
    if not e:
        return "作文不存在", 404
    correction = json.loads(e["correction"]) if e["correction"] else None
    qa_map = get_qa_map(essay_id)
    annotated, annot_meta = ("", [])
    if correction:
        annotated, annot_meta = build_annotated(correction, qa_map)
    return render_template("essay.html", e=e, c=correction,
                           annotated=annotated, annot_meta=annot_meta,
                           qa_map=qa_map)


@app.route("/api/correct/<int:essay_id>", methods=["POST"])
def correct(essay_id):
    e = db().execute("SELECT * FROM essays WHERE id=?", (essay_id,)).fetchone()
    if not e:
        return jsonify({"error": "作文不存在"}), 404
    wanted_part = f"\n学生想表达但不会说的中文意思：{e['wanted']}" if e["wanted"] else ""
    messages = [
        {"role": "system", "content": CORRECT_PROMPT},
        {"role": "user", "content": f"作文标题：{e['title']}\n\n{e['content']}{wanted_part}"},
    ]
    result = call_ai(messages)
    data = extract_json(result) if result else None
    if not data:
        # AI 不可用或输出解析失败 → 演示模式兜底
        data = dict(DEMO_CORRECTION)
        data["demo"] = True
        data["demo_reason"] = _AI_ERROR["msg"] or "AI 返回了无法解析的内容（可重试一次）"
    # 自动起书名（自定义标题也起；改名功能始终可覆盖）
    if False:
        pass
    else:
        bt = call_ai([
            {"role": "system", "content":
                "为一篇英语作文起一个简洁优美的中文'书名'（2-8个字，可含英文单词），"
                "概括文章主题或意境。只输出书名本身，不要引号和解释。"},
            {"role": "user", "content": e["content"][:800]},
        ], timeout=60)
        data["book_title"] = (bt or e["content"][:40]).strip().strip('"“”')[:30]
    db().execute(
        "UPDATE essays SET correction=?, corrected=1 WHERE id=?",
        (json.dumps(data, ensure_ascii=False), essay_id),
    )
    db().commit()
    return redirect(url_for("essay", essay_id=essay_id))


@app.route("/api/capture", methods=["POST", "OPTIONS"])
def capture():
    """浏览器书签抓取入口（支持 CORS，可从任何网页调用）。
    mode=new      → 摘录一段待批改的作文
    mode=imported → 摘录 ChatGPT/Gemini 里已有的批改结果（存档，之后可用 AI 整理成错题格式）
    """
    if request.method == "OPTIONS":  # CORS 预检
        resp = app.response_class("", 204)
    else:
        data = request.get_json(silent=True) or request.form
        content = (data.get("content") or "").strip()
        if not content:
            return jsonify({"error": "内容为空"}), 400
        mode = data.get("mode") or "new"
        imported = 1 if mode == "imported" else 0
        label = "（网页导入·已批改）" if imported else "（网页摘录）"
        title = ((data.get("title") or "").strip()[:50] + label) or \
            f"{time.strftime('%Y-%m-%d')}{label}"
        cur = db().execute(
            "INSERT INTO essays(title, content, created_at, imported, raw_import) "
            "VALUES(?,?,?,?,?)",
            (title, content, time.time(), imported,
             content if imported else ""),
        )
        db().commit()
        essay_id = cur.lastrowid
        parsed = False
        if imported:
            parsed = try_auto_parse(essay_id, content)
        resp = jsonify({"ok": True, "id": essay_id, "mode": mode, "parsed": parsed,
                        "url": url_for("essay", essay_id=essay_id, _external=True)})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp


ASK_PROMPT = """你是一位英语写作老师。学生正在用错题集复习，针对某句话的批改提出了追问。
请结合：学生原句、修改后的句子、批改讲解、以及全文语境，用中文回答学生的疑问。
要求：简洁清楚（2-5 句），必要时给 1-2 个例句；如果学生理解有偏差要温和指出。
直接输出回答文字，不要 JSON，不要多余格式。"""

@app.route("/api/ask/<int:essay_id>", methods=["POST"])
def ask(essay_id):
    """针对某句批改的追问（可多处、可多次）"""
    e = db().execute("SELECT * FROM essays WHERE id=?", (essay_id,)).fetchone()
    if not e:
        return jsonify({"error": "作文不存在"}), 404
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    skey = (data.get("skey") or "")[:120]
    if not question:
        return jsonify({"error": "请输入你的疑问"}), 400
    ctx = json.loads(e["correction"]) if e["correction"] else {}
    target = next((x for x in ctx.get("sentences", []) if x.get("original", "")[:120] == skey), {})
    messages = [
        {"role": "system", "content": ASK_PROMPT},
        {"role": "user", "content":
            f"全文：{e['content'][:600]}\n\n"
            f"学生原句：{target.get('original','')}\n"
            f"修改后：{target.get('revised','')}\n"
            f"批改讲解：{target.get('note','')}\n\n"
            f"学生的追问：{question}"},
    ]
    answer = call_ai(messages)
    if not answer:
        answer = "（演示模式：当前 AI 不可用，无法回答。请确认 Ollama / API 已启动后重试。）"
    answer = answer.strip()
    cur = db().execute(
        "INSERT INTO qa(essay_id, skey, q, a, created_at) VALUES(?,?,?,?,?)",
        (essay_id, skey, question, answer, time.time()),
    )
    db().commit()
    return jsonify({"ok": True, "id": cur.lastrowid, "answer": answer,
                    "time": time.strftime("%H:%M")})


def inline_diff_words(original, revised):
    """词级 diff：返回 (kind, text) 片段列表，kind: same/del/ins"""
    ow, rw = original.split(), revised.split()
    sm = difflib.SequenceMatcher(None, [w.lower().strip('.,!?;:"') for w in ow],
                                      [w.lower().strip('.,!?;:"') for w in rw])
    segs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            segs.append(("same", " ".join(ow[i1:i2])))
        elif tag == "delete":
            segs.append(("del", " ".join(ow[i1:i2])))
        elif tag == "insert":
            segs.append(("ins", " ".join(rw[j1:j2])))
        else:  # replace
            if i1 < i2:
                segs.append(("del", " ".join(ow[i1:i2])))
            if j1 < j2:
                segs.append(("ins", " ".join(rw[j1:j2])))
    return segs


def build_annotated(c, qa_map):
    """生成整篇批改 HTML + 每句元数据（供点击详情/追问）"""
    meta, parts = [], []
    for i, sn in enumerate(c.get("sentences", [])):
        orig, rev = sn.get("original", ""), sn.get("revised", "")
        typ = sn.get("type", "error")
        skey = orig[:120]
        if typ == "good" or not rev or rev == orig:
            segs = [("same", orig)]
        else:
            segs = inline_diff_words(orig, rev)
        # 拼接句子 HTML：只有 error（真正用错）才划掉；
        # optimize / complex_kept 原词保留不划线，彩色字给出更好表达
        html_parts = []
        for kind, txt in segs:
            esc = html_mod.escape(txt)
            if kind == "del" and typ == "error":
                html_parts.append(f'<span class="mk del" onclick="showDetail({i})">{esc}</span> ')
            elif kind == "ins":
                html_parts.append(f'<span class="mk ins {typ}" onclick="showDetail({i})">{esc}</span> ')
            elif kind == "del":
                # 非 error 的原词：正常显示，仍可点击看讲解
                html_parts.append(f'<span class="mk plain" onclick="showDetail({i})">{esc}</span> ')
            else:
                html_parts.append(esc + " ")
        parts.append("".join(html_parts).strip())
        meta.append({"i": i, "type": typ, "note": sn.get("note", ""),
                     "original": orig, "revised": rev, "skey": skey,
                     "qa": qa_map.get(skey, [])})
    return " ".join(parts), meta


def get_qa_map(essay_id):
    """把某篇作文的追问按句子分组：{skey: [{q,a,time}, ...]}"""
    rows = db().execute(
        "SELECT skey, q, a, created_at FROM qa WHERE essay_id=? ORDER BY id",
        (essay_id,)).fetchall()
    m = {}
    for r in rows:
        m.setdefault(r["skey"], []).append(
            {"q": r["q"], "a": r["a"], "time": time.strftime("%m-%d %H:%M", time.localtime(r["created_at"]))})
    return m


PARSE_PROMPT = """你是一位英语写作老师的数据整理助手。下面是学生从 ChatGPT/Gemini 等对话中复制来的英语作文批改内容（格式任意，可能混杂对话、解释、表格等）。

请把其中**有价值的批改信息**提取整理成错题集的标准 JSON 格式。规则：
1. sentences：找出所有"原句 → 修改 + 理由"的批改对。type 判定：
   - 明显语法/用词错误 → "error"
   - 语法正确但表达优化 → "optimize"
   - 长句/从句/倒装等复杂结构的修改 → "complex_kept"
   - 表扬的句子 → "good"
   注意区分学生的原句和 AI 的改句。**original 必须逐字复制学生的原句，一个词都不能改、不能合并、不能增删标点；revised 是修改后的完整句子**。
2. note：**必须完整保留原文里给出的每一条理由**，逐条列出（可用 ①②③ 或换行分隔），一条都不许省略、不许概括成一句话。原文没给理由的才留空。
3. vocab：**提取原文中提到的所有词汇/表达/固定短语建议**——只要批改里出现了"XX 应该用 YY"之类的内容，都要变成一条 {original, suggestion, note}，这是短语本的数据来源，宁多勿漏。
4. version_current / version_advanced：如果原文中有整篇改写或两个版本就填入；只有一个版本就 version_current 填它、version_advanced 留空字符串；都没有则都留空。
5. summary：用中文写一句总体评价（概括这段批改的核心结论）。score 给出合理的 1-10 分估计；error_count / optimize_count 按整理结果统计。
6. book_title：给这篇作文起一个简短的书名（4-12 个字，像书架上书的名字，例如「环境污染之我见」「难忘的一次旅行」），根据作文主题起，不要带日期。
7. wanted_phrases：空数组。
8. 拆分要求：sentences 通常有 5~15 条，**每条只对应一句话的一处修改，绝不允许把整段或整篇塞进一条 sentences**。如果批改原文是"原句中带删除线改词"的行内形式（如 I'm work ~~working~~），先还原出学生的完整原句，再把每处修改单独拆成一条。
9. vocab 除了词汇建议外，**还必须把结尾的"最值得带走的表达 / 好句"清单也收进来**：original 填英文表达本身，suggestion 填中文含义，note 填例句和使用说明。
10. 忽略寒暄、追问、与批改无关的内容。找不到任何批改信息时，sentences 给空数组并在 summary 说明。

只输出 JSON：
{"summary": "...", "score": 0, "error_count": 0, "optimize_count": 0, "book_title": "...",
 "sentences": [{"original": "...", "type": "error|optimize|complex_kept|good", "revised": "...", "note": "..."}],
 "vocab": [], "wanted_phrases": [],
 "version_current": "...", "version_advanced": "..."}
"""


@app.route("/api/parse_import/<int:essay_id>", methods=["POST"])
def parse_import(essay_id):
    """把导入的原始批改文本用 AI 整理成错题集标准格式"""
    e = db().execute("SELECT * FROM essays WHERE id=?", (essay_id,)).fetchone()
    if not e:
        return jsonify({"error": "记录不存在"}), 404
    if not e["imported"]:
        return jsonify({"error": "该记录不是导入的批改"}), 400
    messages = [
        {"role": "system", "content": PARSE_PROMPT},
        {"role": "user", "content": e["raw_import"]},
    ]
    result = call_ai(messages)
    data = extract_json(result) if result else None
    if not data:
        data = rule_parse_import(e["raw_import"] or e["content"] or "")
    if not data:
        return jsonify({"error": "AI 整理失败（Ollama/API 不可用或输出异常），原始内容仍保留，可稍后重试"}), 502
    data.setdefault("sentences", [])
    data.setdefault("vocab", [])
    data.setdefault("wanted_phrases", [])
    data["imported"] = True  # 标记：此记录来自外部对话
    db().execute(
        "UPDATE essays SET correction=?, corrected=1 WHERE id=?",
        (json.dumps(data, ensure_ascii=False), essay_id),
    )
    # 自动起书名
    bt = (data.get("book_title") or "").strip()
    if bt:
        db().execute("UPDATE essays SET title=? WHERE id=?",
                     (bt.strip().strip('"“”')[:30], essay_id))
    db().commit()
    return redirect(url_for("essay", essay_id=essay_id))


@app.route("/api/review", methods=["POST"])
def review():
    interval = int(request.form.get("interval") or get_setting("review_interval", "10"))
    set_setting("review_interval", interval)
    essays = db().execute(
        "SELECT id, title, content, correction FROM essays WHERE corrected=1 "
        "ORDER BY id LIMIT ?", (interval,),
    ).fetchall()
    if len(essays) < 2:
        return jsonify({"error": f"已批改作文不足 2 篇，还无法回顾（当前 {len(essays)} 篇）"}), 400

    brief = []
    for e in essays:
        c = json.loads(e["correction"]) if e["correction"] else {}
        sents = [
            {"original": s.get("original"), "type": s.get("type"), "revised": s.get("revised")}
            for s in c.get("sentences", [])
        ]
        brief.append({"id": e["id"], "score": c.get("score"), "sentences": sents,
                      "vocab": c.get("vocab", [])})
    messages = [
        {"role": "system", "content": REVIEW_PROMPT},
        {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
    ]
    result = call_ai(messages)
    data = extract_json(result) if result else None
    if not data:
        data = dict(DEMO_REVIEW)
        data["demo"] = True
    db().execute(
        "INSERT INTO reviews(essay_ids, report, created_at) VALUES(?,?,?)",
        (json.dumps([e["id"] for e in essays]), json.dumps(data, ensure_ascii=False), time.time()),
    )
    db().commit()
    return redirect(url_for("reviews"))


@app.route("/reviews")
def reviews():
    rows = db().execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
    items = [{"id": r["id"], "report": json.loads(r["report"]),
              "created_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(r["created_at"]))}
             for r in rows]
    return render_template("reviews.html", reviews=items,
                           interval=get_setting("review_interval", "10"))


SAY_PROMPT = """你是一位地道英语表达教练。学生用中文说出他想表达的意思，你给他地道的英文说法。

要求：
1. 给出 3 种不同场景/风格的说法（如日常口语、书面写作、更高级的表达），每种附简短中文讲解（关键词、使用注意）。
2. 优先给母语者真正常用的表达，避免中式英语。
3. 如果学生写的是完整句子就按句子处理；是短语或意思就给出自然的完整说法。

只输出 JSON：
{"options": [{"style": "日常口语|书面写作|高级表达", "english": "...", "note": "中文讲解"}],
 "related": ["相关联的其他地道表达（可选，1-2条）"]}
"""


@app.route("/import", methods=["GET", "POST"])
def import_page():
    """📥 导入页面：粘贴 GPT/Gemini 已批改内容 → AI 整理入库；或粘贴新作文 → 待批改"""
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        mode = request.form.get("mode", "imported")
        if not content:
            return render_template("import.html", error="请先粘贴内容", mode=mode,
                                   bookmarklet=make_bookmarklet("new"), bookmarklet_import=make_bookmarklet("imported"), bookmarklet_paste=make_bookmarklet_paste())
        title = request.form.get("title", "").strip()[:60] or \
            f"{time.strftime('%Y-%m-%d')} {'网页导入·已批改' if mode=='imported' else '新作文'}"
        cur = db().execute(
            "INSERT INTO essays(title, content, created_at, imported, raw_import) "
            "VALUES(?,?,?,?,?)",
            (title, content, time.time(), 1 if mode == "imported" else 0,
             content if mode == "imported" else ""),
        )
        db().commit()
        essay_id = cur.lastrowid
        if mode == "imported":
            # 直接调 AI 整理
            if try_auto_parse(essay_id, content):
                return redirect(url_for("essay", essay_id=essay_id))
            # AI 整理失败 → 原始存档，去详情页手动点整理
            return redirect(url_for("essay", essay_id=essay_id))
        return redirect(url_for("essay", essay_id=essay_id))
    return render_template("import.html", error=None, mode="imported",
                           bookmarklet=make_bookmarklet("new"), bookmarklet_import=make_bookmarklet("imported"), bookmarklet_paste=make_bookmarklet_paste())

DEMO_SAY = {
    "options": [
        {"style": "日常口语", "english": "I was so absorbed in the book that I lost track of time.",
         "note": "be absorbed in 表示沉浸其中；lose track of time 表示忘了时间，母语者日常很常用。"},
        {"style": "书面写作", "english": "The book held my attention so completely that hours slipped by unnoticed.",
         "note": "hold one's attention 表示牢牢吸引注意力；slip by unnoticed 形容时间不知不觉流逝。"},
        {"style": "高级表达", "english": "I was utterly engrossed in the book, oblivious to the passage of time.",
         "note": "engrossed 比 absorbed 更高级；oblivious to the passage of time 是很书面的说法。"},
    ],
    "related": ["一口气读完：read it in one sitting", "爱不释手：I couldn't put it down"],
}


@app.route("/say", methods=["GET", "POST"])
def say():
    """我想说但不会说：输入中文 → AI 给地道英文，并自动存入表达积累本"""
    if request.method == "POST":
        chinese = request.form.get("chinese", "").strip()
        if not chinese:
            return jsonify({"error": "请输入你想表达的中文意思"}), 400
        messages = [
            {"role": "system", "content": SAY_PROMPT},
            {"role": "user", "content": chinese},
        ]
        result = call_ai(messages)
        data = extract_json(result) if result else None
        if not data or not data.get("options"):
            data = dict(DEMO_SAY)
            data["demo"] = True
        # 把最推荐的写法存入积累本
        first = data["options"][0]
        db().execute(
            "INSERT INTO phrases(chinese, english, note, created_at) VALUES(?,?,?,?)",
            (chinese, first["english"], first["note"], time.time()),
        )
        db().commit()
        return render_template("say.html", query=chinese, result=data,
                               phrases=get_phrases())
    return render_template("say.html", query="", result=None, phrases=get_phrases())


def get_phrases():
    rows = db().execute(
        "SELECT chinese, english, note, created_at FROM phrases ORDER BY id DESC LIMIT 100"
    ).fetchall()
    return rows


@app.route("/phrases/delete", methods=["POST"])
def delete_phrase():
    english = request.form.get("english", "")
    db().execute("DELETE FROM phrases WHERE english=?", (english,))
    db().commit()
    return redirect(url_for("say"))


@app.route("/phrases")
def phrase_book():
    """短语本：自动收集所有已批改文章里的词汇与固定短语"""
    rows = db().execute(
        "SELECT id, title, correction FROM essays WHERE corrected=1 ORDER BY id DESC"
    ).fetchall()
    items, seen = [], set()
    for e in rows:
        if not e["correction"]:
            continue
        try:
            c = json.loads(e["correction"])
        except Exception:  # noqa: BLE001
            continue
        for v in c.get("vocab", []):
            orig = (v.get("original") or "").strip()
            sug = (v.get("suggestion") or "").strip()
            if not orig or not sug:
                continue
            key = (orig.lower(), sug.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append({"essay_id": e["id"], "essay_title": e["title"],
                          "original": orig, "suggestion": sug,
                          "note": (v.get("note") or "").strip()})
    # 兜底：批次里 vocab 为空的文章，从逐句修改里提炼词汇对比
    for e in rows:
        if not e["correction"]:
            continue
        try:
            c = json.loads(e["correction"])
        except Exception:  # noqa: BLE001
            continue
        if c.get("vocab"):
            continue
        # 从讲解里补充短语（take up 是短语动词 / 句型：xxx）
        for v in extract_phrases_from_notes(c):
            key = (v["original"].lower(), v["suggestion"].lower()[:60])
            if key in seen:
                continue
            seen.add(key)
            items.append({"essay_id": e["id"], "essay_title": e["title"], **v})
        for s in c.get("sentences", []):
            o = (s.get("original") or "").strip()
            r = (s.get("revised") or "").strip()
            note = (s.get("note") or "").strip()
            if not o or not r or o.lower() == r.lower():
                continue
            # 只在句子差别不大时（词级改动）作为"表达对比"收录
            if abs(len(o) - len(r)) > max(25, len(o) * 0.4):
                continue
            key = (o.lower()[:120], r.lower()[:120])
            if key in seen:
                continue
            seen.add(key)
            items.append({"essay_id": e["id"], "essay_title": e["title"],
                          "original": o, "suggestion": r, "note": note})
    return render_template("phrases.html", items=items)



@app.route("/api/update", methods=["POST"])
def api_update():
    """应用内一键更新：自己从 GitHub 下载最新代码覆盖（绝不碰 data 数据）"""
    try:
        import io as io_mod
        import zipfile
        base = os.path.dirname(os.path.abspath(__file__))
        headers = {}
        token_file = os.path.join(base, "gh-token.txt")
        if os.path.exists(token_file):
            headers["Authorization"] = "Bearer " + open(token_file).read().strip()
        # 先用 raw 上的 VERSION 探一下远端版本（raw 没有 zipball 那种缓存延迟），
        # 顺手把"已经是最新版"这种情况说清楚，避免重复覆盖、也避免用户以为没生效。
        remote_ver = ""
        try:
            import base64 as b64
            rv = requests.get(
                "https://api.github.com/repos/bella10281220/essay-coach/contents/VERSION",
                headers=headers, timeout=15)
            if rv.status_code == 200:
                remote_ver = b64.b64decode(rv.json().get("content", "")).decode(
                    "utf-8", "ignore").strip()[:20]
                if remote_ver and remote_ver == VERSION:
                    return jsonify({"ok": True, "updated": 0, "uptodate": True,
                                    "message": f"✅ 已经是最新版 v{VERSION}，不需要更新。"})
        except Exception:  # noqa: BLE001
            pass

        r = None
        for attempt in range(3):
            r = requests.get(
                "https://api.github.com/repos/bella10281220/essay-coach/zipball/main",
                headers=headers, timeout=90)
            if r.status_code == 200:
                break
            time.sleep(2)
        if r.status_code == 404:
            return jsonify({"ok": False, "error":
                "GitHub 返回 404：仓库访问被拒。请确认项目文件夹里有 gh-token.txt"
                "（内容为你的 GitHub token），或者把仓库改成 Public。"}), 502
        if r.status_code == 401 or r.status_code == 403:
            return jsonify({"ok": False, "error":
                "GitHub 返回 %d：token 失效或请求太频繁。请换一个新 token 放进 gh-token.txt。"
                % r.status_code}), 502
        if r.status_code != 200:
            return jsonify({"ok": False, "error":
                "GitHub 返回 %d（网络或仓库状态异常），请稍后重试。" % r.status_code}), 502
        r.raise_for_status()
        zf = zipfile.ZipFile(io_mod.BytesIO(r.content))
        root = zf.namelist()[0].split("/")[0]
        # 备份将被覆盖的旧文件，万一新版有问题可以手动换回来
        try:
            bak_dir = os.path.join(base, "data", "backup_before_update")
            os.makedirs(bak_dir, exist_ok=True)
            for keep in ("app.py",):
                src_p = os.path.join(base, keep)
                if os.path.exists(src_p):
                    import shutil
                    shutil.copy2(src_p, os.path.join(bak_dir, keep))
        except Exception:  # noqa: BLE001
            pass
        skip_words = ("data/", "gh-token.txt", "更新日志.txt", "启动日志.txt", "start-log.txt")
        updated = 0
        for name in zf.namelist():
            rel = name[len(root) + 1:]
            if not rel or rel.endswith("/"):
                continue
            if any(w in rel for w in skip_words) or rel == "essays.db":
                continue
            dest = os.path.join(base, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as out:
                out.write(src.read())
            updated += 1
        # Windows 下自动重启：拉起重启脚本（它会清掉旧进程并用无窗口方式重启服务）
        if os.name == "nt":
            try:
                import subprocess
                subprocess.Popen(["wscript.exe", os.path.join(base, "重启更新.vbs")],
                                 cwd=base, close_fds=True)
                threading.Timer(1.5, lambda: os._exit(0)).start()
                auto = "服务正在自动重启，几秒后页面会自动刷新为新版本。"
            except Exception:  # noqa: BLE001
                auto = "请手动重启拾贝集（关掉窗口再双击桌面图标）。"
        else:
            auto = "请手动重启拾贝集。"
        return jsonify({"ok": True, "updated": updated, "remote": remote_ver,
                        "message": f"✅ 已更新 {updated} 个文件！{auto}"})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"更新失败：{e}"}), 500


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "GET":
        return render_template(
            "settings.html",
            provider=get_setting("provider", "ollama"),
            model=get_setting("model", ""),
            api_base=get_setting("api_base", ""),
            api_key=get_setting("api_key", ""),
            api_model=get_setting("api_model", ""),
            interval=get_setting("review_interval", "10"),
            presets=API_PRESETS,
        )
    for key in ("review_interval", "model", "provider", "api_base", "api_key", "api_model"):
        if key in request.form:
            set_setting(key, request.form[key].strip())
    return redirect(url_for("settings", saved=1))


def _u(s):
    """把中文等非 ASCII 字符转成 \\uXXXX，保证书签在任何浏览器编码下都不乱码"""
    out = []
    for ch in s:
        if ord(ch) < 128:
            out.append(ch)
        else:
            out.append("\\u%04x" % ord(ch))
    return "".join(out)


def make_bookmarklet_paste():
    """最简单可靠的版本：一键打开导入页，把内容粘贴进去（绝不抓错）"""
    return ("javascript:(function(){window.open("
            "'http://127.0.0.1:5000/import','_blank');})()")


def make_bookmarklet(mode="new"):
    """生成抓取书签的 JS 代码：带全程浮动提示条，直接抓对话主区域（不依赖选中）"""
    tpl = r"""
(function(){
function toast(html,color,sticky){var d=document.createElement('div');
d.style.cssText='position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:2147483647;max-width:86vw;padding:11px 20px;border-radius:24px;font-size:14px;font-family:sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.28);color:#fff;background:'+(color||'#555')+';line-height:1.6';
d.innerHTML=html;document.body.appendChild(d);
if(!sticky){setTimeout(function(){d.remove();},9000);}
return d;}
var cands=[];
try{cands=Array.prototype.slice.call(document.querySelectorAll('main,article,[data-testid^="conversation"],div[class*="conversation"],div[class*="chat"]'));}catch(e){}
cands.push(document.body);
var best='',area='';
for(var i=0;i<cands.length;i++){
 try{
  var t=(cands[i].innerText||'').replace(/\n{3,}/g,'\n\n').trim();
  if(t.length>best.length){best=t;area=(cands[i].tagName||'').toLowerCase();}
 }catch(e){}
}
best=(best||'').slice(0,12000);
if(best.length<150){toast('__ZH_NOTEXT__','#b98a3a',true);return;}
var tip=toast('__ZH_WAIT__'+best.length+' __ZH_CHARS__&hellip;','#555',true);
fetch('http://127.0.0.1:5000/api/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:best,title:document.title,mode:'__MODE__'})})
.then(function(r){return r.json()})
.then(function(d){
if(!d.ok){tip.style.background='#d97b7b';tip.innerHTML='__ZH_FAIL__'+(d.error||'?')+'__ZH_CLOSE__';tip.onclick=function(){tip.remove()};return;}
var link=' <a style="color:#ffe9a8;text-decoration:underline" href="'+d.url+'" target="_blank">__ZH_GO__</a>';
tip.style.background='#46a07c';
if(d.mode==='imported'){tip.innerHTML=d.parsed?'__ZH_OK1__'+link:'__ZH_OK2__'+link;}
else{tip.innerHTML='__ZH_OK3__'+link;}})
.catch(function(){tip.style.background='#d97b7b';tip.innerHTML='__ZH_CONN__';});
})()
"""
    zh = {
        "__ZH_NOTEXT__": _u("这个页面几乎没有文字内容，请在有对话的页面使用书签"),
        "__ZH_WAIT__": _u("⏳ 正在收藏本页内容（"),
        "__ZH_CHARS__": _u("字）"),
        "__ZH_FAIL__": _u("❌ 收藏失败："),
        "__ZH_CLOSE__": _u("（点我关闭）"),
        "__ZH_GO__": _u("去看看 →"),
        "__ZH_OK1__": _u("✅ 已收藏并自动整理成书！"),
        "__ZH_OK2__": _u("⚠️ 已存下原文，但 AI 整理没成功，可去错题集手动点整理"),
        "__ZH_OK3__": _u("✅ 已收藏！"),
        "__ZH_CONN__": _u('❌ 连不上错题集！请先双击桌面的「拾贝集」图标启动（<a style="color:#ffe9a8;text-decoration:underline" href="http://127.0.0.1:5000" target="_blank">试试能否打开</a>）'),
        "__MODE__": mode,
    }
    for k, v in zh.items():
        tpl = tpl.replace(k, v)
    js = " ".join(tpl.split())  # 压掉换行，保证是一行 URL
    return "javascript:" + js.replace("'", "%27").replace('"', "%22")


def rule_parse_import(raw):
    """AI 不可用时的兜底：按 ①②③ 编号 / '原句 → 修改' 结构做规则化拆分"""
    text = raw or ""
    # 去掉开头的对话寒暄与原文引用块（保留"①"之后的内容）
    m = re.search(r"[①❶1][\s\.、]", text)
    core = text[m.start():] if m else text

    # 1) 提取 "最值得带走/值得记住 的 N 个表达"
    vocab = []
    for vm in re.finditer(r"(\d+)[.、]\s*([A-Za-z][A-Za-z' \-]{2,60})\s*\n+\s*([^\n]+)", core):
        eng, zh = vm.group(2).strip(), vm.group(3).strip()
        if re.search(r"[\u4e00-\u9fff]", zh) and len(eng) < 60:
            vocab.append({"original": eng, "suggestion": zh[:60], "note": ""})

    # 2) 按 ①②③ 切段
    parts = re.split(r"(?=[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])", core)
    sentences = []
    for p in parts:
        p = p.strip()
        if not p or p[0] not in "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮":
            continue
        # 去掉编号与"X 类｜..."标题行
        body = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\s*", "", p)
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        if not lines:
            continue
        head = lines[0]
        typ = "error"
        if "优化" in head or "自然" in head:
            typ = "optimize"
        elif "保留" in head:
            typ = "complex_kept"
        # 讲解 = 剩余的说明行
        note = "\n".join(lines[1:])
        # 行内改词：形如 "原句 <新句>" 相邻出现，取最接近的一对
        engs = re.findall(r"[A-Za-z][A-Za-z',\.\!\?\-\s]{6,200}", body)
        engs = [" ".join(e.split()) for e in engs if len(e.split()) >= 3]
        engs = [e.strip(" ,.") for e in engs]
        orig, rev = "", ""
        if len(engs) >= 2:
            # 相邻两段里，选"前短后长/前错后对"最像改写的一对
            best, best_score = None, -1
            for a, b in zip(engs, engs[1:]):
                if a.lower() == b.lower():
                    continue
                # 相似度越高越像"同一句的改写"
                import difflib as _dl
                sim = _dl.SequenceMatcher(None, a.lower(), b.lower()).ratio()
                score = sim * 100 + len(b.split())
                if score > best_score:
                    best_score, best = score, (a, b)
            if best:
                orig, rev = best
        elif len(engs) == 1:
            orig = engs[0]
        if not orig:
            continue
        # 改写句与原文几乎一样 → 视为「无需修改」，不重复展示
        if rev and rev.lower() == orig.lower():
            rev = ""
        sentences.append({"original": orig[:300], "type": typ,
                          "revised": rev[:300], "note": note[:600]})

    # 3) 参考版本（"修改后的参考版本" 之后、第一个中文小标题之前）
    ver = ""
    vm = re.search(r"(?:修改后的参考版本|参考版本)[^\n]*\n(.*?)(?:\n[^\x00-\x7F]|\Z)", core, re.S)
    if vm:
        ver = vm.group(1).strip()[:4000]

    if not sentences:
        return None

    # 4) 标题
    tm = re.search(r"(?:第[一二三四五六七八九十]+篇)[｜|]\s*(.+)", core)
    title = tm.group(1).strip()[:30] if tm else ""

    return {"summary": "（AI 未连接，以下为规则整理，建议连上 AI 后点「重新整理」获得更完整的讲解）",
            "score": 0,
            "error_count": len([s for s in sentences if s["type"] == "error"]),
            "optimize_count": len([s for s in sentences if s["type"] == "optimize"]),
            "book_title": title,
            "sentences": sentences,
            "vocab": vocab,
            "wanted_phrases": [],
            "version_current": ver,
            "version_advanced": ""}


def try_auto_parse(essay_id, content):
    """把已批改的原始内容交给 AI 整理成错题格式；成功返回 True"""
    messages = [
        {"role": "system", "content": PARSE_PROMPT},
        {"role": "user", "content": content},
    ]
    result = call_ai(messages)
    data = extract_json(result) if result else None
    if not data:
        # AI 不可用 → 规则化兜底，至少保证能拆条、能进短语本
        data = rule_parse_import(content)
    if not data:
        return False
    for k in ("sentences", "vocab", "wanted_phrases"):
        data.setdefault(k, [])
    data["imported"] = True
    db().execute(
        "UPDATE essays SET correction=?, corrected=1 WHERE id=?",
        (json.dumps(data, ensure_ascii=False), essay_id),
    )
    # 自动起书名（和普通批改一致）
    bt = (data.get("book_title") or "").strip()
    if bt:
        db().execute("UPDATE essays SET title=? WHERE id=?",
                     (bt.strip().strip('"“”')[:30], essay_id))
    db().commit()
    return True


@app.route("/delete/<int:essay_id>", methods=["POST"])
def delete(essay_id):
    db().execute("DELETE FROM essays WHERE id=?", (essay_id,))
    db().commit()
    # 删完回到原页面（书架删书回书架、写作页删作文回写作页）
    ref = request.referrer or ""
    if "/shelf" in ref:
        return redirect(url_for("shelf"))
    if "/essay/" in ref:
        return redirect(url_for("write_page"))
    return redirect(ref or url_for("index"))



if __name__ == "__main__":
    # Windows 控制台默认 GBK，print emoji 会抛 UnicodeEncodeError 直接崩掉服务。
    # 这里强制把标准输出改成 UTF-8（失败就退化成忽略错误），确保启动绝不因日志而崩。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    host = os.environ.get("HOST", "0.0.0.0")   # 0.0.0.0 = 允许手机通过局域网访问

    # 端口固定为 5000（启动器、书签脚本、桌面图标都写死了这个地址）。
    # 若 5000 被旧进程占用，先尝试清理，实在清不掉就换一个端口并把实际端口写进
    # data/port.txt，启动器读到后会打开正确的地址。
    want = int(os.environ.get("PORT", "5000"))
    port = want
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _ps:
            _ps.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _ps.bind(("127.0.0.1", want))
    except OSError:
        port = pick_port(want + 1)
        log(f"[port] {want} is busy, fallback to {port}")
    try:
        os.makedirs("data", exist_ok=True)
        with open(os.path.join("data", "port.txt"), "w", encoding="utf-8") as _pf:
            _pf.write(str(port))
    except OSError:
        pass

    def safe_print(msg):
        try:
            print(msg, flush=True)
        except Exception:  # noqa: BLE001
            try:
                print(msg.encode("ascii", "ignore").decode("ascii"), flush=True)
            except Exception:  # noqa: BLE001
                pass

    safe_print(f"ShiBeiJi started -> http://127.0.0.1:{port}")
    if host == "0.0.0.0":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
            safe_print(f"Phone (same WiFi) -> http://{lan_ip}:{port}")
        except OSError:
            pass
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)
