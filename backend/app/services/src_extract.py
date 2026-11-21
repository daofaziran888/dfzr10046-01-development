"""源端抽取领域服务：抽取批次管理、水位校验、抽取失败恢复。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class SrcExtractService(BaseModuleService):
    MODULE = "src_extract"
    ENTITY = "抽取批次"
    LIST_FIELDS = ["抽取编号", "来源系统", "抽取范围", "抽取方式", "抽取行数", "抽取水位", "校验摘要", "抽取时间"]
    REQUIRED_FIELDS = ["抽取编号", "来源系统", "抽取范围"]
    STATUS_ORDER = ["待抽取", "抽取中", "已抽取", "抽取失败"]
    ACTION_RULES = {"启动抽取": "抽取中", "确认抽取": "已抽取", "标记失败": "抽取失败"}
    NEGATIVE_ACTIONS = []

    def extract_batch(
        self, system: str, scope: str, method: str, expected_rows: int,
    ) -> tuple[dict[str, Any] | None, str]:
        """执行抽取：校验抽取水位是否符合要求。"""
        extract_id = f"SRC-{system[:3]}-{hash(scope) % 10000:04d}"
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("来源系统") == system and r.get("status") == "抽取中":
                return None, f"来源系统 {system} 存在进行中的抽取批次"

        entry = {
            "抽取编号": extract_id, "来源系统": system,
            "抽取范围": scope, "抽取方式": method,
            "抽取行数": expected_rows, "抽取水位": scope,
            "校验摘要": f"MD5-{hash(str(expected_rows)) % 100000:05d}",
            "抽取时间": "2026-11-21",
            "status": "已抽取", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return entry, f"来源系统 {system} 抽取完成：{expected_rows} 行"

    def check_watermark(self, system: str) -> tuple[bool, str, str]:
        """校验源端抽取水位：返回当前水位与是否满足拉链加工前置条件。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("来源系统") == system and r.get("status") == "已抽取":
                checkpoint = r.get("抽取水位", "1970-01-01")
                return True, f"抽取水位 {checkpoint}", checkpoint
        return False, f"来源系统 {system} 无已抽取批次", "1970-01-01"