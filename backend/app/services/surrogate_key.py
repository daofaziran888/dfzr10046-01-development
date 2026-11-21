"""代理键生成领域服务：键段分配与耗尽标记，校验回收策略，产出键段分配表数据集。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class SurrogateKeyService(BaseModuleService):
    MODULE = "surrogate_key"
    ENTITY = "代理键段"
    LIST_FIELDS = ["键段编号", "所属维度", "键段起点", "键段终点", "已分配数量", "回收标记", "分配策略", "最近分配"]
    REQUIRED_FIELDS = ["键段编号", "所属维度", "键段起点"]
    STATUS_ORDER = ["待分配", "分配中", "已耗尽", "已回收"]
    ACTION_RULES = {"启动分配": "分配中", "标记耗尽": "已耗尽", "回收键段": "已回收"}
    NEGATIVE_ACTIONS = []

    def allocate_key(self, dim_name: str, natural_key: str) -> tuple[int | None, str]:
        """为自然键分配代理键：从键段中取出下一个可用键值。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("所属维度") == dim_name and r.get("status") in ("待分配", "分配中"):
                allocated = int(r.get("已分配数量", 0)) + 1
                r["已分配数量"] = allocated
                start = int(r.get("键段起点", 1))
                new_key = start + allocated - 1
                r["最近分配"] = str(allocated)
                if allocated >= int(r.get("键段终点", start + 100)):
                    r["status"] = "已耗尽"
                    r["pending"] = False
                r["status"] = r["status"] or "分配中"
                return new_key, f"自然键 {natural_key} 分配代理键 {new_key}"
        return None, f"维度 {dim_name} 无可用键段"

    def query_key_range(self, dim_name: str) -> dict[str, Any]:
        """查询维度的当前键段状态。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("所属维度") == dim_name:
                return {
                    "dim_name": dim_name,
                    "key_range_start": r.get("键段起点"),
                    "key_range_end": r.get("键段终点"),
                    "allocated": r.get("已分配数量", 0),
                    "remaining": int(r.get("键段终点", 0)) - int(r.get("已分配数量", 0)),
                    "strategy": r.get("分配策略", ""),
                }
        return {"dim_name": dim_name, "status": "未分配"}

    def reuse_policy(self, dim_name: str, natural_key: str) -> tuple[int | None, str]:
        """复用策略：同一自然键多次变更时，是否复用旧代理键。"""
        existing = self.query_key_range(dim_name)
        policy = existing.get("strategy", "")
        if policy == "REUSE":
            return existing.get("key_range_start", 1), f"复用旧代理键"
        return self.allocate_key(dim_name, natural_key)