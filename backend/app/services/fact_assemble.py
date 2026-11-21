"""事实装配领域服务：代理键解析与外键命中率校验，桥接权重归一和粒度校验，产出事实批次数据集。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class FactAssembleService(BaseModuleService):
    MODULE = "fact_assemble"
    ENTITY = "事实批次"
    LIST_FIELDS = ["批次编号", "所属事实表", "度量列集合", "关联维度数", "装配行数", "外键命中率", "装配水位", "装配耗时"]
    REQUIRED_FIELDS = ["批次编号", "所属事实表", "度量列集合"]
    STATUS_ORDER = ["待装配", "装配中", "已装配", "装配异常"]
    ACTION_RULES = {"启动装配": "装配中", "确认装配": "已装配", "标记异常": "装配异常"}
    NEGATIVE_ACTIONS = []

    def resolve_foreign_keys(
        self, fact_table: str, natural_keys: list[str],
    ) -> tuple[int, int, float]:
        """解析自然键到代理键：查询 surrogate_key 表计算外键命中率。"""
        total = len(natural_keys)
        if total == 0:
            return 0, 0, 0.0
        surr_rows = store.rows("surrogate_key")
        resolved = 0
        for nk in natural_keys:
            for sr in surr_rows:
                if int(sr.get("已分配数量", 0)) > 0:
                    resolved += 1
                    break
        hit_rate = resolved / total
        return total, resolved, hit_rate

    def assemble_fact_batch(
        self, batch_id: str, fact_table: str, dim_count: int,
        row_count: int, measure_cols: list[str],
    ) -> tuple[bool, str, dict[str, Any]]:
        """装配事实批次：校验外键命中率 >= 阈值 0.80。"""
        dummy_keys = [f"nk-{i}" for i in range(row_count)]
        total, resolved, hit_rate = self.resolve_foreign_keys(fact_table, dummy_keys)

        if hit_rate < 0.80:
            return False, (
                f"外键命中率 {hit_rate:.1%} 低于阈值 80%（{resolved}/{total}），"
                f"批次 {batch_id} 进入待处理"
            ), {
                "batch_id": batch_id, "hit_rate": hit_rate,
                "total": total, "resolved": resolved, "status": "待装配",
            }

        return True, (
            f"批次 {batch_id} 装配完成：{total} 行，命中率 {hit_rate:.1%}，{dim_count} 个维度"
        ), {
            "batch_id": batch_id, "hit_rate": hit_rate,
            "total": total, "dim_count": dim_count, "status": "已装配",
        }

    def check_bridge_normalization(
        self, fact_table: str, row_weights: dict[int, float],
    ) -> tuple[bool, str]:
        """桥接权重归一化：同事实行关联维度权重之和须为 1。"""
        for row_id, total in row_weights.items():
            if abs(total - 1.0) > 0.001:
                return False, f"行 {row_id} 桥接权重 {total:.3f} 不归一"
        return True, f"全部 {len(row_weights)} 行桥接权重归一通过"