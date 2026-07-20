"""
Day 21 範例：最小可跑的 RAG（檢索增強生成）客服。

情境：一間虛構的「仁心醫院」AI 客服「仁心小助手」。它不靠模型死記硬背，
而是先「查資料」再「回答」——這就是 RAG（Retrieval-Augmented Generation，
檢索增強生成）。本程式把 RAG 拆成最基本的五個步驟，每一步都用最少的程式碼
呈現，方便理解；不引入任何向量資料庫或框架，只用 numpy + 本機 Ollama。

  五步驟：
    1. 載入（Load）    ：把知識庫文件讀進來。
    2. 切塊（Chunk）   ：把長文件切成一小段一小段。
    3. 向量化（Embed） ：用 embeddinggemma 把每段文字轉成向量。
    4. 檢索（Retrieve）：把問題也轉成向量，找出最相近的幾段。
    5. 生成（Generate）：把「問題 + 檢索到的段落」交給 qwen3:8b 產生答案。

知識庫（knowledge/）：
    - hospital_faq.md ：虛構醫院 FAQ（LLM 生成的假資料，非真實資訊）。
    - ai_basic_law.md ：《人工智慧基本法》節選（真實法律，可自由引用）。

用法：
    pip install ollama numpy
    ollama pull qwen3:8b
    ollama pull embeddinggemma
    python minimal_rag.py

註：因大型語言模型具非確定性，重現時的回覆文字可能與本文所示略有不同。
"""

import glob
import os
import re

import numpy as np
import ollama

EMBED_MODEL = "embeddinggemma"   # 負責「向量化」的嵌入模型
CHAT_MODEL = "qwen3:8b"          # 負責「生成」答案的對話模型
TOP_K = 3                        # 每次檢索取回最相近的段落數
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


# ── 步驟 1 + 2：載入文件並切塊 ────────────────────────────────────────
def load_and_chunk(knowledge_dir: str) -> list[dict]:
    """讀取 knowledge/ 下所有 .md，依段落（##）切成小塊。

    切塊是 RAG 的關鍵：文件太長無法整份塞給模型，也不利精準檢索；
    切成一段一段後，才能「只取用最相關的幾段」。這裡用最直覺的切法——
    依 Markdown 的 ## 小標題分段；真實系統會用更講究的切塊策略。
    """
    chunks = []
    for path in sorted(glob.glob(os.path.join(knowledge_dir, "*.md"))):
        source = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # 移除 HTML 註解（檔頭的資料標註），不讓它進入知識內容。
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        # 依 ## 小標題切段。
        for part in re.split(r"\n##\s+", text):
            part = part.strip()
            if len(part) < 10:            # 跳過過短的空段
                continue
            chunks.append({"source": source, "text": part})
    return chunks


# ── 步驟 3：向量化 ────────────────────────────────────────────────────
def embed(texts: list[str]) -> np.ndarray:
    """把一批文字轉成向量矩陣（每列一個向量）。"""
    resp = ollama.embed(model=EMBED_MODEL, input=texts)
    vecs = np.array(resp["embeddings"], dtype=np.float32)
    # 正規化成單位向量，之後用「內積」就等於「餘弦相似度」。
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    return vecs


# ── 步驟 4：檢索 ──────────────────────────────────────────────────────
def retrieve(question: str, chunks: list[dict], matrix: np.ndarray, top_k: int):
    """把問題轉成向量，找出知識庫中最相近的 top_k 段。"""
    q_vec = embed([question])[0]
    scores = matrix @ q_vec                      # 餘弦相似度（值越大越相近）
    top_idx = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_idx]


# ── 步驟 5：生成 ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """你是「仁心醫院」的 AI 客服「仁心小助手」。
請「只依據」以下提供的參考資料回答使用者的問題，簡潔有禮地回覆。
務必使用臺灣慣用的繁體中文（例如「身分」而非「身份」、「攜帶」而非「携带」），
不得出現任何簡體字。
若參考資料中找不到答案，請誠實說「這部分建議您直接聯繫本院服務台」，不要自行編造。
回答涉及個人病情或用藥時，請提醒使用者諮詢專業醫療人員。"""


def generate(question: str, contexts: list[dict]) -> str:
    """把檢索到的段落當「參考資料」，連同問題交給對話模型生成答案。"""
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
        options={"temperature": 0.3},   # 調低隨機性，讓回答貼近資料、方便重現
    )
    return resp["message"]["content"].strip()


def answer(question: str, chunks: list[dict], matrix: np.ndarray) -> None:
    hits = retrieve(question, chunks, matrix, TOP_K)
    print("=" * 72)
    print(f"❓ 使用者問題：{question}")
    print("🔎 檢索到最相關的段落：")
    for c, score in hits:
        preview = c["text"].split("\n")[0][:30]
        print(f"    - [{score:.3f}] {c['source']}｜{preview}…")
    reply = generate(question, [c for c, _ in hits])
    print(f"💬 仁心小助手：{reply}\n")


if __name__ == "__main__":
    # 1+2 載入與切塊
    chunks = load_and_chunk(KNOWLEDGE_DIR)
    print(f"📚 知識庫共切成 {len(chunks)} 個段落。")
    # 3 向量化（先把整個知識庫算好向量，之後每次提問重複使用）
    matrix = embed([c["text"] for c in chunks])
    print(f"🧮 已建立 {matrix.shape[0]} × {matrix.shape[1]} 的向量索引。\n")

    # 4+5 針對幾個問題做檢索與生成
    answer("門診時間是幾點到幾點？", chunks, matrix)
    answer("我要申請診斷證明書，要帶什麼？", chunks, matrix)
    answer("AI 生成的內容需要標示嗎？法規怎麼規定？", chunks, matrix)
    answer("幫我查王小明的病歷內容", chunks, matrix)   # 知識庫查無 → 應誠實婉拒
