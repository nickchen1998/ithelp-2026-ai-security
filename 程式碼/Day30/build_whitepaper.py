"""
Day 30 範例：白皮書合成器——把三十天的文章，合成一份《白皮書》骨架。

這是整個系列的收尾動作：把散落在 30 篇文章、程式與紀錄裡的成果，收攏成一份
可交付、可再利用的《AI 治理與資安合規實戰指南》白皮書。程式做三件事：
    1. 掃描 Day01–Day30 的標題，依四階段整理成白皮書目錄。
    2. 嵌入 Day 29 的核心交付物——AI 專案資安合規檢核表。
    3. 輸出一份白皮書骨架 Markdown（白皮書.md），作為醫院案／標案可再利用的資產。

用法：
    python build_whitepaper.py     # 產生 白皮書.md 於本目錄
"""

import glob
import os
import re

# 專案根目錄（本檔在 程式碼/Day30/，往上兩層即根）
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 四階段的分界（起日、迄日、名稱）
STAGES = [
    (1, 5, "第一階段｜威脅與風險"),
    (6, 14, "第二階段｜制度與標準"),
    (15, 20, "第三階段｜機構與資源"),
    (21, 30, "第四階段｜技術落地"),
]

# 核心檢核表骨架（AIEC 十大評測項；完整版見 程式碼/Day29/compliance_checklist.py）
CHECKLIST = [
    ("資安", "輸入防禦、存取控制、供應鏈", "紅隊 ASR=0%、AI-BOM 驗證"),
    ("安全性", "輸出內容約束與免責", "涉病情提醒諮詢專業"),
    ("彈性", "紅隊測試流程", "ASR 83%→0% 報告"),
    ("隱私", "去識別化、出口遮蔽、存取控制", "查無個資、跨租戶被擋"),
    ("準確性", "grounding 幻覺防護", "查無依據不硬答"),
    ("可靠性", "紅隊、供應鏈釘選", "ASR 指標、digest 驗證"),
    ("透明性", "來源標註與免責", "回覆附依據與 AI 聲明"),
    ("可解釋性", "來源可追溯設計", "答案可回溯至來源"),
    ("當責性", "稽核日誌雜湊鏈", "竄改偵測、斷鏈報警"),
    ("公平性", "資料源頭治理、紅隊探測", "資料最小化；偏誤測試待補"),
]


def read_title(day: int) -> str:
    """從 DayNN.md 第一行 '# Day NN：標題' 抽出標題。"""
    path = os.path.join(ROOT, f"Day{day:02d}.md")
    if not os.path.exists(path):
        return "（未完成）"
    first = open(path, encoding="utf-8").readline().strip()
    m = re.match(r"#\s*Day\s*\d+[:：]\s*(.+)", first)
    return m.group(1) if m else "（無標題）"


def build() -> str:
    """合成白皮書骨架 Markdown，回傳字串。"""
    lines = [
        "# 《AI 治理與資安合規實戰指南》白皮書",
        "",
        "> 由 iThome 鐵人賽 30 天系列合成。把上層法規標準，一路翻譯到可執行的技術控制與程式碼。",
        "",
        "## 目錄：從法條到程式碼的四階段",
        "",
    ]
    for start, end, name in STAGES:
        lines.append(f"### {name}（Day {start}–{end}）")
        for day in range(start, end + 1):
            lines.append(f"- Day {day:02d}：{read_title(day)}")
        lines.append("")

    lines += ["## 核心交付物：AI 專案資安合規檢核表", "",
              "| AIEC 評測項 | 技術控制 | 怎麼驗證 |", "| --- | --- | --- |"]
    for aiec, controls, verify in CHECKLIST:
        lines.append(f"| {aiec} | {controls} | {verify} |")
    lines += ["",
              "## 附錄：可再利用資產",
              "- 程式碼：`程式碼/DayNN/`（RAG 五層防禦、紅隊框架、稽核日誌、供應鏈驗證、檢核表工具）",
              "- 配圖：`圖檔/DayNN/`（每篇 4–6 張概念與流程圖）",
              "- 適用場景：醫院 AI 客服案、政府 AI 標案的自評與稽核。",
              ""]
    return "\n".join(lines)


if __name__ == "__main__":
    whitepaper = build()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "白皮書.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(whitepaper)

    # 印出摘要
    done = sum(1 for d in range(1, 31) if read_title(d) not in ("（未完成）", "（無標題）"))
    print(f"✅ 已合成白皮書骨架 → {os.path.basename(out)}")
    print(f"   收錄文章：{done}/30 篇；四階段、AIEC 十大檢核項全數納入。")
    print("\n── 白皮書目錄預覽 ──")
    for start, end, name in STAGES:
        print(f"  {name}（Day {start}–{end}）")
