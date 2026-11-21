"""多值桥接领域服务：事实与多值维度桥接的权重归一校验管理，产出桥接条目数据集。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class BridgeLinkService(BaseModuleService):
    MODULE = "bridge_link"
    ENTITY = "桥接条目"
    LIST_FIELDS = ["桥接编号", "所属事实表", "关联维度", "权重比例", "桥接行数", "归一校验", "桥接版本", "最近装配"]
    REQUIRED_FIELDS = ["桥接编号", "所属事实表", "关联维度"]
    STATUS_ORDER = ["待装配", "已装配", "归一失败", "已作废"]
    ACTION_RULES = {"启动装配": "已装配", "登记归一失败": "归一失败", "作废条目": "已作废"}
    NEGATIVE_ACTIONS = ["登记归一失败"]

    def register_bridge(
        self, bridge_id: str, fact_table: str, dim_name: str,
        weight_ratio: float, row_count: int, version: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """登记桥接条目：含权重比例，后续归一校验。"""
        rows = store.rows(self.MODULE)
        entry = {
            "桥接编号": bridge_id, "所属事实表": fact_table,
            "关联维度": dim_name, "权重比例": str(weight_ratio),
            "桥接行数": row_count, "归一校验": "待校验",
            "桥接版本": version, "最近装配": "2026-11-21",
            "status": "待装配", "pending": True, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"桥接 {bridge_id} 已登记：{fact_table}→{dim_name} 权重 {weight_ratio}", entry

    def check_normalization(
        self, fact_table: str, row_weights: dict[int, float],
    ) -> tuple[bool, str, dict[str, Any]]:
        """归一校验：同一事实行关联的维度权重之和必须为1。归一失败时装配结果度量会被重复放大。"""
        failures: dict[int, float] = {}
        for row_id, total in row_weights.items():
            if abs(total - 1.0) > 0.001:
                failures[row_id] = total
        if failures:
            # 标记对应桥接条目为归一失败
            rows = store.rows(self.MODULE)
            for r in rows:
                if r.get("所属事实表") == fact_table:
                    r["归一校验"] = "失败"
                    r["status"] = "归一失败"
                    r["abnormal"] = True
            detail = ", ".join(f"行{k}={v:.3f}" for k, v in failures.items())
            return False, f"归一失败：{detail}", {"failures": failures}
        return True, f"全部桥接权重归一通过", {"ok": True}