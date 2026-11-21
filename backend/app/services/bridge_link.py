"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class BridgeLinkService(BaseModuleService):
    MODULE = "bridge_link"
    ENTITY = "桥接条目"
    OPERATION_TERM = "关联"
    LIST_FIELDS = ["桥接编号", "所属事实表", "关联维度", "权重比例", "桥接行数", "归一校验", "桥接版本", "最近装配"]
    REQUIRED_FIELDS = ["桥接编号", "所属事实表", "关联维度"]
    STATUS_ORDER = ["待装配", "已装配", "归一失败", "已作废"]
    ACTION_RULES = {"启动装配": "已装配", "登记归一失败": "归一失败", "作废条目": "已作废"}
    NEGATIVE_ACTIONS = ["作废条目"]
