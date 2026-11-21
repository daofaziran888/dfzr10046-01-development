"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class FactAssembleService(BaseModuleService):
    MODULE = "fact_assemble"
    ENTITY = "事实批次"
    OPERATION_TERM = "关联"
    LIST_FIELDS = ["批次编号", "所属事实表", "度量列集合", "关联维度数", "装配行数", "外键命中率", "装配水位", "装配耗时"]
    REQUIRED_FIELDS = ["批次编号", "所属事实表", "度量列集合"]
    STATUS_ORDER = ["待装配", "装配中", "已装配", "装配异常"]
    ACTION_RULES = {"启动装配": "装配中", "确认装配": "已装配", "标记异常": "装配异常"}
    NEGATIVE_ACTIONS = []
