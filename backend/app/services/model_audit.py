"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ModelAuditService(BaseModuleService):
    MODULE = "model_audit"
    ENTITY = "审计条目"
    OPERATION_TERM = "合并"
    LIST_FIELDS = ["条目编号", "操作类型", "操作对象", "变更前值", "变更后值", "影响下游数", "操作者标识", "操作时间"]
    REQUIRED_FIELDS = ["条目编号", "操作类型", "操作对象"]
    STATUS_ORDER = ["已记录", "待核查", "已核查", "已封存"]
    ACTION_RULES = {"提交核查": "待核查", "完成核查": "已核查", "封存条目": "已封存"}
    NEGATIVE_ACTIONS = []
