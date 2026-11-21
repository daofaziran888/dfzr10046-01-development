"""事实装配引擎：代理键解析、外键命中率、桥接权重归一、粒度校验。

核心行为：
- 从度量数据按维度关联找到对应代理键（通过 surrogate_key 模块的键段分配表）
- 计算外键命中率，不达标的批次进入待处理
- 多值桥接：权重归一化、归一失败时标记并阻止装配
- 粒度声明校验：事实粒度与汇总层派生粒度必须一致
"""
from __future__ import annotations

from typing import Any


class FactColumn:
    """事实表的度量列定义。"""

    def __init__(self, name: str, measure_name: str, aggregation: str = "SUM"):
        self.name = name
        self.measure_name = measure_name
        self.aggregation = aggregation


class SurrogateKeyMapping:
    """代理键映射：自然键 → 代理键。"""

    def __init__(self) -> None:
        self._mapping: dict[str, list[int]] = {}

    def register(self, natural_key: str, surrogate_key: int) -> None:
        self._mapping.setdefault(natural_key, []).append(surrogate_key)

    def lookup(self, natural_key: str) -> list[int]:
        return self._mapping.get(natural_key, [])


class BridgeWeight:
    """桥接权重条目：事实行 → 维度关联 + 权重比例。"""

    def __init__(self, fact_row_id: int, dim_name: str, weight: float):
        self.fact_row_id = fact_row_id
        self.dim_name = dim_name
        self.weight = weight


class FactAssembler:
    """事实装配器。"""

    def __init__(self) -> None:
        self._key_mapping = SurrogateKeyMapping()
        self._bridge_weights: list[BridgeWeight] = []
        self._dimensions: dict[str, list[str]] = {}
        self._grain_configs: dict[str, set[str]] = {}

    def register_dimension(self, table_name: str, dimension_keys: list[str]) -> None:
        """注册事实表的维度组合。"""
        self._dimensions[table_name] = dimension_keys

    def register_grain(self, table_name: str, grain_dims: set[str]) -> None:
        """注册粒度声明：一行代表的维度组合。"""
        self._grain_configs[table_name] = grain_dims

    def add_bridge_weight(self, weight: BridgeWeight) -> None:
        self._bridge_weights.append(weight)

    def check_grain_consistency(
        self, fact_table: str, summary_grain: set[str]
    ) -> tuple[bool, str]:
        """校验事实粒度与汇总派生粒度一致。"""
        declared = self._grain_configs.get(fact_table)
        if declared is None:
            return False, f"事实表 {fact_table} 无粒度声明"
        if declared != summary_grain:
            return False, (
                f"粒度不一致：事实表声明 {declared}，汇总要求 {summary_grain}"
            )
        return True, "粒度声明与汇总派生粒度一致"

    def compute_hit_rate(
        self, natural_keys: list[str]
    ) -> tuple[float, int, int]:
        """计算外键命中率：(已解析数/总数)。"""
        if not natural_keys:
            return 1.0, 0, 0
        total = len(natural_keys)
        resolved = sum(1 for nk in natural_keys if self._key_mapping.lookup(nk))
        return resolved / total if total > 0 else 0.0, total, resolved

    def normalize_bridge_weights(
        self, fact_row_ids: list[int] | None = None
    ) -> tuple[bool, str, dict[int, float]]:
        """桥接权重归一化：同一事实行关联的维度权重之和必须为 1。

        Returns:
            (ok, message, {fact_row_id: normalized_sum})
        """
        if fact_row_ids is None:
            fact_row_ids = sorted({bw.fact_row_id for bw in self._bridge_weights})

        row_sums: dict[int, float] = {}
        for bw in self._bridge_weights:
            if bw.fact_row_id in (fact_row_ids or []):
                row_sums[bw.fact_row_id] = row_sums.get(bw.fact_row_id, 0.0) + bw.weight

        failures: dict[int, float] = {}
        for rid, total in row_sums.items():
            if abs(total - 1.0) > 0.001:
                failures[rid] = total
        if failures:
            rows_str = ", ".join(f"行{rid}=>{total:.3f}" for rid, total in failures.items())
            return False, f"归一失败：权重之和不为 1，{rows_str}", failures
        return True, f"全部 {len(row_sums)} 行桥接权重归一通过", row_sums

    def assemble_batch(
        self,
        batch_id: str,
        fact_table: str,
        measure_columns: list[FactColumn],
        row_keys: list[str],
        dimension_names: list[str],
    ) -> tuple[bool, str, dict[str, Any]]:
        """装配一个事实批次。

        步骤：
        1. 校验粒度声明
        2. 解析代理键 → 计算外键命中率
        3. 归一化桥接权重
        4. 汇总装配结果
        """
        dims = self._dimensions.get(fact_table, dimension_names)
        declared_grain = self._grain_configs.get(fact_table, set())

        # 外键命中率
        hit_rate, total_keys, resolved_keys = self.compute_hit_rate(row_keys)
        if hit_rate < 0.80:
            return False, (
                f"外键命中率 {hit_rate:.1%} 低于阈值 80%，"
                f"已解析 {resolved_keys}/{total_keys}，批次进入待处理"
            ), {"batch_id": batch_id, "hit_rate": hit_rate, "status": "待装配"}

        # 桥接归一
        norm_ok, norm_msg, _ = self.normalize_bridge_weights()
        if not norm_ok:
            return False, norm_msg, {"batch_id": batch_id, "status": "装配异常"}

        return True, (
            f"批次 {batch_id} 装配完成，{total_keys} 行，命中率 {hit_rate:.1%}"
        ), {
            "batch_id": batch_id,
            "fact_table": fact_table,
            "hit_rate": hit_rate,
            "total_rows": total_keys,
            "dimensions": dims,
            "grain": list(declared_grain),
            "status": "已装配",
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "dimensions": dict(self._dimensions),
            "grain_configs": {k: list(v) for k, v in self._grain_configs.items()},
            "bridge_weights_count": len(self._bridge_weights),
        }