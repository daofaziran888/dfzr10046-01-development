"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ReprocessTaskService(BaseModuleService):
    MODULE = "reprocess_task"
    ENTITY = "重跑任务"
    OPERATION_TERM = "水位"
    LIST_FIELDS = ["重跑编号", "触发原因", "影响事实表", "重跑区间", "覆盖策略", "依赖批次", "重跑水位", "重跑耗时"]
    REQUIRED_FIELDS = ["重跑编号", "触发原因", "影响事实表"]
    STATUS_ORDER = ["待排期", "重跑中", "已完成", "重跑失败"]
    ACTION_RULES = {"排期重跑": "重跑中", "确认完成": "已完成", "标记失败": "重跑失败"}
    NEGATIVE_ACTIONS = []
