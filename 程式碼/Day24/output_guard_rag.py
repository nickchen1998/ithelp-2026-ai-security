"""
Day 24 範例：RAG 輸出層防禦——出口敏感內容過濾、幻覺（grounding）防護、來源標註。

情境沿用 Day 21 的「仁心醫院」最小 RAG 客服。前面守住了資料層（Day 22）與
輸入層（Day 23），本檔補上最後一道關卡——「輸出層」：模型「吐出來的東西」
在送給使用者之前，要再過三道關。

  三道輸出層防禦（皆為可複用樣板）：
    1. 出口敏感內容過濾（redact_pii）：回覆送出前再掃一次個資，命中就遮蔽。
       這是縱深防禦的最後一道——就算資料層、輸入層都失守，出口仍能兜底。
    2. 幻覺防護（is_grounded）：檢索相似度太低＝知識庫其實查無依據，
       此時標記「查無足夠依據」，不讓模型硬掰（抑制幻覺）。
    3. 來源標註（attach_sources）：把答案依據的來源附在後面，讓答案可追溯、
       可查證——這正是「透明與可解釋」原則的技術落點。
  另加「過度依賴」的產品設計對策：附上免責提示，提醒 AI 回覆僅供參考。

知識庫（knowledge/）：
    - hospital_faq.md    ：虛構醫院 FAQ（LLM 生成假資料）。
    - ai_basic_law.md    ：《人工智慧基本法》節選（真實法律，可自由引用）。
    - internal_note.md   ：虛構內部備註，「刻意」殘留一筆未治理的假個資，
                           示範輸出層對「資料層失守」的兜底遮蔽。

用法：
    pip install ollama numpy
    ollama pull qwen3:8b
    ollama pull embeddinggemma
    python output_guard_rag.py

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
GROUNDING_THRESHOLD = 0.50   # 最高相似度低於此值，視為「知識庫查無足夠依據」
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


# ══════════════════════════════════════════════════════════════════════
#  RAG 核心：沿用 Day 21（載入切塊、向量化、檢索），此處不再詳述
# ══════════════════════════════════════════════════════════════════════
def load_and_chunk(knowledge_dir: str) -> list[dict]:
    chunks = []
    for path in sorted(glob.glob(os.path.join(knowledge_dir, "*.md"))):
        source = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        for part in re.split(r"\n##\s+", text):
            part = part.strip()
            if len(part) >= 10:
                chunks.append({"source": source, "text": part})
    return chunks


def embed(texts: list[str]) -> np.ndarray:
    resp = ollama.embed(model=EMBED_MODEL, input=texts)
    vecs = np.array(resp["embeddings"], dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    return vecs


def retrieve(question: str, chunks: list[dict], matrix: np.ndarray, top_k: int):
    q_vec = embed([question])[0]
    scores = matrix @ q_vec
    top_idx = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_idx]


# ══════════════════════════════════════════════════════════════════════
#  輸出層防禦 ①：出口敏感內容過濾（可複用樣板）
# ══════════════════════════════════════════════════════════════════════
# 個資遮蔽規則。這是「出口」的最後一道防線：不管內容為何來源，只要回覆裡
# 出現符合個資格式的字串，一律在送出前遮蔽。與 Day 22 的「進庫前去識別化」
# 相呼應——一個守入口、一個守出口，兩道疊起來才是縱深防禦。
_PII_RULES = [
    (re.compile(r"09\d{2}-?\d{3}-?\d{3}"), "[已遮蔽電話]"),
    (re.compile(r"[A-Z][12]\d{8}"), "[已遮蔽身分證]"),
    (re.compile(r"H\d{7}"), "[已遮蔽病歷號]"),
]


def redact_pii(text: str) -> tuple[str, bool]:
    """掃描並遮蔽回覆中的個資，回傳 (遮蔽後文字, 是否有命中)。"""
    hit = False
    for pattern, mask in _PII_RULES:
        text, n = pattern.subn(mask, text)
        hit = hit or n > 0
    return text, hit


# ══════════════════════════════════════════════════════════════════════
#  輸出層防禦 ②：幻覺防護（grounding check，可複用樣板）
# ══════════════════════════════════════════════════════════════════════
def is_grounded(hits: list[tuple]) -> bool:
    """檢索到的最高相似度是否足以支撐回答；太低代表知識庫其實查無依據。"""
    top_score = hits[0][1] if hits else 0.0
    return top_score >= GROUNDING_THRESHOLD


# ══════════════════════════════════════════════════════════════════════
#  輸出層防禦 ③：來源標註（可解釋，可複用樣板）
# ══════════════════════════════════════════════════════════════════════
DISCLAIMER = "（本回覆由 AI 客服依知識庫生成，僅供參考，不能取代專業醫療判斷。）"


def attach_sources(reply: str, hits: list[tuple]) -> str:
    """在回覆後附上依據來源與免責提示，讓答案可追溯、可查證。"""
    sources = "、".join(dict.fromkeys(c["source"] for c, _ in hits))  # 去重、保序
    return f"{reply}\n📎 依據來源：{sources}\n{DISCLAIMER}"


# ══════════════════════════════════════════════════════════════════════
#  生成：未設防（Day 21 原版）vs 已設防（本日新增輸出層三道防禦）
# ══════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """你是「仁心醫院」的 AI 客服「仁心小助手」。
請「只依據」以下提供的參考資料回答使用者的問題，簡潔有禮地回覆。
務必使用臺灣慣用的繁體中文，不得出現任何簡體字。
若參考資料中找不到答案，請誠實說「這部分建議您直接聯繫本院服務台」，不要自行編造。"""


def _generate_raw(question: str, contexts: list[dict]) -> str:
    """呼叫模型生成原始回覆（尚未經過輸出層處理）。"""
    reference = "\n\n".join(
        f"【參考資料 {i + 1}｜來源：{c['source']}】\n{c['text']}"
        for i, c in enumerate(contexts)
    )
    user_prompt = f"{reference}\n\n──────────\n使用者問題：{question}"
    resp = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        think=False,
        options={"temperature": 0.3},
    )
    return resp["message"]["content"].strip()


def answer_naive(question: str, hits: list[tuple]) -> str:
    """未設防：模型生成什麼就直接回什麼（重現 Day 21 的做法）。"""
    return _generate_raw(question, [c for c, _ in hits])


def answer_guarded(question: str, hits: list[tuple]) -> str:
    """已設防：先做 grounding 檢查，再生成，最後出口過濾＋來源標註。"""
    # 防禦 ②：grounding 檢查——查無足夠依據就不硬答
    if not is_grounded(hits):
        print(f"    ⚠️ 輸出層：最高相似度 {hits[0][1]:.2f} < 門檻 {GROUNDING_THRESHOLD}，判定查無足夠依據。")
        return ("關於您的問題，本院知識庫中查無足夠的對應資料，為避免提供不準確的資訊，"
                "建議您直接聯繫本院服務台由專人為您服務。")
    reply = _generate_raw(question, [c for c, _ in hits])
    # 防禦 ①：出口敏感內容過濾
    reply, redacted = redact_pii(reply)
    if redacted:
        print("    🚨 輸出層：回覆中偵測到個資格式，已於出口遮蔽（資料層兜底）。")
    # 防禦 ③：來源標註 + 免責提示
    return attach_sources(reply, hits)


def demo(title: str, question: str, chunks, matrix) -> None:
    hits = retrieve(question, chunks, matrix, TOP_K)
    print("=" * 72)
    print(f"【{title}】")
    print(f"❓ 使用者問題：{question}")
    print("🔎 檢索到：", "、".join(f"{c['source']}({s:.2f})" for c, s in hits))
    print(f"🔴 未設防回覆：{answer_naive(question, hits)}")
    print("🟢 已設防：")
    print(f"    回覆：{answer_guarded(question, hits)}\n")


if __name__ == "__main__":
    chunks = load_and_chunk(KNOWLEDGE_DIR)
    matrix = embed([c["text"] for c in chunks])
    print(f"📚 知識庫共 {len(chunks)} 段，已建立向量索引。\n")

    # 情境一：正常問答——展示來源標註與可解釋
    demo("正常問答：來源標註讓答案可追溯",
         "門診時間是幾點到幾點？", chunks, matrix)

    # 情境二：幻覺防護——問知識庫查無的問題，不讓模型硬掰
    demo("幻覺防護：知識庫查無依據就不硬答",
         "請問貴院附設的停車場一小時收費多少錢？", chunks, matrix)

    # 情境三：出口兜底——資料層殘留個資，輸出層在出口遮蔽
    demo("出口兜底：殘留個資在出口被遮蔽",
         "家醫科的聯絡窗口是誰？電話幾號？", chunks, matrix)
