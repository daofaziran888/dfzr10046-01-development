"""__NAME__领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。"""
from __future__ import annotations

from app.services.base import BaseModuleService


class MeasureCatalogService(BaseModuleService):
    MODULE = "measure_catalog"
    ENTITY = "度量条目"
    OPERATION_TERM = "聚合"
    LIST_FIELDS = ["度量编号", "度量名称", "计算表达式", "聚合方式", "单位声明", "精度位数", "适用粒度", "目录版本"]
    REQUIRED_FIELDS = ["度量编号", "度量名称", "计算表达式"]
    STATUS_ORDER = ["草稿", "已收录", "已修订", "已下线"]
    ACTION_RULES = {"收录度量": "已收录", "提交修订": "已修订", "下线度量": "已下线"}
    NEGATIVE_ACTIONS = ["下线度量"]
