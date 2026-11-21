"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class SummaryLayerService(BaseModuleService):
    MODULE = "summary_layer"
    ENTITY = "汇总条目"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["汇总编号", "来源事实表", "汇总粒度", "度量表达式", "派生行数", "依赖批次", "刷新方式", "派生时间"]
    REQUIRED_FIELDS = ["汇总编号", "来源事实表", "汇总粒度"]
    STATUS_ORDER = ["待派生", "派生中", "已派生", "派生失败"]
    ACTION_RULES = {"启动派生": "派生中", "确认派生": "已派生", "标记失败": "派生失败"}
    NEGATIVE_ACTIONS = []
