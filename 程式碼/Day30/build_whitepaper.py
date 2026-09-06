"""
Day 30 範例：白皮書合成器——把三十天的成果，合成一份可交付的《白皮書》。

這是整個系列的收尾動作。程式做四件事，全部**從專案的實際狀態讀出來**，
而不是把內容再抄一遍到這支程式裡：

    1. 掃描 Day01–Day30 的標題，依四階段整理成白皮書目錄。
    2. 直接嵌入 Day 29 產出的《AI 系統資安自評表》（程式碼/Day29/自評表.md）。
       ——不重打一份，因為重打的那份一定會跟本尊走鐘。
    3. 清點可再利用資產：實際去數程式碼與配圖有幾支、幾張。
    4. 附上一份「這份文件何時該回頭修」的追蹤清單。

刻意的設計：白皮書裡沒有任何一個數字是手寫的。改了文章標題、改了自評狀態、
多寫一支程式，重跑一次，白皮書就跟著更新——這才叫「活的文件」。

用法：
    python build_whitepaper.py     # 產生 白皮書.md 於本目錄
"""

import glob
import os
import re

# 專案根目錄（本檔在 程式碼/Day30/，往上三層即根）
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))

# 四階段的分界（起日、迄日、名稱）
STAGES = [
    (1, 5, "第一階段｜威脅與風險"),
    (6, 14, "第二階段｜制度與標準"),
    (15, 20, "第三階段｜機構與資源"),
    (21, 30, "第四階段｜技術落地"),
]

# 追蹤清單：這份白皮書會因為什麼而過期，該去哪裡看
WATCHLIST = [
    ("各部會 AI 作用法與指引", "國家科學及技術委員會、各目的事業主管機關",
     "新指引發布時", "檢核表的「制度來源」欄"),
    ("資安法規與採購要求", "數位發展部資通安全署、行政院公共工程委員會",
     "法規修正時", "Day 20 的責任等級與通報義務"),
    ("AIEC 評測項目", "數位產業署 AI 產品與系統評測中心",
     "評測項目調整時", "檢核表的十列骨架"),
    ("ISO/IEC 42001 與 CNS 42001", "ISO、經濟部標準檢驗局",
     "標準改版時", "檢核表的「42001 落點」欄"),
    ("新型攻擊手法", "OWASP LLM Top 10、資安社群",
     "出現新手法時", "Day 26 的紅隊案例庫"),
]


def read_title(day: int) -> str:
    """從 DayNN.md 第一行 '# Day NN：標題' 抽出標題。"""
    path = os.path.join(ROOT, f"Day{day:02d}.md")
    if not os.path.exists(path):
        return "（未完成）"
    first = open(path, encoding="utf-8").readline().strip()
    m = re.match(r"#\s*Day\s*\d+[:：]\s*(.+)", first)
    return m.group(1) if m else "（無標題）"


def read_self_assessment() -> str:
    """讀入 Day 29 產出的自評表；沒有就提示先去跑那支程式。"""
    path = os.path.join(ROOT, "程式碼", "Day29", "自評表.md")
    if not os.path.exists(path):
        return "> ⚠️ 尚未產出自評表，請先執行 `程式碼/Day29/compliance_checklist.py`。"
    body = open(path, encoding="utf-8").read()
    # 去掉自評表自己的大標，只留說明與表格，避免白皮書出現兩層標題
    kept = [ln for ln in body.splitlines() if not ln.startswith("# ")]
    return "\n".join(kept).strip()


def count_assets() -> dict:
    """實際清點可再利用的資產數量，而不是宣稱。"""
    return {
        "程式": len(glob.glob(os.path.join(ROOT, "程式碼", "Day*", "*.py"))),
        "配圖": len(glob.glob(os.path.join(ROOT, "圖檔", "Day*", "*.png"))),
        "知識庫": len(glob.glob(os.path.join(ROOT, "程式碼", "Day*", "knowledge*", "*.md"))),
    }


def build() -> str:
    """合成白皮書 Markdown，回傳字串。"""
    lines = [
        "# 《AI 治理與資安合規實戰指南》白皮書",
        "",
        "> 由 iThome 鐵人賽 30 天系列合成。把上層法規標準，一路翻譯到可執行的技術控制與程式碼。",
        "> 本文件由 `程式碼/Day30/build_whitepaper.py` 自動產生，內容隨專案實際狀態更新。",
        "",
        "## 一、目錄：從法條到程式碼的四階段",
        "",
    ]
    for start, end, name in STAGES:
        lines.append(f"### {name}（Day {start}–{end}）")
        for day in range(start, end + 1):
            lines.append(f"- Day {day:02d}：{read_title(day)}")
        lines.append("")

    lines += ["## 二、核心交付物：AI 系統資安自評表", "",
              "以下直接引用 Day 29 查核工具的產出，每一格佐證都經過存在性驗證。", "",
              read_self_assessment(), ""]

    assets = count_assets()
    lines += ["## 三、可再利用資產", "",
              f"- 可執行程式 {assets['程式']} 支：RAG 五層防禦、紅隊框架、"
              f"稽核日誌、供應鏈驗證、合規查核工具（`程式碼/DayNN/`）",
              f"- 概念與流程配圖 {assets['配圖']} 張（`圖檔/DayNN/`）",
              f"- 教學用知識庫文件 {assets['知識庫']} 份（`程式碼/DayNN/knowledge*/`）",
              "- 適用場景：醫院 AI 客服案、政府 AI 標案的自評、送測與稽核。", ""]

    lines += ["## 四、追蹤清單：這份文件何時該回頭修", "",
              "| 追什麼 | 去哪裡看 | 什麼時候回頭 | 要改白皮書哪裡 |",
              "| --- | --- | --- | --- |"]
    for what, where, when, fix in WATCHLIST:
        lines.append(f"| {what} | {where} | {when} | {fix} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    whitepaper = build()
    out = os.path.join(HERE, "白皮書.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(whitepaper)

    done = sum(1 for d in range(1, 31) if read_title(d) not in ("（未完成）", "（無標題）"))
    assets = count_assets()
    print(f"✅ 已合成白皮書 → {os.path.basename(out)}（{len(whitepaper)} 字元）")
    print(f"   收錄文章：{done}/30 篇")
    embedded = os.path.exists(os.path.join(ROOT, "程式碼", "Day29", "自評表.md"))
    print(f"   嵌入 Day 29 自評表：{'是' if embedded else '否（請先跑 Day 29）'}")
    print(f"   清點資產：程式 {assets['程式']} 支、配圖 {assets['配圖']} 張、"
          f"知識庫 {assets['知識庫']} 份")
    print(f"   追蹤清單：{len(WATCHLIST)} 項")
    print("\n── 白皮書目錄預覽 ──")
    for start, end, name in STAGES:
        print(f"  {name}（Day {start}–{end}）")
