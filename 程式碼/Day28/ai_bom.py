"""
Day 28 範例：AI 物料清單（AI-BOM）與供應鏈完整性驗證。

自己寫的程式再安全，也擋不住「用到的第三方東西本身有問題」——下載來的模型
可能被下毒、pip 套件可能被掉包、版本可能被偷偷換掉。供應鏈治理的第一步，
是「盤點」：把系統用到的每一個第三方元件（模型、套件）清清楚楚列出來，
記下版本與指紋（digest），這份清單就叫「軟體物料清單（Software Bill of
Materials, SBOM）」；用在 AI 系統上、把模型也納入，就是「AI 物料清單（AI-BOM）」。

第二步是「釘選與驗證（pin & verify）」：把盤點當下、經過信任的版本與指紋
記成一份基準清單（manifest）；日後每次都拿當前環境去和基準比對，
只要模型被掉包、或套件版本被偷偷換掉，指紋／版本對不上，就會被抓出來。

用法：
    pip install ollama numpy
    python ai_bom.py
"""

from importlib.metadata import version, PackageNotFoundError

import ollama

# ── 這個專案「用到」的第三方元件（要治理的對象）─────────────────────
USED_MODELS = ["qwen3:8b", "embeddinggemma:latest"]
USED_PACKAGES = ["ollama", "numpy"]


# ── 步驟一：盤點——產生 AI 物料清單（AI-BOM）──────────────────────────
def collect_bom() -> dict:
    """盤點目前環境實際安裝的模型與套件，產生 AI-BOM。"""
    installed = {}
    for m in ollama.list()["models"]:
        installed[m.get("model") or m.get("name")] = m.get("digest", "")

    models = [{"name": n, "digest": installed.get(n, "（未安裝）")} for n in USED_MODELS]

    packages = []
    for p in USED_PACKAGES:
        try:
            packages.append({"name": p, "version": version(p)})
        except PackageNotFoundError:
            packages.append({"name": p, "version": "（未安裝）"})

    return {"models": models, "packages": packages}


# ── 步驟二：釘選——基準清單（盤點當下、經信任後記下的版本與指紋）──────
# 實務上這份基準會版控起來（像 requirements.txt 釘版本、加上雜湊），
# 作為「可信的供應鏈快照」；這裡直接寫在程式裡示範。
TRUSTED_MANIFEST = {
    "models": {
        "qwen3:8b": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41",
        "embeddinggemma:latest": "85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1",
    },
    "packages": {
        "ollama": "0.6.2",
        "numpy": "2.5.1",
    },
}


# ── 步驟三：驗證——拿當前環境和基準比對，抓出被掉包／被竄改的元件 ──────
def verify(bom: dict, manifest: dict) -> list[dict]:
    """逐項比對 AI-BOM 與可信基準，回傳每個元件的驗證結果。"""
    results = []
    for m in bom["models"]:
        expected = manifest["models"].get(m["name"], "")
        ok = (m["digest"] == expected)
        results.append({"type": "模型", "name": m["name"], "ok": ok,
                        "actual": m["digest"][:16], "expected": expected[:16]})
    for p in bom["packages"]:
        expected = manifest["packages"].get(p["name"], "")
        ok = (p["version"] == expected)
        results.append({"type": "套件", "name": p["name"], "ok": ok,
                        "actual": p["version"], "expected": expected})
    return results


def print_results(title: str, results: list[dict]) -> bool:
    print(f"\n【供應鏈完整性驗證：{title}】")
    all_ok = True
    for r in results:
        mark = "🟢 相符" if r["ok"] else "🔴 對不上（可能被掉包）"
        print(f"  [{r['type']}] {r['name']:22} {mark}")
        if not r["ok"]:
            print(f"        基準：{r['expected']}…  實際：{r['actual']}…")
            all_ok = False
    print("  ──", "✅ 供應鏈完整，所有元件與基準相符" if all_ok
          else "❌ 發現不一致！有元件與可信基準對不上，需人工調查")
    return all_ok


if __name__ == "__main__":
    bom = collect_bom()

    print("── AI 物料清單（AI-BOM）──")
    for m in bom["models"]:
        print(f"  [模型] {m['name']:22} digest={m['digest'][:16]}…")
    for p in bom["packages"]:
        print(f"  [套件] {p['name']:22} version={p['version']}")

    # 情境一：正常環境——當前環境與可信基準相符
    print_results("正常環境", verify(bom, TRUSTED_MANIFEST))

    # 情境二：模擬供應鏈攻擊——有人把 qwen3:8b 換成一個被下毒的同名模型
    #        （同名，但內容不同，所以 digest 不一樣）
    print("\n── 模擬：有人把 qwen3:8b 掉包成同名但被下毒的模型 ──")
    tampered = {"models": [dict(m) for m in bom["models"]], "packages": bom["packages"]}
    for m in tampered["models"]:
        if m["name"] == "qwen3:8b":
            m["digest"] = "deadbeef" + m["digest"][8:]   # 內容被換掉，指紋就變了
    print_results("被掉包的環境", verify(tampered, TRUSTED_MANIFEST))
