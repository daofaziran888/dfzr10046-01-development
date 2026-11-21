"""装载窗口领域服务：装载区间管理、偏差检测、中断恢复。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class LoadWindowService(BaseModuleService):
    MODULE = "load_window"
    ENTITY = "装载窗口"
    LIST_FIELDS = ["窗口编号", "所属事实表", "窗口起点", "窗口终点", "预期行数", "实际行数", "装载水位", "装载耗时"]
    REQUIRED_FIELDS = ["窗口编号", "所属事实表", "窗口起点"]
    STATUS_ORDER = ["待装载", "装载中", "已装载", "装载中断"]
    ACTION_RULES = {"启动装载": "装载中", "确认装载": "已装载", "标记中断": "装载中断"}
    NEGATIVE_ACTIONS = ["标记中断"]

    def advance_window(
        self, window_id: str, fact_table: str, start: str, end: str,
        expected_rows: int, actual_rows: int,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """推进装载窗口：实际行数与预期行数偏差超过 20% 时窗口不得推进。"""
        if expected_rows <= 0:
            return False, f"预期行数 {expected_rows} 无效", None

        deviation = abs(actual_rows - expected_rows) / expected_rows
        if deviation > 0.20:
            rows = store.rows(self.MODULE)
            entry = {
                "窗口编号": window_id, "所属事实表": fact_table,
                "窗口起点": start, "窗口终点": end,
                "预期行数": expected_rows, "实际行数": actual_rows,
                "装载水位": start, "装载耗时": "",
                "status": "装载中断", "pending": False, "abnormal": True,
                "偏差率": f"{deviation:.1%}",
            }
            entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
            rows.append(entry)
            return False, (
                f"实际行数 {actual_rows} 与预期 {expected_rows} 偏差 {deviation:.1%}，窗口不得推进"
            ), entry

        rows = store.rows(self.MODULE)
        entry = {
            "窗口编号": window_id, "所属事实表": fact_table,
            "窗口起点": start, "窗口终点": end,
            "预期行数": expected_rows, "实际行数": actual_rows,
            "装载水位": end, "装载耗时": "1.5s",
            "status": "已装载", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"装载窗口 [{start}, {end}] 已推进，水位 {end}", entry

    def detect_dirty_window(self, fact_table: str) -> list[dict[str, Any]]:
        """检测脏数据窗口：偏差超阈值或中断的窗口。"""
        rows = store.rows(self.MODULE)
        return [dict(r) for r in rows if r.get("所属事实表") == fact_table
                and (r.get("status") == "装载中断" or r.get("abnormal"))]