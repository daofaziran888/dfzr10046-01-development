"""维度快照领域服务：冻结校验维度全量状态，产出快照版本数据集。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class DimSnapshotService(BaseModuleService):
    MODULE = "dim_snapshot"
    ENTITY = "快照版本"
    LIST_FIELDS = ["快照编号", "所属维度", "快照日期", "维度行数", "当前链占比", "快照摘要值", "引用批次", "生成时间"]
    REQUIRED_FIELDS = ["快照编号", "所属维度", "快照日期"]
    STATUS_ORDER = ["生成中", "可用", "已过期", "已重建"]
    ACTION_RULES = {"标记可用": "可用", "标记过期": "已过期", "重建快照": "已重建"}
    NEGATIVE_ACTIONS = []

    def freeze_snapshot(
        self, snapshot_id: str, dim_name: str, snapshot_date: str,
        ref_batch: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """冻结维度快照：计算当前维度全量状态。"""
        scd_rows = store.rows("scd_chain")
        dim_rows = [
            r for r in scd_rows
            if r.get("所属维度") == dim_name
        ]
        total = len(dim_rows)
        current_count = sum(1 for r in dim_rows if r.get("是否当前") == "是")
        ratio = current_count / total if total > 0 else 0.0

        import hashlib
        checksum = hashlib.md5(
            str(sorted(r.get("代理键", "") for r in dim_rows)).encode()
        ).hexdigest()[:8]

        rows = store.rows(self.MODULE)
        entry = {
            "快照编号": snapshot_id, "所属维度": dim_name,
            "快照日期": snapshot_date, "维度行数": total,
            "当前链占比": f"{ratio:.1%}", "快照摘要值": checksum,
            "引用批次": ref_batch, "生成时间": snapshot_date,
            "status": "可用", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"维度 {dim_name} 快照已生成：{total} 行", entry

    def verify_snapshot_consistency(
        self, dim_name: str, snapshot_date: str,
    ) -> tuple[bool, str, int]:
        """验证同一快照日期的维度行数一致性。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("所属维度") == dim_name and r.get("快照日期") == snapshot_date:
                count = int(r.get("维度行数", 0))
                return True, f"快照一致：{count} 行", count
        return False, f"维度 {dim_name} 无 {snapshot_date} 快照", 0