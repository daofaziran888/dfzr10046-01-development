"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DimEntryService(BaseModuleService):
    MODULE = "dim_entry"
    ENTITY = "维度条目"
    OPERATION_TERM = "合并"
    LIST_FIELDS = ["维度编号", "维度名称", "业务主键", "自然键来源", "维度类型", "所属主题域", "生效标记", "登记时间"]
    REQUIRED_FIELDS = ["维度编号", "维度名称", "业务主键"]
    STATUS_ORDER = ["待注册", "已注册", "已合并", "已废弃"]
    ACTION_RULES = {"确认注册": "已注册", "合并维度": "已合并", "废弃维度": "已废弃"}
    NEGATIVE_ACTIONS = []
