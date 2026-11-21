"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class DimSnapshotService(BaseModuleService):
    MODULE = "dim_snapshot"
    ENTITY = "快照版本"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["快照编号", "所属维度", "快照日期", "维度行数", "当前链占比", "快照摘要值", "引用批次", "生成时间"]
    REQUIRED_FIELDS = ["快照编号", "所属维度", "快照日期"]
    STATUS_ORDER = ["生成中", "可用", "已过期", "已重建"]
    ACTION_RULES = {"标记可用": "可用", "标记过期": "已过期", "重建快照": "已重建"}
    NEGATIVE_ACTIONS = []
