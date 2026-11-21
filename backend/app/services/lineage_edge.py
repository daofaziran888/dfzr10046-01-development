"""血缘关系领域服务：维度、事实与汇总层的血缘边管理。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class LineageEdgeService(BaseModuleService):
    MODULE = "lineage_edge"
    ENTITY = "血缘边"
    LIST_FIELDS = ["血缘编号", "上游对象", "下游对象", "传递方式", "重算触发", "影响层级", "血缘版本", "最近更新"]
    REQUIRED_FIELDS = ["血缘编号", "上游对象", "下游对象"]
    STATUS_ORDER = ["已登记", "待核对", "已核对", "已失效"]
    ACTION_RULES = {"提交核对": "待核对", "确认核对": "已核对", "标记失效": "已失效"}
    NEGATIVE_ACTIONS = []

    def register_edge(
        self, edge_id: str, upstream: str, downstream: str,
        propagation: str, recalc_trigger: str, impact_level: int,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """登记血缘边：上游对象→下游对象的传递方式与重算触发。"""
        rows = store.rows(self.MODULE)
        entry = {
            "血缘编号": edge_id, "上游对象": upstream,
            "下游对象": downstream, "传递方式": propagation,
            "重算触发": recalc_trigger, "影响层级": impact_level,
            "血缘版本": "v1", "最近更新": "2026-11-21",
            "status": "已登记", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"血缘边 {upstream}→{downstream} 已登记", entry

    def propagate_impact(
        self, upstream_id: str, levels: int = 3,
    ) -> list[dict[str, Any]]:
        """沿血缘边向下传递重跑影响范围，多层传播。"""
        rows = store.rows(self.MODULE)
        current = [upstream_id]
        seen = {upstream_id}
        result: list[dict[str, Any]] = []
        for _ in range(levels):
            next_level: list[str] = []
            for up in current:
                for r in rows:
                    if r.get("上游对象") == up and r.get("下游对象") not in seen:
                        down = str(r.get("下游对象", ""))
                        next_level.append(down)
                        seen.add(down)
                        result.append({
                            "upstream": up, "downstream": down,
                            "propagation": r.get("传递方式"),
                            "impact_level": r.get("影响层级"),
                        })
            current = next_level
            if not current:
                break
        return result