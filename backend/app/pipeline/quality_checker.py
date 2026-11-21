"""装配质量闸：阈值校验与阻断/放行决策。

核心行为：
- 在事实装配出口设置质量闸，校验项含外键命中率阈值、行数偏差阈值
- 实测读数越界时按阻断范围拦下批次，阻断与放行都会留痕
- 阻断后触发重跑任务编排，放行后推进装载窗口
"""
from __future__ import annotations

from typing import Any


class GateCheck:
    """质量闸校验项。"""

    def __init__(self, gate_id: str, check_item: str, threshold: float, scope: str):
        self.gate_id = gate_id
        self.check_item = check_item
        self.threshold = threshold
        self.scope = scope

    def evaluate(self, measured: float) -> tuple[bool, str]:
        """评估实测读数是否通过阈值。"""
        if measured < self.threshold:
            return False, (
                f"校验项「{self.check_item}」实测读数 {measured:.3f} "
                f"低于阈值 {self.threshold}，阻断范围：{self.scope}"
            )
        return True, (
            f"校验项「{self.check_item}」实测读数 {measured:.3f} "
            f"通过阈值 {self.threshold}"
        )


class GateResult:
    """质量闸执行结果。"""

    def __init__(self, gate_id: str, passed: bool, reason: str, scope: str, measured: float):
        self.gate_id = gate_id
        self.passed = passed
        self.reason = reason
        self.scope = scope
        self.measured = measured

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "passed": self.passed,
            "reason": self.reason,
            "scope": self.scope,
            "measured": self.measured,
        }


class QualityChecker:
    """质量闸检查器。"""

    def __init__(self) -> None:
        self._gates: dict[str, list[GateCheck]] = {}
        self._results: list[GateResult] = []

    def register_gate(self, fact_table: str, gate: GateCheck) -> None:
        self._gates.setdefault(fact_table, []).append(gate)

    def run_checks(self, fact_table: str, measurements: dict[str, float]) -> tuple[bool, list[GateResult]]:
        """执行质量闸全部校验项，返回 (全部通过, 结果列表)。"""
        gates = self._gates.get(fact_table, [])
        results: list[GateResult] = []
        all_passed = True
        for gate in gates:
            measured = measurements.get(gate.check_item)
            if measured is None:
                results.append(GateResult(
                    gate.gate_id, False,
                    f"校验项「{gate.check_item}」缺少实测读数",
                    gate.scope, 0.0,
                ))
                all_passed = False
                continue
            passed, reason = gate.evaluate(measured)
            result = GateResult(gate.gate_id, passed, reason, gate.scope, measured)
            results.append(result)
            if not passed:
                all_passed = False
        self._results.extend(results)
        return all_passed, results

    def last_results(self) -> list[GateResult]:
        return list(self._results)

    def snapshot(self) -> dict[str, Any]:
        return {
            "gates": {
                table: [  # type: ignore[has-type]
                    {"gate_id": g.gate_id, "check_item": g.check_item, "threshold": g.threshold}
                    for g in gates
                ]
                for table, gates in self._gates.items()
            },
            "results": [r.to_dict() for r in self._results],
        }