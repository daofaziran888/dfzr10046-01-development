"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class ScdChainService(BaseModuleService):
    MODULE = "scd_chain"
    ENTITY = "拉链记录"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["拉链编号", "所属维度", "代理键", "变更字段", "生效起日", "生效止日", "是否当前", "链上前序"]
    REQUIRED_FIELDS = ["拉链编号", "所属维度", "代理键"]
    STATUS_ORDER = ["加工中", "已闭链", "区间冲突", "已作废"]
    ACTION_RULES = {"闭链记录": "已闭链", "标记冲突": "区间冲突", "作废记录": "已作废"}
    NEGATIVE_ACTIONS = ["作废记录"]
