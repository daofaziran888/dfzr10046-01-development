"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class HierPathService(BaseModuleService):
    MODULE = "hier_path"
    ENTITY = "层级路径"
    OPERATION_TERM = "聚合"
    LIST_FIELDS = ["路径编号", "所属维度", "层级名称", "上级层级", "层级深度", "跨越标记", "路径校验值", "最近校验"]
    REQUIRED_FIELDS = ["路径编号", "所属维度", "层级名称"]
    STATUS_ORDER = ["草稿", "已校验", "存在断裂", "已停用"]
    ACTION_RULES = {"提交校验": "已校验", "登记断裂": "存在断裂", "停用路径": "已停用"}
    NEGATIVE_ACTIONS = ["停用路径"]
