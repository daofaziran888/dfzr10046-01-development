"""拉链区间加工引擎：闭链校验、重叠冲突检测、属性失效联动。

核心行为：
- 闭链时校验收敛条件（生效起日 <= 生效止日，链上前序存在且首尾相接）
- 重叠区间冲突检测（容忍首尾相接、不允许多记录重叠同一时间点）
- 属性失效联动：属性失效判定后自动标记受影响链的处置方式
- 区间空窗检测：同维度相邻区间之间的空隙
"""
from __future__ import annotations

from datetime import date
from typing import Any


def _parse_date(d: Any) -> date:
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        return date.fromisoformat(d)
    raise ValueError(f"无法解析日期: {d}")


class ScdRecord:
    """拉链记录的核心字段。"""

    def __init__(
        self,
        record_id: int,
        dim_name: str,
        surrogate_key: str,
        changed_field: str,
        effective_start: date,
        effective_end: date,
        is_current: bool,
        predecessor_id: int | None,
    ):
        self.record_id = record_id
        self.dim_name = dim_name
        self.surrogate_key = surrogate_key
        self.changed_field = changed_field
        self.effective_start = effective_start
        self.effective_end = effective_end
        self.is_current = is_current
        self.predecessor_id = predecessor_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "dim_name": self.dim_name,
            "surrogate_key": self.surrogate_key,
            "changed_field": self.changed_field,
            "effective_start": self.effective_start.isoformat(),
            "effective_end": self.effective_end.isoformat(),
            "is_current": self.is_current,
            "predecessor_id": self.predecessor_id,
        }


class OverlapConflict:
    """区间重叠冲突记录。"""

    def __init__(self, record_a: int, record_b: int, overlap_start: date, overlap_end: date):
        self.record_a = record_a
        self.record_b = record_b
        self.overlap_start = overlap_start
        self.overlap_end = overlap_end

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_a": self.record_a,
            "record_b": self.record_b,
            "overlap_start": self.overlap_start.isoformat(),
            "overlap_end": self.overlap_end.isoformat(),
        }


class ScdProcessor:
    """拉链加工处理器。"""

    def __init__(self) -> None:
        self._records: dict[str, list[ScdRecord]] = {}

    def add_record(self, record: ScdRecord) -> None:
        self._records.setdefault(record.dim_name, []).append(record)

    def close_chain(
        self, record_id: int, end_date: date, predecessor_id: int | None = None
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """闭链记录：设定生效止日并收敛前置检查。"""
        found: ScdRecord | None = None
        for records in self._records.values():
            for rec in records:
                if rec.record_id == record_id:
                    found = rec
                    break
            if found:
                break
        if found is None:
            return False, f"拉链记录 {record_id} 不存在", None

        if end_date < found.effective_start:
            return False, (
                f"闭链失败：生效止日 {end_date} 早于生效起日 {found.effective_start}"
            ), None

        if predecessor_id is not None:
            pred = None
            for records in self._records.values():
                for rec in records:
                    if rec.record_id == predecessor_id:
                        pred = rec
                        break
                if pred:
                    break
            if pred is None:
                return False, f"链上前序 {predecessor_id} 不存在", None
            if pred.effective_end != found.effective_start:
                return False, (
                    f"前序区间止日 {pred.effective_end} 与当前起日 {found.effective_start} "
                    f"不首尾相接"
                ), None
            found.predecessor_id = predecessor_id

        found.effective_end = end_date
        found.is_current = False
        return True, f"拉链记录 {record_id} 已闭链，止日 {end_date}", found.to_dict()

    def detect_overlap(
        self, dim_name: str
    ) -> tuple[list[OverlapConflict], str]:
        """检测同一维度下各链区间的重叠冲突。

        规则：
        - 首尾相接不视作冲突（record_a.end == record_b.start）
        - 任何内点重叠（[s1,e1] 与 [s2,e2] 的交集长度 > 0）视为冲突
        """
        records = sorted(self._records.get(dim_name, []), key=lambda r: r.effective_start)
        if len(records) < 2:
            return [], "无重叠检测：记录数不足 2 条"

        conflicts: list[OverlapConflict] = []
        for i, a in enumerate(records):
            for b in records[i + 1:]:
                if a.effective_end > b.effective_start and a.effective_start < b.effective_end:
                    overlap_start = max(a.effective_start, b.effective_start)
                    overlap_end = min(a.effective_end, b.effective_end)
                    if overlap_start < overlap_end:
                        conflicts.append(
                            OverlapConflict(a.record_id, b.record_id, overlap_start, overlap_end)
                        )
        if conflicts:
            return conflicts, (
                f"维度 {dim_name} 检测到 {len(conflicts)} 处区间重叠冲突"
            )
        return [], f"维度 {dim_name} 区间无重叠冲突"

    def detect_gaps(self, dim_name: str) -> list[tuple[date, date]]:
        """检测区间空窗：相邻记录之间未覆盖的日期范围。"""
        records = sorted(self._records.get(dim_name, []), key=lambda r: r.effective_start)
        gaps: list[tuple[date, date]] = []
        for i in range(len(records) - 1):
            if records[i].effective_end < records[i + 1].effective_start:
                gaps.append((records[i].effective_end, records[i + 1].effective_start))
        return gaps

    def apply_attr_decay(
        self, dim_name: str, attr_name: str, default_value: str
    ) -> int:
        """属性失效联动：将指定维度属性失效后回填默认值。

        返回受影响的链记录数量。
        """
        count = 0
        for rec in self._records.get(dim_name, []):
            rec.changed_field = f"{attr_name}→{default_value}（已失效）"
            count += 1
        return count

    def get_dim_records(self, dim_name: str) -> list[ScdRecord]:
        return self._records.get(dim_name, [])

    def snapshot(self) -> dict[str, Any]:
        return {
            dim: [r.to_dict() for r in recs]
            for dim, recs in self._records.items()
        }