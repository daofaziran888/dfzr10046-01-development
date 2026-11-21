"""建模审计领域服务：记录维度建模变更前后的值与影响下游数量。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class ModelAuditService(BaseModuleService):
    MODULE = "model_audit"
    ENTITY = "审计条目"
    LIST_FIELDS = ["条目编号", "操作类型", "操作对象", "变更前值", "变更后值", "影响下游数", "操作者标识", "操作时间"]
    REQUIRED_FIELDS = ["条目编号", "操作类型", "操作对象"]
    STATUS_ORDER = ["已记录", "待核查", "已核查", "已封存"]
    ACTION_RULES = {"提交核查": "待核查", "完成核查": "已核查", "封存条目": "已封存"}
    NEGATIVE_ACTIONS = []

    def record_audit(
        self, audit_id: str, operation: str, target: str,
        before_value: str, after_value: str, downstream_count: int,
        operator_id: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """记录建模变更审计：含变更前后值与影响下游数量。"""
        rows = store.rows(self.MODULE)
        entry = {
            "条目编号": audit_id, "操作类型": operation,
            "操作对象": target, "变更前值": before_value,
            "变更后值": after_value, "影响下游数": downstream_count,
            "操作者标识": operator_id, "操作时间": "2026-11-21",
            "status": "已记录", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"审计记录 {audit_id}：{operation} {target}", entry

    def check_audit_trail(
        self, target: str, since: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询目标对象的审计轨迹。"""
        rows = store.rows(self.MODULE)
        result = [dict(r) for r in rows if r.get("操作对象") == target]
        if since:
            result = [r for r in result if str(r.get("操作时间", "")) >= since]
        return result

    def seal_audit(self, target: str) -> int:
        """封存审计记录：标记已封存状态。"""
        rows = store.rows(self.MODULE)
        count = 0
        for r in rows:
            if r.get("操作对象") == target and r.get("status") != "已封存":
                r["status"] = "已封存"
                count += 1
        return count