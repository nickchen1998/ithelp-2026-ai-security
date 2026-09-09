"""
Day 22 範例（二）：個資的可逆假名化與還原——送模型前遮蔽、回覆後還原。

`data_governance_demo.py` 處理的是「入庫前」這一站：個資根本不該進知識庫，
所以那裡的去識別化是**不可逆**的——遮掉就回不來了。

但還有一站需要處理個資：**推論時**。當病患本人（已通過身分驗證）要問
「我的用藥是什麼」，系統勢必要把他那一筆病歷送進模型。這時遮蔽如果也是
不可逆的，回覆就會殘缺；但完全不遮，個資就會離開組織邊界進入模型
（若是外部雲端 API，這一步等同把個資交給第三方）。

解法是把「遮蔽」換成**可逆的假名化（Pseudonymization）**，走完整的來回：

    原始病歷 ──假名化──▶ 佔位符版本 ──▶ 模型 ──▶ 含佔位符的回覆
                  │                                      │
                  └─── 對照表存在本地金庫（vault） ───▶ 還原 ──▶ 使用者

關鍵有三：
  1. 同一個真值永遠對到同一個佔位符 —— 模型才分得清「誰是誰」，
     照樣能組織語句、寫出完整通知，不會因為遮蔽而答不出來。
  2. 對照表（vault）只存在自家系統，從不隨提示送出。
  3. **還原本身是要授權的動作** —— 不是每個拿到回覆的人都能還原。

用法：
    pip install ollama
    python pii_roundtrip_demo.py

註：因大型語言模型具非確定性，重現時的回覆文字可能與本文所示略有不同。
"""

import re

import ollama

CHAT_MODEL = "qwen3:8b"

# ── 步驟一：定義「哪裡是個資、屬於哪一類」 ────────────────────────────
# 身分證、病歷號、手機有固定格式，可直接靠格式辨識；姓名與生日沒有專屬格式，
# 只能靠欄位標籤定位。兩種寫法各有破口，取捨見本文「誠實的限制」。
_PII_PATTERNS = [
    ("姓名", re.compile(r"(?<=姓名：)[一-鿿]{2,4}")),
    ("身分證", re.compile(r"[A-Z][12]\d{8}")),
    ("病歷號", re.compile(r"H\d{7}")),
    ("生日", re.compile(r"(?<=出生：)\d{4}-\d{2}-\d{2}")),
    ("電話", re.compile(r"09\d{2}-?\d{3}-?\d{3}")),
]


# ── 步驟二：假名化——把真值換成佔位符，對照關係留在金庫 ────────────────
def pseudonymize(text: str) -> tuple[str, dict[str, str]]:
    """回傳（佔位符版本, 金庫）。金庫是 {佔位符: 真值} 的對照表。"""
    vault: dict[str, str] = {}
    reverse: dict[str, str] = {}      # 真值 → 佔位符，確保同值同代號
    counters: dict[str, int] = {}

    def to_token(kind: str, match: re.Match) -> str:
        value = match.group(0)
        if value in reverse:          # 這個真值先前出現過 → 沿用同一個佔位符
            return reverse[value]
        counters[kind] = counters.get(kind, 0) + 1
        token = f"【{kind}_{counters[kind]}】"
        vault[token] = value
        reverse[value] = token
        return token

    for kind, pattern in _PII_PATTERNS:
        text = pattern.sub(lambda m, k=kind: to_token(k, m), text)
    return text, vault


# ── 步驟三：還原——但這是一個「要授權」的動作 ──────────────────────────
def rehydrate(text: str, vault: dict[str, str], authorized: bool) -> str:
    """只有請求者確為資料當事人（或有權人員）時，才把佔位符換回真值。

    未授權時佔位符原樣留著：真值自始至終沒有離開金庫。
    """
    if not authorized:
        return text
    for token, value in vault.items():
        text = text.replace(token, value)
    return text


# ── 步驟四：送出前自檢——確認提示裡沒有任何真值 ────────────────────────
def leaked_values(prompt: str, vault: dict[str, str]) -> list[str]:
    """列出提示中殘留的真值。空清單＝這次呼叫沒有個資離開組織邊界。"""
    return [value for value in vault.values() if value in prompt]


def ask_model(masked_record: str, question: str) -> tuple[str, str]:
    """回傳（實際送出的提示, 模型回覆）。提示一併回傳，才能留下自檢證據。"""
    system = (
        "你是「仁心醫院」的 AI 客服。只依據參考資料回答，"
        "使用臺灣慣用的繁體中文，不得出現簡體字。"
        "參考資料中形如【姓名_1】的字串是代號，不是真實內容："
        "請在回覆中原樣保留，不得改寫、翻譯或自行猜測它代表什麼。"
    )
    user = f"【參考資料】\n{masked_record}\n\n──────────\n問題：{question}"
    resp = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        think=False, options={"temperature": 0.3},
    )
    return f"{system}\n{user}", resp["message"]["content"].strip()


# 這一筆病歷是「通過身分驗證後、由查詢通道取回」的單筆資料（存取控制見 Day 25），
# 不是從 RAG 知識庫檢索來的——個資本來就不該待在知識庫裡。
RECORD = """病歷摘要
姓名：王大明；病歷號：H0000001；身分證：A123456789；出生：1958-03-12；
電話：0912-345-678
診斷：第二型糖尿病
用藥：metformin 500mg 每日兩次，隨餐服用
回診安排：三個月一次，下次為 8 月 15 日上午
"""

QUESTION = ("請幫我擬一則回診提醒簡訊：開頭稱呼我的姓名，"
            "並附上我的病歷號與聯絡電話供院方核對。")


def main() -> None:
    masked, vault = pseudonymize(RECORD)
    print("── ① 原始病歷（留在組織內，不出境）──")
    print(RECORD)
    print("── ② 假名化後、真正送進模型的內容 ──")
    print(masked)
    print("── 金庫（vault，只存在本地）──")
    for token, value in vault.items():
        print(f"   {token} → {value}")

    prompt, answer = ask_model(masked, QUESTION)
    residue = leaked_values(prompt, vault)
    print(f"\n── ③ 送出前自檢：提示中殘留的真值 → "
          f"{residue if residue else '無（0 筆）🟢'}")
    print("\n── ④ 模型回覆（模型眼中的世界只有代號）──")
    print(answer)

    for label, authorized in [("已驗證為本人 P001", True), ("未驗證的第三方", False)]:
        final = rehydrate(answer, vault, authorized)
        unresolved = [t for t in re.findall(r"【[^】]+】", final) if t not in vault]
        print("=" * 72)
        print(f"── ⑤ 交付給「{label}」（authorized={authorized}）──")
        print(final)
        if unresolved:
            print(f"⚠️ 金庫中查無此代號，模型可能自行杜撰：{unresolved}")


if __name__ == "__main__":
    main()
