"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class AttrDecayService(BaseModuleService):
    MODULE = "attr_decay"
    ENTITY = "失效条目"
    OPERATION_TERM = "回填"
    LIST_FIELDS = ["失效编号", "所属维度", "属性名称", "失效判定", "失效日期", "受影响链数", "处置方式", "最近处置"]
    REQUIRED_FIELDS = ["失效编号", "所属维度", "属性名称"]
    STATUS_ORDER = ["待判定", "判定中", "已处置", "已忽略"]
    ACTION_RULES = {"启动判定": "判定中", "确认处置": "已处置", "忽略条目": "已忽略"}
    NEGATIVE_ACTIONS = ["忽略条目"]
