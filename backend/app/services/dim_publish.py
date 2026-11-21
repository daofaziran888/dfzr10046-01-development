"""维度发布领域服务：版本化发布维度快照给下游。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class DimPublishService(BaseModuleService):
    MODULE = "dim_publish"
    ENTITY = "发布版本"
    LIST_FIELDS = ["发布编号", "所属维度", "发布版本", "快照日期", "可见范围", "下游引用数", "发布标签", "发布时间"]
    REQUIRED_FIELDS = ["发布编号", "所属维度", "发布版本"]
    STATUS_ORDER = ["待发布", "发布中", "已发布", "已撤回"]
    ACTION_RULES = {"启动发布": "发布中", "确认发布": "已发布", "撤回发布": "已撤回"}
    NEGATIVE_ACTIONS = []

    def publish_version(
        self, publish_id: str, dim_name: str, version: str,
        snapshot_date: str, visible_scope: str, label: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """发布维度版本：绑定快照日期与可见范围。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("所属维度") == dim_name and r.get("发布版本") == version \
                    and r.get("status") == "已发布":
                return False, (
                    f"维度 {dim_name} 版本 {version} 已有发布记录，不得静默替换"
                ), None

        entry = {
            "发布编号": publish_id, "所属维度": dim_name,
            "发布版本": version, "快照日期": snapshot_date,
            "可见范围": visible_scope, "下游引用数": "0",
            "发布标签": label, "发布时间": "2026-11-21",
            "status": "已发布", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"维度 {dim_name} 版本 {version} 已发布", entry

    def withdraw_publish(self, publish_id: str) -> tuple[bool, str]:
        """撤回发布：更新已撤回状态。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("发布编号") == publish_id:
                if r.get("status") == "已撤回":
                    return False, f"发布 {publish_id} 已撤回"
                r["status"] = "已撤回"
                r["pending"] = False
                return True, f"发布 {publish_id} 已撤回"
        return False, f"发布 {publish_id} 不存在"

    def count_downstream_refs(self, dim_name: str) -> int:
        """统计下游引用数。"""
        rows = store.rows(self.MODULE)
        return sum(1 for r in rows if r.get("所属维度") == dim_name and r.get("status") == "已发布")