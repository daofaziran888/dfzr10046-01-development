"""属性失效领域服务：维度属性失效的校验判定与处置，产出失效条目数据集。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class AttrDecayService(BaseModuleService):
    MODULE = "attr_decay"
    ENTITY = "失效条目"
    LIST_FIELDS = ["失效编号", "所属维度", "属性名称", "失效判定", "失效日期", "受影响链数", "处置方式", "最近处置"]
    REQUIRED_FIELDS = ["失效编号", "所属维度", "属性名称"]
    STATUS_ORDER = ["待判定", "判定中", "已处置", "已忽略"]
    ACTION_RULES = {"启动判定": "判定中", "确认处置": "已处置", "忽略条目": "已忽略"}
    NEGATIVE_ACTIONS = []

    def judge_attr_decay(
        self, decay_id: str, dim_name: str, attr_name: str,
        condition: str, decay_date: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """判定属性失效：计算受影响链数量。"""
        scd_rows = store.rows("scd_chain")
        affected = sum(
            1 for r in scd_rows
            if r.get("所属维度") == dim_name
        )

        rows = store.rows(self.MODULE)
        entry = {
            "失效编号": decay_id, "所属维度": dim_name,
            "属性名称": attr_name, "失效判定": condition,
            "失效日期": decay_date, "受影响链数": str(affected),
            "处置方式": "保留原值", "最近处置": decay_date,
            "status": "待判定", "pending": True, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"属性 {attr_name} 失效判定已启动，受影响链数 {affected}", entry

    def resolve_decay(
        self, decay_id: str, resolution: str,
    ) -> tuple[bool, str]:
        """处置属性失效：保留原值或回填默认值。"""
        if resolution not in ("保留原值", "回填默认值"):
            return False, f"处置方式 {resolution} 无效"
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("失效编号") == decay_id:
                r["处置方式"] = resolution
                r["status"] = "已处置"
                r["pending"] = False
                return True, f"属性失效 {decay_id} 已处置：{resolution}"
        return False, f"失效条目 {decay_id} 不存在"