"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class MetricBindService(BaseModuleService):
    MODULE = "metric_bind"
    ENTITY = "绑定关系"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["绑定编号", "指标名称", "引用度量", "绑定维度", "统计口径", "时间窗口", "绑定版本", "最近生效"]
    REQUIRED_FIELDS = ["绑定编号", "指标名称", "引用度量"]
    STATUS_ORDER = ["待生效", "生效中", "已替换", "已解除"]
    ACTION_RULES = {"启效绑定": "生效中", "替换绑定": "已替换", "解除绑定": "已解除"}
    NEGATIVE_ACTIONS = []
