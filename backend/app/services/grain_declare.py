"""粒度声明领域服务：声明事实表业务粒度和度量可加性。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class GrainDeclareService(BaseModuleService):
    MODULE = "grain_declare"
    ENTITY = "粒度声明"
    LIST_FIELDS = ["声明编号", "所属事实表", "一行代表", "维度组合", "度量可加性", "重复判定键", "声明版本", "最近核对"]
    REQUIRED_FIELDS = ["声明编号", "所属事实表", "一行代表"]
    STATUS_ORDER = ["草稿", "已声明", "待修订", "已作废"]
    ACTION_RULES = {"确认声明": "已声明", "提交修订": "待修订", "作废声明": "已作废"}
    NEGATIVE_ACTIONS = []

    def declare_grain(
        self, declare_id: str, fact_table: str, one_row_means: str,
        dim_combo: str, additivity: str, dedup_key: str, version: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """声明事实表粒度：一行代表 + 维度组合 + 度量可加性。"""
        rows = store.rows(self.MODULE)
        entry = {
            "声明编号": declare_id, "所属事实表": fact_table,
            "一行代表": one_row_means, "维度组合": dim_combo,
            "度量可加性": additivity, "重复判定键": dedup_key,
            "声明版本": version, "最近核对": "2026-11-21",
            "status": "已声明", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"粒度声明 {declare_id} 已生效：{one_row_means}", entry

    def revise_grain(self, declare_id: str, new_dims: str) -> tuple[bool, str]:
        """修订粒度声明：触发汇总层重算与下游引用更新。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("声明编号") == declare_id:
                r["status"] = "待修订"
                r["维度组合"] = new_dims
                r["pending"] = True
                return True, f"粒度声明 {declare_id} 已提交修订：{new_dims}"
        return False, f"粒度声明 {declare_id} 不存在"