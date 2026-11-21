"""装配质量闸领域服务：阈值校验与阻断放行决策，校验命中率导入导出规则，产出质量闸条目数据集。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class QualityGateService(BaseModuleService):
    MODULE = "quality_gate"
    ENTITY = "质量闸条目"
    LIST_FIELDS = ["闸口编号", "所属事实表", "校验项", "阈值声明", "实测读数", "通过判定", "阻断范围", "最近执行"]
    REQUIRED_FIELDS = ["闸口编号", "所属事实表", "校验项"]
    STATUS_ORDER = ["待执行", "执行中", "已放行", "已阻断"]
    ACTION_RULES = {"执行校验": "执行中", "放行批次": "已放行", "阻断批次": "已阻断"}
    NEGATIVE_ACTIONS = []

    def evaluate_gate(
        self, gate_id: str, fact_table: str, check_item: str,
        threshold: float, measured: float, block_scope: str,
    ) -> tuple[bool, str, dict[str, Any]]:
        """执行质量闸校验：实测读数越界时按阻断范围拦下批次。"""
        passed = measured >= threshold
        status = "已放行" if passed else "已阻断"

        entry = {
            "闸口编号": gate_id, "所属事实表": fact_table,
            "校验项": check_item, "阈值声明": str(threshold),
            "实测读数": str(measured), "通过判定": "是" if passed else "否",
            "阻断范围": block_scope if not passed else "",
            "最近执行": "2026-11-21",
            "status": status, "pending": False,
            "abnormal": not passed,
        }
        rows = store.rows(self.MODULE)
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)

        if passed:
            return True, f"质量闸 {gate_id} 放行：{check_item}={measured} >= 阈值{threshold}", entry
        return False, (
            f"质量闸 {gate_id} 阻断：{check_item}={measured} < 阈值{threshold}，阻断范围 {block_scope}"
        ), entry

    def check_fact_readiness(self, fact_table: str) -> tuple[bool, str]:
        """检查事实表是否有阻断中的质量闸。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("所属事实表") == fact_table and r.get("status") == "已阻断":
                return False, f"事实表 {fact_table} 存在阻断的质量闸"
        return True, f"事实表 {fact_table} 质量闸全部放行"