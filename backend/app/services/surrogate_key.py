"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class SurrogateKeyService(BaseModuleService):
    MODULE = "surrogate_key"
    ENTITY = "代理键段"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["键段编号", "所属维度", "键段起点", "键段终点", "已分配数量", "回收标记", "分配策略", "最近分配"]
    REQUIRED_FIELDS = ["键段编号", "所属维度", "键段起点"]
    STATUS_ORDER = ["待分配", "分配中", "已耗尽", "已回收"]
    ACTION_RULES = {"启动分配": "分配中", "标记耗尽": "已耗尽", "回收键段": "已回收"}
    NEGATIVE_ACTIONS = []
