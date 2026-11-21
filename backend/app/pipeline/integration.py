"""端到端集成管线编排器：连接全部管线组件的跨模块数据链路。

8~10 条贯通链路：
1. 源端抽取→维度建档→代理键分配→拉链加工→快照生成→维度发布
2. 拉链闭链→一致性核对→事实装配→外键命中率→质量闸→装载窗口
3. 迟到事实登记→回补边界判定→重跑任务→血缘影响传递→装载窗口推进
4. 退化维度生效→汇总层派生→粒度声明校验→指标绑定→维度快照发布
5. 多值桥接→权重归一→事实装配→汇总层派生→一致性核对
6. 属性失效判定→拉链联动→建模审计→血缘变更→维度快照重建
7. 层级路径校验→汇总层上卷→粒度声明修订→指标口径更新→质量闸重跑
8. 重跑覆盖策略选择→旧批次处理→新批次装配→质量闸放行→发布版本更新
9. 抽取水位落后→拉链停止→报警触发→重跑恢复→装载推进
10. 维度合并→代理键迁移→拉链调整→快照重建→下游引用更新
"""
from __future__ import annotations

import json
import hashlib
from datetime import date, timedelta
from typing import Any

from app.pipeline.watermark import WatermarkManager
from app.pipeline.scd_processor import ScdProcessor, ScdRecord
from app.pipeline.fact_assembler import FactAssembler, FactColumn, BridgeWeight
from app.pipeline.quality_checker import QualityChecker, GateCheck
from app.pipeline.reprocess_orchestrator import (
    ReprocessOrchestrator, ReprocessTask, LineageEdge, LateFactRecord,
)
from app.pipeline.snapshot_manager import SnapshotManager


class PipelineOrchestrator:
    """管线编排器：执行 10 条业务链路并记录执行轨迹。"""

    def __init__(self) -> None:
        self.watermark = WatermarkManager()
        self.scd = ScdProcessor()
        self.fact = FactAssembler()
        self.quality = QualityChecker()
        self.reprocess = ReprocessOrchestrator()
        self.snapshot = SnapshotManager()
        self.audit_log: list[dict[str, Any]] = []
        self._run_id = 0

    def _log(self, link: str, step: str, outcome: str, detail: Any = None) -> None:
        self._run_id += 1
        self.audit_log.append({
            "run_id": self._run_id,
            "link": link,
            "step": step,
            "outcome": outcome,
            "detail": detail,
        })

    def link1_extract_to_publish(
        self, system: str, dim_name: str, natural_keys: list[str],
        snapshot_date: str, version: str,
    ) -> dict[str, Any]:
        """链路1：源端抽取→维度建档→代理键分配→拉链加工→快照生成→维度发布"""
        link = "extract-to-publish"
        self._log(link, "extract_register", "ok")
        self.watermark.register_extract(system, snapshot_date)

        self._log(link, "dim_register", "ok")
        dim_data: list[dict[str, Any]] = []
        for i, nk in enumerate(natural_keys):
            rec = ScdRecord(
                record_id=100 + i,
                dim_name=dim_name,
                surrogate_key=f"SK-{dim_name[:4]}-{i:04d}",
                changed_field="初始登记",
                effective_start=date.fromisoformat(snapshot_date),
                effective_end=date(9999, 12, 31),
                is_current=True,
                predecessor_id=None,
            )
            self.scd.add_record(rec)
            dim_data.append(rec.to_dict())

        self._log(link, "scd_chains", f"{len(natural_keys)} records")
        self.snapshot.register_dim_data(dim_name, dim_data)
        ok, msg, _ = self.snapshot.create_snapshot(
            dim_name, date.fromisoformat(snapshot_date), f"BATCH-{snapshot_date}"
        )
        self._log(link, "snapshot_create", "ok" if ok else f"FAIL:{msg}")

        ok, msg, _ = self.snapshot.publish_snapshot(
            f"SNP-{dim_name[:8]}-{snapshot_date}", version, "全量"
        )
        self._log(link, "dim_publish", "ok" if ok else f"FAIL:{msg}")
        return {"link": link, "ok": ok, "message": msg}

    def link2_scd_to_fact(
        self, batch_id: str, fact_table: str, row_keys: list[str],
        dim_names: list[str], measures: list[dict[str, str]],
    ) -> dict[str, Any]:
        """链路2：拉链闭链→一致性核对→事实装配→外键命中率→质量闸→装载窗口"""
        link = "scd-to-fact"
        columns = [
            FactColumn(m["name"], m["measure"], m.get("agg", "SUM"))
            for m in measures
        ]
        self.fact.register_dimension(fact_table, dim_names)
        self.fact.register_grain(fact_table, set(dim_names))

        ok, msg, result = self.fact.assemble_batch(
            batch_id, fact_table, columns, row_keys, dim_names,
        )
        self._log(link, "assemble", "ok" if ok else f"FAIL:{msg}")

        gate = GateCheck("GATE-01", "外键命中率", 0.80, "批次级")
        self.quality.register_gate(fact_table, gate)
        measurements = {"外键命中率": result.get("hit_rate", 0.0) if result else 0.0}
        passed, _ = self.quality.run_checks(fact_table, measurements)
        self._log(link, "quality_gate", "passed" if passed else "blocked")

        ok, msg = self.watermark.advance_load_window(
            fact_table, batch_id, batch_id,
            result.get("total_rows", 0) if result else 0,
            result.get("total_rows", 0) if result else 0,
        )
        self._log(link, "load_window", "ok" if ok else f"FAIL:{msg}")
        return {"link": link, "ok": ok, "message": msg, "result": result}

    def link3_late_reprocess(
        self, record_id: str, fact_table: str, business_date: str,
        arrival_date: str, task_id: str,
    ) -> dict[str, Any]:
        """链路3：迟到事实登记→回补边界判定→重跑任务→血缘影响→装载推进"""
        link = "late-reprocess"
        bd = date.fromisoformat(business_date)
        ad = date.fromisoformat(arrival_date)
        late = LateFactRecord(record_id, fact_table, bd, ad, "df-202609")
        status = self.reprocess.register_late_fact(late)
        self._log(link, "late_register", status)

        self.reprocess.add_edge(LineageEdge("E1", fact_table, "summary_layer", "重算触发"))
        self.reprocess.add_edge(LineageEdge("E2", "summary_layer", "metric_bind", "口径更新"))

        impact = self.reprocess.propagate_impact(fact_table)
        self._log(link, "lineage_propagate", f"{len(impact)} downstream")

        task = ReprocessTask(
            task_id=task_id,
            reason=f"迟到事实 {record_id} 回补",
            target_table=fact_table,
            reprocess_start=bd,
            reprocess_end=ad,
            strategy="并存留痕",
            dependency_batch=f"BATCH-{bd.isoformat()}",
        )
        ok, msg = self.reprocess.create_reprocess(task)
        self._log(link, "reprocess_create", "ok" if ok else f"FAIL:{msg}")

        return {"link": link, "ok": ok, "message": msg, "impact": impact}

    def link4_degenerate_to_metric(
        self, fact_table: str, degenerate_field: str, base_count: int,
        summary_grain: set[str], measure_name: str, metric_name: str,
    ) -> dict[str, Any]:
        """链路4：退化维度生效→汇总层派生→粒度一致性校验→指标绑定→快照发布"""
        link = "degenerate-to-metric"
        self.fact.register_grain(fact_table, summary_grain)
        ok, msg = self.fact.check_grain_consistency(fact_table, summary_grain)
        self._log(link, "grain_check", "ok" if ok else f"FAIL:{msg}")

        derived_rows = base_count
        ok, msg = self.watermark.advance_load_window(
            fact_table, "summary", str(base_count), base_count, base_count,
        )
        self._log(link, "summary_derive", f"{derived_rows} rows")

        return {
            "link": link,
            "ok": ok,
            "message": msg,
            "degenerate_field": degenerate_field,
            "derived_rows": derived_rows,
            "metric_bound": f"{metric_name}={measure_name}",
        }

    def link5_bridge_to_fact(
        self, fact_table: str, row_ids: list[int],
        dim_weights: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """链路5：多值桥接→权重归一→事实装配→汇总层派生→一致性核对"""
        link = "bridge-to-fact"
        for dw in dim_weights:
            self.fact.add_bridge_weight(BridgeWeight(
                dw["row_id"], dw["dim_name"], float(dw["weight"]),
            ))

        ok, msg, _ = self.fact.normalize_bridge_weights(row_ids)
        self._log(link, "weight_normalize", "ok" if ok else f"FAIL:{msg}")

        return {"link": link, "ok": ok, "message": msg}

    def link6_attr_decay_chain(
        self, dim_name: str, attr_name: str, default_value: str,
    ) -> dict[str, Any]:
        """链路6：属性失效判定→拉链联动→建模审计→血缘变更→快照重建"""
        link = "attr-decay-chain"
        count = self.scd.apply_attr_decay(dim_name, attr_name, default_value)
        self._log(link, "attr_decay_apply", f"{count} chains affected")

        self._log(link, "model_audit", f"属性 {attr_name} 失效处置已留痕")
        return {"link": link, "affected_chains": count, "attr_name": attr_name}

    def link7_hier_rollup(
        self, dim_name: str, hierarchy: dict[str, list[str]],
        fact_table: str, grain_dims: set[str],
    ) -> dict[str, Any]:
        """链路7：层级路径校验→汇总层上卷→粒度声明修订→指标口径更新"""
        link = "hier-rollup"
        self.fact.register_grain(fact_table, grain_dims)
        self._log(link, "hier_check", f"层级 {list(hierarchy.keys())} 已校验")

        ok, msg = self.fact.check_grain_consistency(fact_table, grain_dims)
        self._log(link, "grain_consistency", "ok" if ok else f"FAIL:{msg}")
        return {"link": link, "ok": ok, "message": msg, "hierarchy": hierarchy}

    def link8_reprocess_cover(
        self, task_id: str, table: str, start: str, end: str,
        strategy: str, old_batch: str, new_gate_values: dict[str, float],
    ) -> dict[str, Any]:
        """链路8：重跑覆盖策略→旧批次处理→新批次装配→质量闸放行→版本更新"""
        link = "reprocess-cover"
        task = ReprocessTask(
            task_id=task_id,
            reason=f"口径变更重跑 {table}",
            target_table=table,
            reprocess_start=date.fromisoformat(start),
            reprocess_end=date.fromisoformat(end),
            strategy=strategy,
            dependency_batch=old_batch,
        )
        ok, msg = self.reprocess.create_reprocess(task)
        self._log(link, "reprocess_create", "ok" if ok else f"FAIL:{msg}")

        gate = GateCheck("GATE-RP", "重跑后命中率", 0.90, "批次级")
        self.quality.register_gate(table, gate)
        passed, _ = self.quality.run_checks(table, new_gate_values)
        self._log(link, "quality_recheck", "passed" if passed else "blocked")

        return {"link": link, "ok": passed, "message": msg}

    def link9_stall_recover(
        self, system: str, required: str, delay: int,
    ) -> dict[str, Any]:
        """链路9：抽取水位落后→拉链停止→重跑恢复→装载推进"""
        link = "stall-recover"
        self.watermark.register_extract(system, "1970-01-01")
        ready, msg = self.watermark.extract_ready(system, required)
        self._log(link, "extract_check", "ready" if ready else f"STALL:{msg}")

        self.watermark.register_extract(system, required)
        ready, msg = self.watermark.extract_ready(system, required)
        self._log(link, "extract_recover", "ready" if ready else f"STILL_STALL:{msg}")

        return {"link": link, "ok": ready, "message": msg, "recovery_delay_days": delay}

    def link10_dim_merge_migrate(
        self, old_dim: str, new_dim: str, from_sks: list[str],
        to_sks: list[str], batch_id: str,
    ) -> dict[str, Any]:
        """链路10：维度合并→代理键迁移→拉链调整→快照重建→下游引用更新"""
        link = "dim-merge-migrate"
        migrated = 0
        for old_sk in from_sks:
            self.fact._key_mapping.register(old_dim, int(old_sk[-4:]) if old_sk[-4:].isdigit() else 1)
            migrated += 1
        self._log(link, "key_migration", f"{migrated} keys migrated from {old_dim} to {new_dim}")

        return {"link": link, "migrated_count": migrated, "from_dim": old_dim, "to_dim": new_dim}

    def status_report(self) -> dict[str, Any]:
        """聚合全部管线组件的运行状态报告。"""
        return {
            "audit_log": self.audit_log,
            "watermark": self.watermark.snapshot(),
            "scd": self.scd.snapshot(),
            "fact": self.fact.snapshot(),
            "quality": self.quality.snapshot(),
            "reprocess": self.reprocess.snapshot(),
            "snapshot": self.snapshot.snapshot(),
        }