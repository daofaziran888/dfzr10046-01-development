"""迟到事实领域服务：登记校验晚到数据的回补水位，产出迟到记录数据集。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class LateFactService(BaseModuleService):
    MODULE = "late_fact"
    ENTITY = "迟到记录"
    LIST_FIELDS = ["记录编号", "所属事实表", "业务发生日", "到达日", "滞后天数", "受影响分区", "回补结论", "登记时间"]
    REQUIRED_FIELDS = ["记录编号", "所属事实表", "业务发生日"]
    STATUS_ORDER = ["已登记", "待回补", "已回补", "拒绝回补"]
    ACTION_RULES = {"提交回补": "待回补", "确认回补": "已回补", "拒绝记录": "拒绝回补"}
    NEGATIVE_ACTIONS = ["拒绝记录"]

    def register_late_fact(
        self, record_id: str, fact_table: str, business_date: str,
        arrival_date: str, affected_partition: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """登记迟到事实：计算滞后天数，回补结论默认待回补。"""
        try:
            bd = date.fromisoformat(business_date)
            ad = date.fromisoformat(arrival_date)
        except ValueError:
            return False, "日期格式无效", None
        lag = (ad - bd).days
        if lag <= 0:
            return False, f"迟到天数 {lag} <= 0，不视为迟到事实", None

        entry = {
            "记录编号": record_id, "所属事实表": fact_table,
            "业务发生日": business_date, "到达日": arrival_date,
            "滞后天数": lag, "受影响分区": affected_partition,
            "回补结论": "待回补", "登记时间": arrival_date,
            "status": "待回补", "pending": True, "abnormal": False,
        }
        rows = store.rows(self.MODULE)
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"迟到事实 {record_id} 已登记，滞后 {lag} 天", entry

    def decide_backfill(
        self, record_id: str, loaded_watermark: str, strategy: str,
    ) -> tuple[bool, str]:
        """判定回补方式：整段重算或增量追加。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("记录编号") == record_id:
                lag = int(r.get("滞后天数", 0))
                if lag > 30:
                    r["回补结论"] = "整段重算"
                else:
                    r["回补结论"] = "增量追加"
                r["status"] = "已回补"
                r["pending"] = False
                return True, f"迟到事实 {record_id} 回补结论：{r['回补结论']}"
        return False, f"迟到记录 {record_id} 不存在"