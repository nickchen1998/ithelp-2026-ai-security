"""
Day 24 補充範例：出口個資過濾，手寫規則 vs 通用防護工具。

`output_guard_rag.py` 的 `redact_pii()` 是三條手寫的正規表示式，
只認得台灣的電話、國民身分證統一編號與本院病歷號格式。本檔把它和
LLM Guard（Protect AI 開源工具包，MIT 授權）的 Sensitive 輸出掃描器
擺在一起比。Sensitive 底層是 Microsoft Presidio，用具名實體辨識加規則
偵測個資，是這個領域最通用的開源方案之一。

比的目的不是分高下，而是看清楚兩者「認得什麼、不認得什麼」——
結論和 Day 23 的注入偵測恰好相反，值得對照著讀。

環境需求與 Day 23 相同：LLM Guard 尚無 Python 3.14 輪檔，請用 3.11／3.12。

    pip install llm-guard

首次執行會自動下載中英文斷詞模型。本檔不呼叫 Ollama。
"""

import sys

from output_guard_rag import redact_pii

try:
    from llm_guard.output_scanners import Sensitive
except ImportError:
    sys.exit("需要 llm-guard，請先在 Python 3.11／3.12 環境執行 pip install llm-guard")


# 每個案例標出「這句話裡有哪些個資該被遮掉」，作為對答案的依據。
CASES = [
    ("中文·姓名與電話",
     "王大明先生您好，您的聯絡電話 0912-345-678 已登記完成。",
     "王大明、0912-345-678"),
    ("中文·身分證與病歷號",
     "病患身分證 A123456789，病歷號 H0000001。",
     "A123456789、H0000001"),
    ("英文·姓名與電話",
     "Hello Mr. John Smith, your phone number 415-555-0123 is registered.",
     "John Smith、415-555-0123"),
]


def main() -> None:
    scanner = Sensitive(
        entity_types=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN"],
        redact=True,
    )

    for name, text, expected in CASES:
        ours, _ = redact_pii(text)
        theirs, _, _ = scanner.scan("", text)
        print("=" * 72)
        print(f"【{name}】應遮蔽：{expected}")
        print(f"  原文　　　　　：{text}")
        print(f"  手寫規則　　　：{ours}")
        print(f"  LLM Guard　　 ：{theirs}")
        print()


if __name__ == "__main__":
    main()
