"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class SrcExtractService(BaseModuleService):
    MODULE = "src_extract"
    ENTITY = "抽取批次"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["抽取编号", "来源系统", "抽取范围", "抽取方式", "抽取行数", "抽取水位", "校验摘要", "抽取时间"]
    REQUIRED_FIELDS = ["抽取编号", "来源系统", "抽取范围"]
    STATUS_ORDER = ["待抽取", "抽取中", "已抽取", "抽取失败"]
    ACTION_RULES = {"启动抽取": "抽取中", "确认抽取": "已抽取", "标记失败": "抽取失败"}
    NEGATIVE_ACTIONS = []
