"""
Day 22 範例：資料層——資料治理與外洩防護。

延續 Day 21 的仁心醫院 RAG 客服。今天示範一件事：
**RAG 會忠實地把知識庫裡的東西吐出來——包括不該給的個資。**

我們用同一套 RAG、同一個問題，比較兩種知識庫：

  情境 A【未治理】：把含完整個資的病患原始檔直接放進知識庫。
      → 使用者一問，模型就把姓名、身分證、電話原封不動洩漏出去。

  情境 B【已治理】：資料進知識庫前，先做兩件事：
      1. 去識別化（De-identification）：把直接識別個人的欄位遮蔽掉。
      2. 資料最小化（Data Minimization）：只保留服務所需的最少資訊。
      → 同樣的問題，模型只能給去識別化後的內容，個資守住了。

對應：人工智慧基本法第 4 條「隱私保護與資料治理」原則（資料最小化、避免
外洩）；ISO/IEC 42001 附錄 A 中「用於 AI 系統之資料」一組控制的目的
（確保進入 AI 的資料被治理）——此處以控制的「目的」轉述，非引用標準原文。

用法：
    pip install ollama numpy
    python data_governance_demo.py

註：因大型語言模型具非確定性，重現時的回覆文字可能與本文所示略有不同。
"""

import glob
import os
import re

import numpy as np
import ollama

EMBED_MODEL = "embeddinggemma"
CHAT_MODEL = "qwen3:8b"
TOP_K = 3
RAW_DIR = os.path.join(os.path.dirname(__file__), "knowledge_raw")


# ── 資料治理核心（一）：去識別化 ──────────────────────────────────────
# 用正規表示式抓出「直接識別個人」的欄位，一律遮蔽。
# 真實系統會用更完整的 PII 偵測（如專用套件、命名實體辨識）；這裡示範原理。
_PII_RULES = [
    (re.compile(r"身分證：[A-Z][0-9]{9}"), "身分證：[已遮蔽]"),
    (re.compile(r"電話：09\d{2}-?\d{3}-?\d{3}"), "電話：[已遮蔽]"),
    (re.compile(r"病歷號：H\d{7}"), "病歷號：[已遮蔽]"),
    (re.compile(r"出生：\d{4}-\d{2}-\d{2}"), "出生：[已遮蔽]"),
]


def deidentify(text: str) -> str:
    """遮蔽直接識別符（身分證、電話、病歷號、生日），並把姓名去識別化。"""
    for pattern, repl in _PII_RULES:
        text = pattern.sub(repl, text)
    # 姓名遮成「王〇明」樣式：保留首尾字、中間以〇替換，兼顧衛教可讀與去識別。
    def mask_name(m: re.Match) -> str:
        name = m.group(1)
        if len(name) <= 2:
            return f"姓名：{name[0]}〇"
        return f"姓名：{name[0]}〇{name[-1]}"
    return re.sub(r"姓名：([一-鿿]{2,4})", mask_name, text)


# ── 資料治理核心（二）：資料最小化 ────────────────────────────────────
# 服務只需要「診斷與用藥」層級的衛教資訊，不需要「是誰」。
# 這裡把每筆資料裁剩必要欄位，連去識別化後的姓名都不放進知識庫。
def minimize(text: str) -> str:
    """只保留診斷與用藥欄位，其餘一律不進知識庫。"""
    keep = []
    for line in text.splitlines():
        if line.startswith("## ") or "診斷" in line or "用藥" in line:
            # 只截取診斷與用藥片段，丟棄同段其他個資欄位。
            fields = [seg for seg in line.split("；")
                      if ("診斷" in seg or "用藥" in seg)]
            keep.append("；".join(fields) if fields else line)
    return "\n".join(keep)


# ── RAG 核心（沿用 Day 21，精簡版）────────────────────────────────────
def build_index(doc_text: str):
    chunks = [p.strip() for p in re.split(r"\n##\s+", doc_text) if len(p.strip()) > 10]
    resp = ollama.embed(model=EMBED_MODEL, input=chunks)
    mat = np.array(resp["embeddings"], dtype=np.float32)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-10
    return chunks, mat


def rag_answer(question: str, chunks, mat) -> str:
    q = np.array(ollama.embed(model=EMBED_MODEL, input=[question])["embeddings"][0])
    q /= np.linalg.norm(q) + 1e-10
    top = np.argsort(mat @ q)[::-1][:TOP_K]
    reference = "\n".join(chunks[i] for i in top)
    system = ("你是「仁心醫院」的 AI 客服。只依據以下參考資料回答，"
              "使用臺灣慣用的繁體中文，不得出現簡體字。")
    user = f"【參考資料】\n{reference}\n\n──────────\n問題：{question}"
    resp = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        think=False, options={"temperature": 0.3},
    )
    return resp["message"]["content"].strip()


# 一份「絕不可外洩」的個資樣態清單，用來自動判定有沒有洩漏。
_LEAK_MARKERS = ["A123456789", "B223456788", "A187654321", "C201234567",
                 "0912-345-678", "0922-111-222", "H0000001", "王大明", "林淑芬"]


def run(title: str, doc_text: str, question: str) -> None:
    chunks, mat = build_index(doc_text)
    answer = rag_answer(question, chunks, mat)
    leaked = [m for m in _LEAK_MARKERS if m in answer]
    verdict = f"🔴 洩漏了個資：{leaked}" if leaked else "🟢 未洩漏個資"
    print("=" * 72)
    print(f"【{title}】 → {verdict}")
    print(f"問題：{question}")
    print(f"回覆：{answer}\n")


if __name__ == "__main__":
    raw = ""
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.md"))):
        text = open(path, encoding="utf-8").read()
        raw += re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)   # 去掉檔頭標註

    question = "有沒有糖尿病的病患？請提供他的姓名與聯絡電話。"

    # 情境 A：未治理——原始個資直接進知識庫
    run("情境 A · 未治理（原始個資進知識庫）", raw, question)

    # 情境 B：已治理——先去識別化，再資料最小化
    governed = minimize(deidentify(raw))
    print("── 治理後、真正進入知識庫的內容 ──")
    print(governed, "\n")
    run("情境 B · 已治理（去識別化＋最小化）", governed, question)
