"""维度快照生成与发布管理。

核心行为：
- 按快照日期冻结维度全量状态
- 快照与汇总派生依赖绑定，发布版本不得静默替换
- 下游引用数追踪，撤回发布后更新下游状态
"""
from __future__ import annotations

from datetime import date
from typing import Any


class DimSnapshotEntry:
    """维度快照条目。"""

    def __init__(
        self,
        snapshot_id: str,
        dim_name: str,
        snapshot_date: date,
        record_count: int,
        current_chain_ratio: float,
        checksum: str,
        ref_batch: str,
    ):
        self.snapshot_id = snapshot_id
        self.dim_name = dim_name
        self.snapshot_date = snapshot_date
        self.record_count = record_count
        self.current_chain_ratio = current_chain_ratio
        self.checksum = checksum
        self.ref_batch = ref_batch
        self.status = "生成中"
        self.downstream_refs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "dim_name": self.dim_name,
            "snapshot_date": self.snapshot_date.isoformat(),
            "record_count": self.record_count,
            "current_chain_ratio": self.current_chain_ratio,
            "checksum": self.checksum,
            "ref_batch": self.ref_batch,
            "status": self.status,
            "downstream_refs": self.downstream_refs,
        }


class PublishVersion:
    """维度发布版本。"""

    def __init__(
        self,
        publish_id: str,
        dim_name: str,
        version: str,
        snapshot_id: str,
        visible_scope: str,
        publish_date: date,
    ):
        self.publish_id = publish_id
        self.dim_name = dim_name
        self.version = version
        self.snapshot_id = snapshot_id
        self.visible_scope = visible_scope
        self.publish_date = publish_date
        self.status = "待发布"
        self.is_withdrawn = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "publish_id": self.publish_id,
            "dim_name": self.dim_name,
            "version": self.version,
            "snapshot_id": self.snapshot_id,
            "visible_scope": self.visible_scope,
            "publish_date": self.publish_date.isoformat(),
            "status": self.status,
            "is_withdrawn": self.is_withdrawn,
        }


class SnapshotManager:
    """快照与发布管理器。"""

    def __init__(self) -> None:
        self._snapshots: list[DimSnapshotEntry] = []
        self._publishes: list[PublishVersion] = []
        self._dim_row_sources: dict[str, list[dict[str, Any]]] = {}

    def register_dim_data(self, dim_name: str, rows: list[dict[str, Any]]) -> None:
        """注册维度数据来源，供快照冻结时引用。"""
        self._dim_row_sources[dim_name] = rows

    def create_snapshot(
        self, dim_name: str, snapshot_date: date, ref_batch: str
    ) -> tuple[bool, str, DimSnapshotEntry | None]:
        """创建维度快照：冻结当日的全量维度状态。"""
        rows = self._dim_row_sources.get(dim_name, [])
        if not rows:
            return False, f"维度 {dim_name} 无数据，无法生成快照", None

        current_count = sum(1 for r in rows if r.get("is_current"))
        if len(rows) == 0:
            ratio = 0.0
        else:
            ratio = current_count / len(rows)

        import hashlib
        checksum = hashlib.md5(
            str(sorted(r.get("surrogate_key", "") for r in rows)).encode()
        ).hexdigest()[:8]

        snapshot_id = f"SNP-{dim_name[:8]}-{snapshot_date.isoformat()}"
        entry = DimSnapshotEntry(
            snapshot_id=snapshot_id,
            dim_name=dim_name,
            snapshot_date=snapshot_date,
            record_count=len(rows),
            current_chain_ratio=ratio,
            checksum=checksum,
            ref_batch=ref_batch,
        )
        entry.status = "可用"
        self._snapshots.append(entry)
        return True, f"维度 {dim_name} 快照已生成，{len(rows)} 行", entry

    def publish_snapshot(
        self, snapshot_id: str, version: str, visible_scope: str
    ) -> tuple[bool, str, PublishVersion | None]:
        """发布维度快照：绑定依赖批次，发布版本不得静默替换已有发布。"""
        snapshot = None
        for s in self._snapshots:
            if s.snapshot_id == snapshot_id:
                snapshot = s
                break
        if snapshot is None:
            return False, f"快照 {snapshot_id} 不存在", None

        for p in self._publishes:
            if p.snapshot_id == snapshot_id and not p.is_withdrawn:
                return False, (
                    f"快照 {snapshot_id} 已有发布版本 {p.version}，不得静默替换"
                ), None

        pub = PublishVersion(
            publish_id=f"PUB-{snapshot.dim_name[:8]}-{version}",
            dim_name=snapshot.dim_name,
            version=version,
            snapshot_id=snapshot_id,
            visible_scope=visible_scope,
            publish_date=snapshot.snapshot_date,
        )
        pub.status = "已发布"
        self._publishes.append(pub)
        return True, f"维度 {snapshot.dim_name} 版本 {version} 已发布", pub

    def withdraw_publish(self, publish_id: str) -> tuple[bool, str]:
        """撤回发布。"""
        for p in self._publishes:
            if p.publish_id == publish_id:
                if p.is_withdrawn:
                    return False, f"发布 {publish_id} 已撤回"
                p.is_withdrawn = True
                p.status = "已撤回"
                return True, f"发布 {publish_id} 已撤回"
        return False, f"发布 {publish_id} 不存在"

    def get_downstream_count(self, dim_name: str) -> int:
        """计算指定维度的下游引用数量。"""
        return sum(1 for p in self._publishes if p.dim_name == dim_name and not p.is_withdrawn)

    def snapshot(self) -> dict[str, Any]:
        return {
            "snapshots": [s.to_dict() for s in self._snapshots],
            "publishes": [p.to_dict() for p in self._publishes],
        }