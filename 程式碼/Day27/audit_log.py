"""
Day 27 範例：稽核日誌與可追溯性——結構化紀錄 + 雜湊鏈防竄改。

這支模組是可複用的「稽核日誌」樣板，回答稽核日誌的三個核心問題：
    1. 記什麼：記「誰、何時、做了什麼、系統怎麼決策」的中繼資料，
       但「不記原始敏感內容」——日誌本身若含個資，就變成新的外洩點。
    2. 留多久：每筆帶時間戳，可依保存政策（retention）保留與清理（見文章討論）。
    3. 怎麼防竄改：用「雜湊鏈（hash chain）」把每一筆日誌串起來——
       每筆的雜湊都包含前一筆的雜湊，只要有人竄改任何一筆，
       後面所有雜湊就對不上，竄改立刻被驗證出來（append-only、tamper-evident）。
"""

import hashlib
import json


def _hash(prev_hash: str, entry: dict) -> str:
    """一筆日誌的雜湊 = SHA-256(前一筆雜湊 + 本筆內容的正規化 JSON)。"""
    # sort_keys 確保同樣內容永遠得到同樣的 JSON 字串（正規化），雜湊才穩定。
    payload = prev_hash + json.dumps(entry, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditLog:
    """append-only 的稽核日誌，內建雜湊鏈防竄改。"""

    GENESIS = "0" * 64   # 鏈的起點（創世雜湊）

    def __init__(self):
        self.records: list[dict] = []

    def append(self, entry: dict) -> dict:
        """新增一筆日誌，串上雜湊鏈。回傳完整的紀錄。"""
        prev_hash = self.records[-1]["hash"] if self.records else self.GENESIS
        record = {
            "seq": len(self.records) + 1,
            "entry": entry,
            "prev_hash": prev_hash,
            "hash": _hash(prev_hash, entry),
        }
        self.records.append(record)
        return record

    def verify(self) -> tuple[bool, int]:
        """驗證整條鏈是否完整。回傳 (是否完整, 第一個出問題的 seq；0 表示完整)。"""
        prev_hash = self.GENESIS
        for rec in self.records:
            # 前後相接的雜湊要對得上，且本筆雜湊要能由內容重新算出來。
            if rec["prev_hash"] != prev_hash or rec["hash"] != _hash(prev_hash, rec["entry"]):
                return False, rec["seq"]
            prev_hash = rec["hash"]
        return True, 0
