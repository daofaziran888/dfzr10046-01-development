"""重跑任务编排器：覆盖策略、血缘传递、迟到事实回补边界。

核心行为：
- 因迟到事实/维度修订/口径变更触发的重跑任务
- 覆盖策略："整段替换"（旧批次被新批次替换）、"并存留痕"（保留旧批次+追加新批次）
- 血缘传递：重跑影响范围沿血缘边逐层向下传播
- 迟到事实回补边界判定：业务发生日早于已装配水位的记录，判定是否整段重算还是增量追加
"""
from __future__ import annotations

from datetime import date
from typing import Any


class ReprocessTask:
    """重跑任务定义。"""

    def __init__(
        self,
        task_id: str,
        reason: str,
        target_table: str,
        reprocess_start: date,
        reprocess_end: date,
        strategy: str,
        dependency_batch: str,
    ):
        self.task_id = task_id
        self.reason = reason
        self.target_table = target_table
        self.reprocess_start = reprocess_start
        self.reprocess_end = reprocess_end
        self.strategy = strategy
        self.dependency_batch = dependency_batch
        self.status = "待排期"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "reason": self.reason,
            "target_table": self.target_table,
            "reprocess_start": self.reprocess_start.isoformat(),
            "reprocess_end": self.reprocess_end.isoformat(),
            "strategy": self.strategy,
            "dependency_batch": self.dependency_batch,
            "status": self.status,
        }


class LineageEdge:
    """血缘边：上游对象 → 下游对象。"""

    def __init__(self, edge_id: str, upstream: str, downstream: str, propagation: str):
        self.edge_id = edge_id
        self.upstream = upstream
        self.downstream = downstream
        self.propagation = propagation

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "upstream": self.upstream,
            "downstream": self.downstream,
            "propagation": self.propagation,
        }


class LateFactRecord:
    """迟到事实记录。"""

    def __init__(
        self,
        record_id: str,
        fact_table: str,
        business_date: date,
        arrival_date: date,
        affected_partition: str,
    ):
        self.record_id = record_id
        self.fact_table = fact_table
        self.business_date = business_date
        self.arrival_date = arrival_date
        self.affected_partition = affected_partition
        self.lag_days = (arrival_date - business_date).days

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "fact_table": self.fact_table,
            "business_date": self.business_date.isoformat(),
            "arrival_date": self.arrival_date.isoformat(),
            "lag_days": self.lag_days,
            "affected_partition": self.affected_partition,
        }


class ReprocessOrchestrator:
    """重跑编排器。"""

    def __init__(self) -> None:
        self._tasks: list[ReprocessTask] = []
        self._lineage: list[LineageEdge] = []
        self._late_records: list[LateFactRecord] = []
        self._watermark_cutoff: dict[str, date] = {}

    def set_watermark_cutoff(self, table: str, cutoff: date) -> None:
        """设定装配水位截止日期。"""
        self._watermark_cutoff[table] = cutoff

    def register_late_fact(self, record: LateFactRecord) -> str:
        """登记迟到事实：判定回补结论。"""
        cutoff = self._watermark_cutoff.get(record.fact_table)
        if cutoff is None:
            return "拒绝回补"
        if record.business_date < cutoff:
            self._late_records.append(record)
            return "待回补"
        return "拒绝回补"

    def add_edge(self, edge: LineageEdge) -> None:
        self._lineage.append(edge)

    def propagate_impact(self, target_table: str) -> list[str]:
        """血缘影响传播：沿血缘边找到以 target_table 为上游的全部下游对象。"""
        direct = [
            e.downstream for e in self._lineage
            if e.upstream == target_table
        ]
        result = list(direct)
        seen = set(direct)
        for downstream in direct:
            deeper = self.propagate_impact(downstream)
            for d in deeper:
                if d not in seen:
                    seen.add(d)
                    result.append(d)
        return result

    def create_reprocess(
        self, task: ReprocessTask
    ) -> tuple[bool, str]:
        """创建重跑任务。覆盖策略决定旧区间被替换还是并存留痕。"""
        if task.strategy not in ("整段替换", "并存留痕"):
            return False, f"覆盖策略「{task.strategy}」无效，仅支持「整段替换」或「并存留痕」"
        if task.reprocess_end <= task.reprocess_start:
            return False, f"重跑区间结束日 {task.reprocess_end} 不晚于开始日 {task.reprocess_start}"
        self._tasks.append(task)
        impacted = self.propagate_impact(task.target_table)
        return True, (
            f"重跑任务 {task.task_id} 已创建，策略：{task.strategy}，"
            f"影响下游 {len(impacted)} 个对象"
        )

    def decide_backfill_boundary(
        self, late: LateFactRecord, loaded_watermark: date
    ) -> str:
        """判定迟到事实的回补边界：整段重算还是增量追加。"""
        if late.lag_days > 30:
            return "整段重算"
        if late.business_date < loaded_watermark:
            return "增量追加"
        return "拒绝回补"

    def snapshot(self) -> dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self._tasks],
            "lineage_edges": [l.to_dict() for l in self._lineage],
            "late_records": [r.to_dict() for r in self._late_records],
        }