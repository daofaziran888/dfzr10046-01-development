"""建档交接领域服务：维度建档提交后同步代理键待办，覆盖领取、分段、退回与补正重提。

设计要点：
- 同一维度编号只保留一份有效交接回执，补正重提走原回执，不产生第二份有效待办；
- 领取采用锁内检查并设置，两个窗口同时领取时只有一个取得填写资格；
- 分段登记直连代理键生成，已登记的键段在退回/补正后继续可用；
- 补正重提对比登记快照，结构字段变化时补正前分段说明作废（需重填），否则可沿用。
"""
from __future__ import annotations

import re
import threading
from datetime import date
from typing import Any

from app.services.base import BaseModuleService
from app.store import store

# 影响键段分段含义的结构字段：补正涉及这些字段时，补正前分段说明不得沿用。
STRUCTURAL_FIELDS = ["业务主键", "自然键来源", "维度类型"]
SNAPSHOT_FIELDS = ["维度名称", "业务主键", "自然键来源", "维度类型", "所属主题域"]
DEFAULT_CLAIMERS = "代理键操作员·赵、代理键操作员·钱"
DEFAULT_SUBMITTER = "值班员"

HINT_BY_STATUS = {
    "待领取": "待领取",
    "已领取": "可继续分段",
    "分段登记中": "可继续分段",
    "已退回": "必须先补正",
    "已完成": "已办结",
}


def _today() -> str:
    return date.today().isoformat()


class EntryHandoffService(BaseModuleService):
    MODULE = "entry_handoff"
    ENTITY = "交接回执"
    LIST_FIELDS = ["交接编号", "维度编号", "维度名称", "提交人", "待领人", "可填写对象",
                   "领取人", "分段进度", "沿用标记", "办理提示", "交接时间"]
    REQUIRED_FIELDS = ["交接编号", "维度编号", "维度名称"]
    STATUS_ORDER = ["待领取", "已领取", "分段登记中", "已退回", "已完成"]
    ACTION_RULES = {"领取交接": "已领取", "登记分段": "分段登记中", "退回补正": "已退回",
                    "补正重提": "待领取", "完成交接": "已完成"}
    NEGATIVE_ACTIONS = ["退回补正"]

    def __init__(self) -> None:
        # 领取互斥锁：检查状态与写入领取人必须在同一把锁内完成。
        self._claim_lock = threading.Lock()

    # ---------- 查询 ----------

    def list_entries(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        self._refresh_hints()
        return super().list_entries(**kwargs)

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = super().get_entry(entry_id)
        if row is not None:
            row["办理提示"] = HINT_BY_STATUS.get(str(row.get("status", "")), "")
        return row

    def _refresh_hints(self) -> None:
        for row in store.rows(self.MODULE):
            row["办理提示"] = HINT_BY_STATUS.get(str(row.get("status", "")), "")

    # ---------- 登记（手工登记回执，幂等） ----------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [
            field for field in self.REQUIRED_FIELDS
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, missing
        code = str(values.get("维度编号") or "").strip()
        active = self._active_receipt(code)
        if active is not None:
            # 同一维度只保留一份有效待办，重复登记直接返回原回执。
            return active, []
        rows = store.rows(self.MODULE)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "领取人": "", "分段进度": "已登记0段", "沿用标记": "—", "退回原因": "",
            "交接履历": [f"{_today()} 手工登记交接回执"],
            "分段说明列表": [], "登记快照": {},
            "status": self.STATUS_ORDER[0], "pending": True, "abnormal": False,
        }
        entry.update({field: values.get(field) for field in self.LIST_FIELDS})
        rows.append(entry)
        self._refresh_hints()
        return entry, []

    # ---------- 与维度建档的同步 ----------

    def sync_from_dim_entry(
        self, dim_row: dict[str, Any], submitter: str = DEFAULT_SUBMITTER,
    ) -> tuple[dict[str, Any], str, bool]:
        """维度建档提交后同步代理键待办。

        返回 (回执, 说明, 是否新建)。已退回的回执走补正重提回到待领取；
        仍在办理的回执不重复生成，保证同一维度只有一份有效待办。
        """
        code = str(dim_row.get("维度编号") or "").strip()
        active = self._active_receipt(code)
        if active is None:
            receipt = self._new_receipt(dim_row, submitter)
            return receipt, f"已同步代理键待办：{receipt['交接编号']}", True
        if active.get("status") == "已退回":
            receipt, message = self._resubmit(active, dim_row, submitter)
            return receipt, message, False
        return active, f"{active['交接编号']} 仍在办理，未重复生成待办", False

    def _new_receipt(self, dim_row: dict[str, Any], submitter: str) -> dict[str, Any]:
        rows = store.rows(self.MODULE)
        seq = max(
            (int(str(row.get("交接编号", "HOF-000")).split("-")[-1])
             for row in rows if str(row.get("交接编号", "")).startswith("HOF-")),
            default=0,
        ) + 1
        dim_name = str(dim_row.get("维度名称") or "")
        receipt: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "交接编号": f"HOF-{seq:03d}",
            "维度编号": str(dim_row.get("维度编号") or ""),
            "维度名称": dim_name,
            "提交人": submitter,
            "待领人": DEFAULT_CLAIMERS,
            "可填写对象": f"{dim_name}·代理键分段登记",
            "领取人": "",
            "分段进度": "已登记0段",
            "沿用标记": "—",
            "退回原因": "",
            "交接时间": _today(),
            "交接履历": [f"{_today()} {submitter} 提交{dim_name}，生成交接回执"],
            "分段说明列表": [],
            "登记快照": {field: dim_row.get(field, "") for field in SNAPSHOT_FIELDS},
            "status": "待领取", "pending": True, "abnormal": False,
        }
        rows.append(receipt)
        self._refresh_hints()
        return receipt

    # ---------- 动作 ----------

    def run_action(
        self, entry_id: int, action: str, remark: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        receipt = store.find(self.MODULE, entry_id)
        if receipt is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"
        note = (remark or "").strip()
        handlers = {
            "领取交接": lambda: self._claim(receipt, note),
            "登记分段": lambda: self._register_segment(receipt, note),
            "退回补正": lambda: self._return_for_correction(receipt, note),
            "补正重提": lambda: self._resubmit_action(receipt),
            "完成交接": lambda: self._complete(receipt),
        }
        handler = handlers.get(action)
        if handler is None:
            return None, f"动作「{action}」不属于{self.MODULE}可执行范围"
        entry, message = handler()
        self._refresh_hints()
        return entry, message

    def _claim(
        self, receipt: dict[str, Any], operator: str,
    ) -> tuple[dict[str, Any] | None, str]:
        if not operator:
            return None, f"领取交接需指定领取人（待领人：{receipt.get('待领人', '')}）"
        with self._claim_lock:
            status = str(receipt.get("status", ""))
            if status == "已退回":
                return None, f"{receipt['交接编号']} 已退回原提交人，必须先补正再领取"
            if status != "待领取":
                claimer = receipt.get("领取人") or "其他操作员"
                return None, f"{receipt['交接编号']} 已被{claimer}领取，本窗口未取得填写资格"
            allowed = self._claimers(receipt)
            if allowed and operator not in allowed:
                return None, f"{operator} 不在待领人名单（{receipt.get('待领人', '')}）"
            receipt["领取人"] = operator
            receipt["status"] = "已领取"
            receipt["pending"] = True
            receipt["交接履历"].append(
                f"{_today()} {operator} 领取交接，取得填写资格")
            return dict(receipt), f"{operator} 已领取 {receipt['交接编号']}，可继续分段登记"

    def _register_segment(
        self, receipt: dict[str, Any], note: str,
    ) -> tuple[dict[str, Any] | None, str]:
        status = str(receipt.get("status", ""))
        if status == "已退回":
            return None, f"{receipt['交接编号']} 已退回，必须先补正再登记分段"
        if status not in ("已领取", "分段登记中"):
            return None, f"{receipt['交接编号']} 当前状态为{status}，不可登记分段"
        if not note:
            return None, "登记分段需填写分段说明"
        with self._claim_lock:
            seg_code = self._create_key_segment(str(receipt.get("维度名称") or ""))
            notes: list[str] = receipt.setdefault("分段说明列表", [])
            notes.append(f"{seg_code}：{note}")
            receipt["分段进度"] = f"已登记{len(notes)}段"
            if str(receipt.get("沿用标记", "—")) in ("", "—"):
                receipt["沿用标记"] = "可沿用"
            receipt["status"] = "分段登记中"
            receipt["pending"] = True
            receipt["交接履历"].append(
                f"{_today()} {receipt.get('领取人', '')} 登记分段 {seg_code}：{note}")
        return dict(receipt), f"已登记分段 {seg_code}，键段同步至代理键生成"

    def _return_for_correction(
        self, receipt: dict[str, Any], reason: str,
    ) -> tuple[dict[str, Any] | None, str]:
        status = str(receipt.get("status", ""))
        if status not in ("已领取", "分段登记中"):
            return None, f"{receipt['交接编号']} 当前状态为{status}，不可退回"
        reason = reason or "登记不完整"
        claimer = receipt.get("领取人") or "接手人"
        submitter = receipt.get("提交人") or DEFAULT_SUBMITTER
        receipt["status"] = "已退回"
        receipt["退回原因"] = reason
        receipt["abnormal"] = True
        receipt["pending"] = True
        receipt["交接履历"].append(
            f"{_today()} {claimer} 退回原提交人{submitter}补正：{reason}")
        return dict(receipt), f"已退回原提交人{submitter}补正：{reason}"

    def _resubmit_action(
        self, receipt: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        if str(receipt.get("status", "")) != "已退回":
            return None, f"仅已退回的回执可补正重提（当前：{receipt.get('status', '')}）"
        dim_row = self._dim_row(str(receipt.get("维度编号") or ""))
        return self._resubmit(receipt, dim_row, str(receipt.get("提交人") or DEFAULT_SUBMITTER))

    def _resubmit(
        self, receipt: dict[str, Any], dim_row: dict[str, Any] | None, submitter: str,
    ) -> tuple[dict[str, Any], str]:
        """补正重提：回到待领取，判定补正前分段说明能否沿用，履历留痕。"""
        snapshot: dict[str, Any] = receipt.get("登记快照") or {}
        current = dim_row or {}
        changed = [
            field for field in STRUCTURAL_FIELDS
            if str(snapshot.get(field, "")) != str(current.get(field, ""))
        ]
        notes: list[str] = receipt.get("分段说明列表") or []
        if changed and notes:
            receipt["沿用标记"] = "需重填"
            receipt["交接履历"].append(
                f"{_today()} 补正涉及{'、'.join(changed)}，补正前分段说明作废：{'；'.join(notes)}")
            receipt["分段说明列表"] = []
            receipt["分段进度"] = "已登记0段"
        elif changed:
            receipt["沿用标记"] = "需重填"
            receipt["交接履历"].append(
                f"{_today()} 补正涉及{'、'.join(changed)}，后续分段说明需重填")
        else:
            receipt["沿用标记"] = "可沿用" if notes else "—"
        if dim_row:
            receipt["登记快照"] = {field: dim_row.get(field, "") for field in SNAPSHOT_FIELDS}
            receipt["维度名称"] = str(dim_row.get("维度名称") or receipt.get("维度名称") or "")
            receipt["可填写对象"] = f"{receipt['维度名称']}·代理键分段登记"
        receipt["领取人"] = ""
        receipt["退回原因"] = ""
        receipt["abnormal"] = False
        receipt["pending"] = True
        receipt["status"] = "待领取"
        receipt["交接时间"] = _today()
        receipt["交接履历"].append(
            f"{_today()} {submitter} 补正重提，回执回到待领取（沿用标记：{receipt['沿用标记']}）")
        reuse_note = "分段说明可沿用" if receipt["沿用标记"] == "可沿用" else "分段说明需重填"
        if receipt["沿用标记"] == "—":
            reuse_note = "尚未填写分段说明"
        return receipt, f"{receipt['交接编号']} 补正重提完成，{reuse_note}，已分配键段继续可用"

    def _complete(self, receipt: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        if str(receipt.get("status", "")) != "分段登记中":
            return None, f"{receipt['交接编号']} 至少登记一段后才能完成交接"
        receipt["status"] = "已完成"
        receipt["pending"] = False
        receipt["交接履历"].append(
            f"{_today()} {receipt.get('领取人', '')} 完成交接，{receipt.get('分段进度', '')}")
        return dict(receipt), f"{receipt['交接编号']} 已完成交接"

    # ---------- 内部工具 ----------

    def _active_receipt(self, dim_code: str) -> dict[str, Any] | None:
        """同一维度编号最近一份未办结的回执；已完成的旧回执不算有效待办。"""
        for row in reversed(store.rows(self.MODULE)):
            if row.get("维度编号") == dim_code and row.get("status") != "已完成":
                return row
        return None

    @staticmethod
    def _claimers(receipt: dict[str, Any]) -> list[str]:
        raw = str(receipt.get("待领人") or "")
        return [name.strip() for name in re.split(r"[、,，/]", raw) if name.strip()]

    @staticmethod
    def _dim_row(dim_code: str) -> dict[str, Any] | None:
        for row in store.rows("dim_entry"):
            if row.get("维度编号") == dim_code:
                return row
        return None

    @staticmethod
    def _create_key_segment(dim_name: str) -> str:
        """分段登记直连代理键生成：为该维度追加一个待分配键段。"""
        rows = store.rows("surrogate_key")
        max_end = max(
            (int(row.get("键段终点") or 0) for row in rows
             if row.get("所属维度") == dim_name and str(row.get("键段终点") or "").isdigit()),
            default=0,
        )
        start = max_end + 1 if max_end else 1000
        seq = max(
            (int(str(row.get("键段编号", "SEG-0")).split("-")[-1])
             for row in rows if str(row.get("键段编号", "")).startswith("SEG-")),
            default=0,
        ) + 1
        rows.append({
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "键段编号": f"SEG-{seq:03d}", "所属维度": dim_name,
            "键段起点": str(start), "键段终点": str(start + 999),
            "已分配数量": 0, "回收标记": "否",
            "分配策略": "SEQUENTIAL", "最近分配": "",
            "status": "待分配", "pending": True, "abnormal": False,
        })
        return f"SEG-{seq:03d}"
