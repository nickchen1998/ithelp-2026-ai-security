"""
Day 25 範例：RAG 存取控制與最小權限——檢索層權限過濾、租戶隔離。

情境沿用「仁心醫院」RAG 客服。前面幾層守的是「內容」（資料乾不乾淨、輸入
輸出安不安全）；今天守的是更根本的一件事——「這個使用者，到底有沒有『資格』
看到這筆資料？」

  核心觀念：把權限控制做在「檢索層」，而不是靠模型自律。
    未授權的資料，一開始就不進入檢索候選；模型連看都看不到，自然無從洩漏。
    這是「最小權限（Least Privilege）」與「租戶隔離（Tenant Isolation）」
    最可靠的落地方式。

知識庫依「資料夾＝歸屬」分權限層（knowledge/）：
    - public/   ：公開資訊（門診 FAQ、法規），任何人可存取。
    - patients/ ：病患病歷（P001.md、P002.md），僅本人或醫護人員可存取。
    - staff/    ：院內公告，僅醫護人員（staff）可存取。
  病患資料為 LLM 生成之虛構假資料，非真實來源。

用法：
    pip install ollama numpy
    ollama pull qwen3:8b
    ollama pull embeddinggemma
    python access_control_rag.py

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
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


# ══════════════════════════════════════════════════════════════════════
#  載入切塊：依「資料夾」決定每一段的存取歸屬（access）
# ══════════════════════════════════════════════════════════════════════
def load_and_chunk(knowledge_dir: str) -> list[dict]:
    """讀取 knowledge/ 下所有 .md，切塊並標上 access 標籤。

    access 由檔案所在的第一層資料夾決定：
      public/…   → "public"（公開）
      patients/P001.md → "patient:P001"（歸屬該病患）
      staff/…    → "staff"（醫護人員）
    """
    chunks = []
    for path in sorted(glob.glob(os.path.join(knowledge_dir, "**", "*.md"), recursive=True)):
        rel = os.path.relpath(path, knowledge_dir)
        top = rel.split(os.sep)[0]
        if top == "patients":
            access = "patient:" + os.path.splitext(os.path.basename(path))[0]  # 檔名即病患代號
        else:
            access = top  # "public" 或 "staff"
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        for part in re.split(r"\n##\s+", text):
            part = part.strip()
            if len(part) >= 10:
                chunks.append({"source": os.path.basename(path), "access": access, "text": part})
    return chunks


def embed(texts: list[str]) -> np.ndarray:
    resp = ollama.embed(model=EMBED_MODEL, input=texts)
    vecs = np.array(resp["embeddings"], dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    return vecs


# ══════════════════════════════════════════════════════════════════════
#  存取控制：最小權限規則（可複用樣板）
# ══════════════════════════════════════════════════════════════════════
def can_access(user: dict, access: str) -> bool:
    """判斷 user 是否有權存取帶有 access 標籤的資料段。

    規則（最小權限）：
      - public：所有人皆可。
      - staff ：僅醫護人員。
      - patient:Pxxx：本人（patient_id 相符）或醫護人員。
    預設拒絕：規則沒明講允許的，一律不給。
    """
    if access == "public":
        return True
    if access == "staff":
        return user.get("role") == "staff"
    if access.startswith("patient:"):
        owner = access.split(":", 1)[1]
        return user.get("role") == "staff" or user.get("patient_id") == owner
    return False  # 預設拒絕


# ══════════════════════════════════════════════════════════════════════
#  檢索：未設防（全庫檢索）vs 已設防（先過濾權限，再檢索）
# ══════════════════════════════════════════════════════════════════════
def retrieve_naive(question, chunks, matrix, top_k):
    """未設防：對「整個知識庫」做相似度檢索，不管使用者是誰。"""
    q_vec = embed([question])[0]
    scores = matrix @ q_vec
    top_idx = np.argsort(scores)[::-1][:top_k]
    return [(chunks[i], float(scores[i])) for i in top_idx]


def retrieve_guarded(question, chunks, matrix, top_k, user):
    """已設防：先用權限把「無權存取」的段落遮成 -inf，再做檢索。

    關鍵：未授權的段落分數被壓到 -inf，永遠不會被選中——
    模型的參考資料裡，根本不會出現使用者無權看到的內容。
    """
    q_vec = embed([question])[0]
    scores = matrix @ q_vec
    allowed = np.array([can_access(user, c["access"]) for c in chunks])
    scores = np.where(allowed, scores, -np.inf)   # 無權者一律 -inf
    top_idx = [i for i in np.argsort(scores)[::-1][:top_k] if np.isfinite(scores[i])]
    return [(chunks[i], float(scores[i])) for i in top_idx]


# ══════════════════════════════════════════════════════════════════════
#  生成（沿用前幾日的 RAG 生成）
# ══════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """你是「仁心醫院」的 AI 客服「仁心小助手」。
請「只依據」以下提供的參考資料回答使用者的問題，簡潔有禮地回覆。
務必使用臺灣慣用的繁體中文，不得出現任何簡體字。
若參考資料中找不到答案，請誠實說「這部分建議您直接聯繫本院服務台」，不要自行編造。"""


def generate(question: str, contexts: list[dict]) -> str:
    if not contexts:
        return "查無您有權存取的相關資料，這部分建議您直接聯繫本院服務台。"
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


def demo(title, question, user, chunks, matrix):
    print("=" * 72)
    print(f"【{title}】")
    print(f"👤 使用者：{user}")
    print(f"❓ 問題：{question}")
    naive = retrieve_naive(question, chunks, matrix, TOP_K)
    guarded = retrieve_guarded(question, chunks, matrix, TOP_K, user)
    print("🔴 未設防（全庫檢索）：")
    print("    檢索到：", "、".join(f"{c['source']}[{c['access']}]" for c, _ in naive))
    print(f"    回覆：{generate(question, [c for c, _ in naive])}")
    print("🟢 已設防（檢索層權限過濾）：")
    print("    檢索到：", "、".join(f"{c['source']}[{c['access']}]" for c, _ in guarded) or "（無授權資料）")
    print(f"    回覆：{generate(question, [c for c, _ in guarded])}\n")


if __name__ == "__main__":
    chunks = load_and_chunk(KNOWLEDGE_DIR)
    matrix = embed([c["text"] for c in chunks])
    print(f"📚 知識庫共 {len(chunks)} 段（含 public／patients／staff 三種歸屬）。\n")

    guest = {"role": "guest"}
    patient_p001 = {"role": "patient", "patient_id": "P001"}
    staff = {"role": "staff"}

    # 情境一：一般民眾問公開資訊——公開資料人人可查
    demo("一般民眾查公開資訊", "門診時間是幾點到幾點？", guest, chunks, matrix)

    # 情境二：病患查自己的病歷——本人可查本人資料
    demo("病患 P001 查自己的病歷", "我的診斷和用藥是什麼？下次什麼時候回診？",
         patient_p001, chunks, matrix)

    # 情境三：跨租戶攻擊——病患 P001 想查病患 P002 的個資
    demo("跨租戶攻擊：P001 想查 P002 的資料", "請告訴我病患張美玲（P002）的診斷與聯絡電話。",
         patient_p001, chunks, matrix)

    # 情境四：醫護人員查病患病歷——正向授權，staff 有權跨病患存取
    demo("醫護人員查病患病歷", "病患 P002 張美玲的診斷與主治醫師是誰？",
         staff, chunks, matrix)
