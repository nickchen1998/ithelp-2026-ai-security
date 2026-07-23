"""
Day 29 範例：AI 專案資安合規檢核表——機器可讀的檢核表 + 自評工具。

這支程式把本系列的核心交付物「檢核表」寫成結構化資料：以 AIEC 十大評測項目
為骨架，每一項都對應到「基本法原則 → ISO/IEC 42001 落點 → 技術控制（哪一天）
→ 怎麼驗證」。接著提供一個自評工具，拿一個專案的落實狀態去對照檢核表，
算出「合規準備度」並列出還沒補齊的缺口（gap）。

檢核表是「白皮書核心」，這支程式讓它從一張靜態表格，變成可執行的自評與稽核工具。
"""

# ── 檢核表本體：以 AIEC 十大評測項目為骨架（機器可讀）──────────────────
# 每一項：AIEC 評測項、對應基本法原則、ISO/IEC 42001 落點、技術控制（本系列日次）、怎麼驗證
CHECKLIST = [
    {"id": "C1", "aiec": "資安", "principle": "資安與安全",
     "iso": "附錄 A 安全相關控制", "controls": "輸入注入防禦(D23)、存取控制(D25)、供應鏈(D28)",
     "verify": "紅隊 ASR=0%(D26)、AI-BOM 完整性驗證(D28)"},
    {"id": "C2", "aiec": "安全性", "principle": "資安與安全",
     "iso": "附錄 A 安全相關控制", "controls": "輸出內容約束與免責提示(D24)、輸入層有害請求阻擋(D23)",
     "verify": "回覆附「不能取代專業醫療判斷」免責、涉病情提醒諮詢專業(D24)"},
    {"id": "C3", "aiec": "彈性", "principle": "資安與安全",
     "iso": "附錄 A 驗證與測試相關控制", "controls": "紅隊測試流程(D26)",
     "verify": "ASR 83%→0% 的紅隊報告(D26)"},
    {"id": "C4", "aiec": "隱私", "principle": "隱私保護與資料治理",
     "iso": "附錄 A 資料相關控制", "controls": "去識別化與最小化(D22)、出口遮蔽(D24)、存取控制(D25)",
     "verify": "治理後知識庫查無個資、跨租戶被擋(D22/24/25)"},
    {"id": "C5", "aiec": "準確性", "principle": "（品質面）",
     "iso": "附錄 A 品質相關控制", "controls": "grounding 幻覺防護(D24)",
     "verify": "查無足夠依據時不硬答(D24)"},
    {"id": "C6", "aiec": "可靠性", "principle": "（品質面）",
     "iso": "附錄 A 驗證與供應者控制", "controls": "紅隊(D26)、供應鏈釘選(D28)",
     "verify": "ASR 指標、digest 驗證通過"},
    {"id": "C7", "aiec": "透明性", "principle": "透明與可解釋",
     "iso": "附錄 A 資訊揭露相關控制", "controls": "來源標註與免責提示(D24)",
     "verify": "回覆附上依據來源與 AI 生成聲明(D24)"},
    {"id": "C8", "aiec": "可解釋性", "principle": "透明與可解釋",
     "iso": "附錄 A 資訊揭露相關控制", "controls": "來源可追溯設計(D24)",
     "verify": "答案可回溯至 RAG 檢索來源(D24)"},
    {"id": "C9", "aiec": "當責性", "principle": "問責",
     "iso": "附錄 A 紀錄與事件管理相關控制", "controls": "稽核日誌雜湊鏈(D27)",
     "verify": "竄改偵測（斷鏈報警）(D27)"},
    {"id": "C10", "aiec": "公平性", "principle": "公平與不歧視",
     "iso": "附錄 A 資料與影響評估相關控制", "controls": "資料源頭治理(D22)、紅隊探測(D26)",
     "verify": "資料最小化、去偏；偏誤測試（待補）"},
]

# ── 某個 AI 專案的自評狀態：done=已落實、partial=部分、todo=尚未 ─────────
# 這裡填入「本系列 RAG 醫院客服 demo」的實際落實狀態作為示範。
ASSESSMENT = {
    "C1": "done", "C2": "done", "C3": "done", "C4": "done", "C5": "done",
    "C6": "done", "C7": "done", "C8": "done", "C9": "done",
    "C10": "partial",   # 資料治理有做，但尚未做正式的偏誤（bias）量測
}

_MARK = {"done": "🟢 已落實", "partial": "🟡 部分", "todo": "🔴 未落實"}
_SCORE = {"done": 1.0, "partial": 0.5, "todo": 0.0}


def render_checklist():
    """印出完整檢核表（白皮書核心交付物）。"""
    print("=" * 100)
    print("《AI 專案資安合規檢核表》——以 AIEC 十大評測項目為骨架")
    print("=" * 100)
    for c in CHECKLIST:
        print(f"[{c['id']:>3}] AIEC：{c['aiec']}  ｜對應原則：{c['principle']}")
        print(f"      ISO/IEC 42001：{c['iso']}")
        print(f"      技術控制：{c['controls']}")
        print(f"      怎麼驗證：{c['verify']}")


def assess(assessment):
    """拿專案的落實狀態對照檢核表，回傳 (準備度百分比, 缺口清單)。"""
    total = len(CHECKLIST)
    score = sum(_SCORE[assessment.get(c["id"], "todo")] for c in CHECKLIST)
    gaps = [c for c in CHECKLIST if assessment.get(c["id"], "todo") != "done"]
    return score / total * 100, gaps


def render_report(assessment):
    """印出自評報告：逐項狀態、準備度、缺口。"""
    print("\n" + "=" * 100)
    print("自評報告：本系列 RAG 醫院客服 demo")
    print("=" * 100)
    for c in CHECKLIST:
        status = assessment.get(c["id"], "todo")
        print(f"  [{c['id']:>3}] {c['aiec']:5} {_MARK[status]:8} 佐證：{c['verify']}")
    readiness, gaps = assess(assessment)
    print("-" * 100)
    print(f"合規準備度：{readiness:.0f}%（{len(CHECKLIST) - len(gaps)}/{len(CHECKLIST)} 項已完全落實）")
    if gaps:
        print("尚待補齊的缺口：")
        for g in gaps:
            print(f"    - [{g['id']}] {g['aiec']}：{g['verify']}")


if __name__ == "__main__":
    render_checklist()
    render_report(ASSESSMENT)
