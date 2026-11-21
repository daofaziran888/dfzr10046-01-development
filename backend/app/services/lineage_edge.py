"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class LineageEdgeService(BaseModuleService):
    MODULE = "lineage_edge"
    ENTITY = "血缘边"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["血缘编号", "上游对象", "下游对象", "传递方式", "重算触发", "影响层级", "血缘版本", "最近更新"]
    REQUIRED_FIELDS = ["血缘编号", "上游对象", "下游对象"]
    STATUS_ORDER = ["已登记", "待核对", "已核对", "已失效"]
    ACTION_RULES = {"提交核对": "待核对", "确认核对": "已核对", "标记失效": "已失效"}
    NEGATIVE_ACTIONS = []
