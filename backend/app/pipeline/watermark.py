"""装载水位与窗口推进管理。

维护源端抽取水位、装配水位和装载窗口的推进策略。
抽取水位落后时拉链加工不得启动；实际行数与预期行数偏差过大时窗口不得推进。
"""
from __future__ import annotations

from typing import Any


class WatermarkLine:
    """单条水位线：记录所属事实表的水位推进状态。"""

    def __init__(self, table_name: str, loaded_to: str = "", checkpoint: str = ""):
        self.table_name = table_name
        self.loaded_to = loaded_to
        self.checkpoint = checkpoint
        self.dirty_rows: int = 0
        self.expected_rows: int = 0

    def advance(self, new_boundary: str, actual_rows: int, expected_rows: int) -> tuple[bool, str]:
        """推进水位：检查实际行数与预期偏差，偏差超过 20% 时推进失败。"""
        if expected_rows <= 0:
            return False, f"预期行数 {expected_rows} 无效，水位不得推进"
        deviation = abs(actual_rows - expected_rows) / expected_rows
        if deviation > 0.20:
            self.dirty_rows = abs(actual_rows - expected_rows)
            return False, (
                f"实际行数 {actual_rows} 与预期行数 {expected_rows} 偏差 {deviation:.1%}，"
                f"窗口不得推进，脏行数 {self.dirty_rows}"
            )
        self.loaded_to = new_boundary
        self.checkpoint = new_boundary
        self.expected_rows = expected_rows
        return True, f"水位已推进至 {new_boundary}"

    def mark_dirty(self, count: int) -> None:
        self.dirty_rows += count

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "loaded_to": self.loaded_to,
            "checkpoint": self.checkpoint,
            "dirty_rows": self.dirty_rows,
            "expected_rows": self.expected_rows,
        }


class WatermarkManager:
    """管理全部事实表的水位线与抽取水位依赖。"""

    def __init__(self) -> None:
        self._watermarks: dict[str, WatermarkLine] = {}
        self._extract_checkpoints: dict[str, str] = {}

    def register_table(self, table_name: str) -> WatermarkLine:
        if table_name not in self._watermarks:
            self._watermarks[table_name] = WatermarkLine(table_name)
        return self._watermarks[table_name]

    def get_line(self, table_name: str) -> WatermarkLine | None:
        return self._watermarks.get(table_name)

    def register_extract(self, system: str, checkpoint: str) -> None:
        """登记源端抽取确认水位。"""
        self._extract_checkpoints[system] = checkpoint

    def extract_ready(self, system: str, required: str) -> tuple[bool, str]:
        """检查源端抽取水位是否满足拉链加工/事实装配的前置条件。"""
        checkpoint = self._extract_checkpoints.get(system, "")
        if checkpoint < required:
            return False, f"源端抽取水位 {checkpoint} 落后于所需 {required}，拉链加工不得启动"
        return True, f"源端抽取水位 {checkpoint} >= {required}，前置条件满足"

    def advance_load_window(
        self, table_name: str, window_start: str, window_end: str,
        actual_rows: int, expected_rows: int,
    ) -> tuple[bool, str]:
        """推进装载窗口：偏差校验 + 水位更新。"""
        line = self.register_table(table_name)
        ok, msg = line.advance(window_end, actual_rows, expected_rows)
        if ok:
            return True, f"装载窗口 [{window_start}, {window_end}] 已推进，{msg}"
        return False, msg

    def snapshot(self) -> dict[str, Any]:
        return {
            "watermarks": {k: v.to_dict() for k, v in self._watermarks.items()},
            "extract_checkpoints": dict(self._extract_checkpoints),
        }