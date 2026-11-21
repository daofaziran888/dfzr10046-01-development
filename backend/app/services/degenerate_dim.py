"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DegenerateDimService(BaseModuleService):
    MODULE = "degenerate_dim"
    ENTITY = "退化维条目"
    OPERATION_TERM = "聚合"
    LIST_FIELDS = ["条目编号", "所属事实表", "退化字段", "来源单据类型", "去重基数", "是否参与聚合", "生效版本", "最近核对"]
    REQUIRED_FIELDS = ["条目编号", "所属事实表", "退化字段"]
    STATUS_ORDER = ["草稿", "已生效", "已停用", "核对不符"]
    ACTION_RULES = {"生效条目": "已生效", "停用条目": "已停用", "登记不符": "核对不符"}
    NEGATIVE_ACTIONS = ["停用条目"]
