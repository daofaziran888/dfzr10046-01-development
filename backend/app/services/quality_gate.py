"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class QualityGateService(BaseModuleService):
    MODULE = "quality_gate"
    ENTITY = "质量闸条目"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["闸口编号", "所属事实表", "校验项", "阈值声明", "实测读数", "通过判定", "阻断范围", "最近执行"]
    REQUIRED_FIELDS = ["闸口编号", "所属事实表", "校验项"]
    STATUS_ORDER = ["待执行", "执行中", "已放行", "已阻断"]
    ACTION_RULES = {"执行校验": "执行中", "放行批次": "已放行", "阻断批次": "已阻断"}
    NEGATIVE_ACTIONS = []
