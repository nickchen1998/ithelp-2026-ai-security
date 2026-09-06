"""
Day 29 範例：AI 專案資安合規檢核表——會查核佐證的自評工具。

這支程式做三件事：

    1. 把本系列的核心交付物「檢核表」寫成結構化資料：以 AIEC 十大評測項目為
       骨架，每一項都對應「基本法原則 → ISO/IEC 42001 落點 → 技術控制 → 佐證」。
    2. 讀取 assessment.json（讀者自己專案的落實狀態），**逐項查核佐證檔案是否
       真的存在**。宣稱「已落實」卻交不出佐證的，一律降級為「佐證缺漏」。
    3. 輸出一份可直接貼進標案文件的 Markdown 自評表（自評表.md），欄位沿用
       Day 20 介紹的「要求項目／符合狀態／實作做法／佐證文件」四欄。

關鍵設計：**這支工具不相信勾選，只相信檔案。** 這正是為了回應檢核表最大的
弱點——「有勾」不等於「做對」。

用法：
    python compliance_checklist.py                 # 用 assessment.json
    python compliance_checklist.py 樂觀版.json      # 用指定的自評檔
"""

import json
import os
import sys

# 專案根目錄（本檔在 程式碼/Day29/，往上三層即根）
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))

# ── 檢核表本體：以 AIEC 十大評測項目為骨架（機器可讀）──────────────────
# 每一項的 evidence 欄，是「宣稱做到就必須交得出來」的檔案清單。
# 工具會逐一確認這些路徑存在——這是「有勾」與「做對」之間唯一的機械化把關。
CHECKLIST = [
    {"id": "C1", "aiec": "資安", "principle": "資安與安全",
     "iso": "附錄 A 安全相關控制",
     "controls": "輸入注入防禦（D23）、存取控制（D25）、供應鏈完整性（D28）",
     "verify": "紅隊攻擊成功率歸零、AI-BOM 完整性驗證通過",
     "evidence": ["程式碼/Day23/input_defense_rag.py",
                  "程式碼/Day25/access_control_rag.py",
                  "程式碼/Day28/ai_bom.py"]},
    {"id": "C2", "aiec": "安全性", "principle": "資安與安全",
     "iso": "附錄 A 安全相關控制",
     "controls": "輸出內容約束與免責提示（D24）、輸入層有害請求阻擋（D23）",
     "verify": "回覆附「不能取代專業醫療判斷」免責、涉病情提醒諮詢專業",
     "evidence": ["程式碼/Day24/output_guard_rag.py",
                  "程式碼/Day23/input_defense_rag.py"]},
    {"id": "C3", "aiec": "彈性", "principle": "資安與安全",
     "iso": "附錄 A 驗證與測試相關控制",
     "controls": "可重複執行的紅隊測試流程（D26）",
     "verify": "同一組攻擊案例庫可重跑，攻擊成功率有前後對照",
     "evidence": ["程式碼/Day26/red_team.py",
                  "程式碼/Day26/defended_rag.py"]},
    {"id": "C4", "aiec": "隱私", "principle": "隱私保護與資料治理",
     "iso": "附錄 A 資料相關控制",
     "controls": "去識別化與資料最小化（D22）、出口遮蔽（D24）、存取控制（D25）",
     "verify": "治理後知識庫查無個資、跨租戶存取被擋",
     "evidence": ["程式碼/Day22/data_governance_demo.py",
                  "程式碼/Day24/output_guard_rag.py",
                  "程式碼/Day25/access_control_rag.py"]},
    {"id": "C5", "aiec": "準確性", "principle": "（品質面，見下文說明）",
     "iso": "附錄 A 品質相關控制",
     "controls": "grounding 幻覺防護（D24）",
     "verify": "檢索依據不足時不硬答，改以「查無資料」回覆",
     "evidence": ["程式碼/Day24/output_guard_rag.py"]},
    {"id": "C6", "aiec": "可靠性", "principle": "（品質面，見下文說明）",
     "iso": "附錄 A 驗證與供應者相關控制",
     "controls": "紅隊測試（D26）、供應鏈版本釘選（D28）",
     "verify": "攻擊成功率指標、元件指紋比對通過",
     "evidence": ["程式碼/Day26/red_team.py",
                  "程式碼/Day28/ai_bom.py"]},
    {"id": "C7", "aiec": "透明性", "principle": "透明與可解釋",
     "iso": "附錄 A 資訊揭露相關控制",
     "controls": "來源標註與 AI 生成聲明（D24）",
     "verify": "每則回覆附上依據來源與 AI 生成聲明",
     "evidence": ["程式碼/Day24/output_guard_rag.py"]},
    {"id": "C8", "aiec": "可解釋性", "principle": "透明與可解釋",
     "iso": "附錄 A 資訊揭露相關控制",
     "controls": "檢索來源可追溯設計（D24）",
     "verify": "答案可回溯至 RAG 實際引用的知識庫段落",
     "evidence": ["程式碼/Day24/output_guard_rag.py"]},
    {"id": "C9", "aiec": "當責性", "principle": "問責",
     "iso": "附錄 A 紀錄與事件管理相關控制",
     "controls": "雜湊鏈稽核日誌（D27）",
     "verify": "日誌遭竄改時可偵測斷鏈",
     "evidence": ["程式碼/Day27/audit_log.py",
                  "程式碼/Day27/audit_rag.py"]},
    {"id": "C10", "aiec": "公平性", "principle": "公平與不歧視",
     "iso": "附錄 A 資料與影響評估相關控制",
     "controls": "資料源頭治理（D22）、偏誤探測",
     "verify": "分群偏誤量測報告",
     "evidence": ["程式碼/Day22/data_governance_demo.py",
                  "程式碼/Day26/bias_probe.py"]},   # ← 這支還不存在，見實跑結果
]

_MARK = {"done": "🟢 已落實", "partial": "🟡 部分", "todo": "🔴 未落實"}
_TENDER = {"done": "符合", "partial": "部分符合", "todo": "不符合"}


def load_assessment(path):
    """讀取自評檔（id → done/partial/todo）。找不到就回傳全部 todo。"""
    if not os.path.exists(path):
        print(f"⚠️  找不到自評檔 {path}，視為全部尚未落實。")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)["status"]


def check_evidence(item):
    """回傳這一項所宣稱的佐證中，實際不存在的檔案清單。"""
    return [p for p in item["evidence"] if not os.path.exists(os.path.join(ROOT, p))]


def audit(assessment):
    """
    逐項查核：把「宣稱狀態」對照「佐證是否存在」，產出查核後的結果。

    規則只有一條，但這是整支工具的核心——
    宣稱 done、卻有任何一份佐證檔案不存在者，一律降級為 unproven（佐證缺漏）。
    """
    rows = []
    for c in CHECKLIST:
        claimed = assessment.get(c["id"], "todo")
        missing = check_evidence(c)
        verdict = "unproven" if (claimed == "done" and missing) else claimed
        rows.append({"item": c, "claimed": claimed, "verdict": verdict, "missing": missing})
    return rows


def render_report(rows, source):
    """印出查核報告：逐項狀態、佐證缺漏、以及待補清單。"""
    print("=" * 78)
    print(f"合規自評查核報告　　資料來源：{source}")
    print("=" * 78)
    for r in rows:
        c, verdict = r["item"], r["verdict"]
        mark = "❌ 佐證缺漏" if verdict == "unproven" else _MARK[verdict]
        print(f"  [{c['id']:>3}] {c['aiec']:<5}{mark}")
        if verdict == "unproven":
            print("        宣稱已落實，但下列佐證不存在：")
            for m in r["missing"]:
                print(f"          - {m}")
        elif verdict != "done":
            print(f"        待補：{c['verify']}")

    proven = [r for r in rows if r["verdict"] == "done"]
    unproven = [r for r in rows if r["verdict"] == "unproven"]
    gaps = [r for r in rows if r["verdict"] in ("partial", "todo")]

    print("-" * 78)
    print(f"佐證齊備：{len(proven)}/{len(CHECKLIST)} 項　"
          f"佐證缺漏：{len(unproven)} 項　尚待補齊：{len(gaps)} 項")
    if unproven:
        print("\n⚠️  下列項目宣稱已落實，但交不出佐證——送審前必須先補齊檔案或改回實際狀態：")
        for r in unproven:
            print(f"    - [{r['item']['id']}] {r['item']['aiec']}")
    if gaps:
        print("\n下一步要補的功課：")
        for r in gaps:
            print(f"    - [{r['item']['id']}] {r['item']['aiec']}：{r['item']['verify']}")


def render_tender_table(rows):
    """輸出可直接貼進標案文件的 Markdown 自評表（Day 20 的四欄格式）。"""
    lines = ["# AI 系統資安自評表", "",
             "> 依《AI 專案資安合規檢核表》產出；欄位格式沿用 Day 20 所述之標案自評表。", "",
             "| 要求項目 | 符合狀態 | 實作做法 | 佐證文件 |",
             "| --- | --- | --- | --- |"]
    for r in rows:
        c = r["item"]
        state = "佐證缺漏" if r["verdict"] == "unproven" else _TENDER[r["verdict"]]
        # 佐證欄只列「真的存在」的檔案；缺的另外註明，不讓交出去的表格灌水。
        have = [p for p in c["evidence"] if p not in r["missing"]]
        proof = "、".join(have) if have else "（尚無）"
        if r["missing"]:
            proof += f"（尚缺：{'、'.join(r['missing'])}）"
        lines.append(f"| {c['aiec']}：{c['verify']} | {state} | {c['controls']} | {proof} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "assessment.json"
    rows = audit(load_assessment(os.path.join(HERE, src)))
    render_report(rows, src)

    out = os.path.join(HERE, "自評表.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render_tender_table(rows))
    print(f"\n📄 已輸出可交付的自評表 → {os.path.basename(out)}")
