"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class LateFactService(BaseModuleService):
    MODULE = "late_fact"
    ENTITY = "迟到记录"
    OPERATION_TERM = "水位"
    LIST_FIELDS = ["记录编号", "所属事实表", "业务发生日", "到达日", "滞后天数", "受影响分区", "回补结论", "登记时间"]
    REQUIRED_FIELDS = ["记录编号", "所属事实表", "业务发生日"]
    STATUS_ORDER = ["已登记", "待回补", "已回补", "拒绝回补"]
    ACTION_RULES = {"提交回补": "待回补", "确认回补": "已回补", "拒绝记录": "拒绝回补"}
    NEGATIVE_ACTIONS = ["拒绝记录"]
