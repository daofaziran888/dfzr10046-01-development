"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class GrainDeclareService(BaseModuleService):
    MODULE = "grain_declare"
    ENTITY = "粒度声明"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["声明编号", "所属事实表", "一行代表", "维度组合", "度量可加性", "重复判定键", "声明版本", "最近核对"]
    REQUIRED_FIELDS = ["声明编号", "所属事实表", "一行代表"]
    STATUS_ORDER = ["草稿", "已声明", "待修订", "已作废"]
    ACTION_RULES = {"确认声明": "已声明", "提交修订": "待修订", "作废声明": "已作废"}
    NEGATIVE_ACTIONS = ["作废声明"]
