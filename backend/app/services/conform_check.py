"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ConformCheckService(BaseModuleService):
    MODULE = "conform_check"
    ENTITY = "核对条目"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["核对编号", "基准维度", "对照维度", "核对粒度", "匹配键数", "不匹配键数", "核对结论", "核对时间"]
    REQUIRED_FIELDS = ["核对编号", "基准维度", "对照维度"]
    STATUS_ORDER = ["待核对", "核对中", "已一致", "存在偏差"]
    ACTION_RULES = {"启动核对": "核对中", "确认一致": "已一致", "登记偏差": "存在偏差"}
    NEGATIVE_ACTIONS = []
