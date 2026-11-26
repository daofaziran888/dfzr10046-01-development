"""建档交接链路测试：维度建档提交 → 代理键待办 → 领取/分段/退回/补正重提。"""
from __future__ import annotations

import threading

import pytest

from app.services.dim_entry import DimEntryService
from app.services.entry_handoff import EntryHandoffService
from app.store import store


@pytest.fixture()
def handoff():
    return EntryHandoffService()


@pytest.fixture()
def dim():
    return DimEntryService()


def _submit_dim(dim: DimEntryService, code: str, name: str, business_key: str = "biz_key"):
    entry, missing = dim.create_entry({
        "维度编号": code, "维度名称": name, "业务主键": business_key,
        "自然键来源": "ERP", "维度类型": "SCD2", "所属主题域": "测试",
        "生效标记": "待生效", "登记时间": "2026-11-26",
    })
    assert not missing
    return entry


def _receipts_of(code: str) -> list[dict]:
    return [r for r in store.rows("entry_handoff") if r.get("维度编号") == code]


def _active_of(code: str) -> list[dict]:
    return [r for r in _receipts_of(code) if r.get("status") != "已完成"]


class TestHandoffSync:
    """值班员提交维度后，建档工作台把提交结果同步到代理键待办。"""

    def test_submit_dim_creates_handoff_todo(self, dim, handoff):
        entry = _submit_dim(dim, "DIM-H01", "客户维度H01")
        assert entry["交接同步"].startswith("已同步代理键待办")
        receipts = _receipts_of("DIM-H01")
        assert len(receipts) == 1
        receipt = receipts[0]
        assert receipt["status"] == "待领取"
        assert receipt["待领人"]  # 交接视图要展示待领人
        assert receipt["可填写对象"] == "客户维度H01·代理键分段登记"
        assert receipt["提交人"]

    def test_duplicate_submit_no_second_todo(self, dim, handoff):
        _submit_dim(dim, "DIM-H02", "客户维度H02")
        _submit_dim(dim, "DIM-H02", "客户维度H02")
        assert len(_active_of("DIM-H02")) == 1

    def test_handoff_view_lists_claimers_and_fillable(self, dim, handoff):
        _submit_dim(dim, "DIM-H03", "门店维度H03")
        items, total = handoff.list_entries(
            filters={"维度编号": "DIM-H03"}, keyword=None, status=None, page=1, size=20)
        assert total == 1
        row = items[0]
        assert "代理键操作员" in row["待领人"]
        assert row["可填写对象"].startswith("门店维度H03")
        assert row["办理提示"] == "待领取"


class TestClaimExclusive:
    """两个窗口同时提交领取：只有一个取得填写资格，另一个看到谁已领取。"""

    def test_second_claim_sees_claimer(self, dim, handoff):
        _submit_dim(dim, "DIM-H10", "客户维度H10")
        receipt = _receipts_of("DIM-H10")[0]
        entry, msg = handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        assert entry is not None and entry["status"] == "已领取"
        # 另一窗口再领：失败且指名已领取人
        entry2, msg2 = handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·钱")
        assert entry2 is None
        assert "代理键操作员·赵" in msg2
        assert "未取得填写资格" in msg2

    def test_concurrent_claim_only_one_wins(self, dim, handoff):
        _submit_dim(dim, "DIM-H11", "客户维度H11")
        receipt = _receipts_of("DIM-H11")[0]
        results: list[tuple[bool, str]] = []

        def claim(operator: str):
            entry, msg = handoff.run_action(receipt["id"], "领取交接", remark=operator)
            results.append((entry is not None, msg))

        threads = [
            threading.Thread(target=claim, args=("代理键操作员·赵",)),
            threading.Thread(target=claim, args=("代理键操作员·钱",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wins = [ok for ok, _ in results if ok]
        losses = [msg for ok, msg in results if not ok]
        assert len(wins) == 1 and len(losses) == 1
        assert "已被" in losses[0] and "领取" in losses[0]

    def test_claim_requires_listed_operator(self, dim, handoff):
        _submit_dim(dim, "DIM-H12", "客户维度H12")
        receipt = _receipts_of("DIM-H12")[0]
        entry, msg = handoff.run_action(receipt["id"], "领取交接", remark="外来人员")
        assert entry is None
        assert "不在待领人名单" in msg
        entry2, msg2 = handoff.run_action(receipt["id"], "领取交接")
        assert entry2 is None
        assert "需指定领取人" in msg2

    def test_claim_two_dims_independently(self, dim, handoff):
        """客户和门店各提交一笔：领客户不影响继续领门店。"""
        _submit_dim(dim, "DIM-H13A", "客户维度H13")
        _submit_dim(dim, "DIM-H13B", "门店维度H13")
        cust = _receipts_of("DIM-H13A")[0]
        shop = _receipts_of("DIM-H13B")[0]
        entry1, _ = handoff.run_action(cust["id"], "领取交接", remark="代理键操作员·赵")
        assert entry1 is not None
        # 另一窗口领客户失败，但继续领门店成功
        fail, msg = handoff.run_action(cust["id"], "领取交接", remark="代理键操作员·钱")
        assert fail is None and "代理键操作员·赵" in msg
        entry2, _ = handoff.run_action(shop["id"], "领取交接", remark="代理键操作员·钱")
        assert entry2 is not None and entry2["status"] == "已领取"
        # 客户最后只能存在一份可继续的分段登记
        assert len(_active_of("DIM-H13A")) == 1


class TestSegmentRegistration:
    """领取后继续对应维度的分段登记，键段同步到代理键生成。"""

    def test_segment_creates_key_range(self, dim, handoff):
        _submit_dim(dim, "DIM-H20", "门店维度H20")
        receipt = _receipts_of("DIM-H20")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        entry, msg = handoff.run_action(receipt["id"], "登记分段", remark="门店键段一段")
        assert entry is not None
        assert entry["status"] == "分段登记中"
        assert entry["分段进度"] == "已登记1段"
        segs = [r for r in store.rows("surrogate_key") if r.get("所属维度") == "门店维度H20"]
        assert len(segs) == 1
        assert segs[0]["status"] == "待分配"
        entry2, _ = handoff.run_action(receipt["id"], "登记分段", remark="门店键段二段")
        assert entry2["分段进度"] == "已登记2段"
        segs = [r for r in store.rows("surrogate_key") if r.get("所属维度") == "门店维度H20"]
        assert len(segs) == 2
        # 第二段起点接在第一段终点之后
        assert int(segs[1]["键段起点"]) == int(segs[0]["键段终点"]) + 1

    def test_segment_requires_claim_first(self, dim, handoff):
        _submit_dim(dim, "DIM-H21", "客户维度H21")
        receipt = _receipts_of("DIM-H21")[0]
        entry, msg = handoff.run_action(receipt["id"], "登记分段", remark="未领取先填")
        assert entry is None
        assert "不可登记分段" in msg

    def test_complete_handoff(self, dim, handoff):
        _submit_dim(dim, "DIM-H22", "客户维度H22")
        receipt = _receipts_of("DIM-H22")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        handoff.run_action(receipt["id"], "登记分段", remark="客户键段一段")
        entry, msg = handoff.run_action(receipt["id"], "完成交接")
        assert entry is not None and entry["status"] == "已完成"
        assert entry["pending"] is False


class TestReturnAndResubmit:
    """退回补正与补正重提：原回执留痕，不产生第二份有效待办。"""

    def test_return_marks_must_correct(self, dim, handoff):
        _submit_dim(dim, "DIM-H30", "客户维度H30")
        receipt = _receipts_of("DIM-H30")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        entry, msg = handoff.run_action(receipt["id"], "退回补正", remark="业务主键缺失")
        assert entry is not None and entry["status"] == "已退回"
        assert "值班员" in msg  # 退回原提交人
        row = handoff.get_entry(receipt["id"])
        assert row["办理提示"] == "必须先补正"
        # 已退回的回执不能再领取、不能登记分段
        fail1, m1 = handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·钱")
        assert fail1 is None and "必须先补正" in m1
        fail2, m2 = handoff.run_action(receipt["id"], "登记分段", remark="x")
        assert fail2 is None and "必须先补正" in m2

    def test_resubmit_via_dim_recreate_keeps_single_todo(self, dim, handoff):
        _submit_dim(dim, "DIM-H31", "客户维度H31")
        receipt = _receipts_of("DIM-H31")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        handoff.run_action(receipt["id"], "退回补正", remark="登记不完整")
        # 值班员补正后重提：同维度编号再次提交
        _submit_dim(dim, "DIM-H31", "客户维度H31")
        actives = _active_of("DIM-H31")
        assert len(actives) == 1  # 不产生第二份有效待办
        again = actives[0]
        assert again["id"] == receipt["id"]  # 仍是原回执
        assert again["status"] == "待领取"
        assert again["领取人"] == ""
        # 从原回执能找到历次交接
        history = again["交接履历"]
        assert any("领取交接" in h for h in history)
        assert any("退回" in h for h in history)
        assert any("补正重提" in h for h in history)

    def test_resubmit_action_on_receipt(self, dim, handoff):
        _submit_dim(dim, "DIM-H32", "客户维度H32")
        receipt = _receipts_of("DIM-H32")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        handoff.run_action(receipt["id"], "退回补正", remark="缺主题域")
        entry, msg = handoff.run_action(receipt["id"], "补正重提")
        assert entry is not None and entry["status"] == "待领取"
        assert len(_active_of("DIM-H32")) == 1

    def test_segment_notes_reusable_when_structure_unchanged(self, dim, handoff):
        """补正未动结构字段：刚填的分段说明可沿用到补正后的下一轮。"""
        _submit_dim(dim, "DIM-H33", "客户维度H33")
        receipt = _receipts_of("DIM-H33")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        handoff.run_action(receipt["id"], "登记分段", remark="客户键段一段")
        handoff.run_action(receipt["id"], "退回补正", remark="主题域写错")
        # 补正只改主题域（非结构字段）
        entry, _ = dim.create_entry({
            "维度编号": "DIM-H33", "维度名称": "客户维度H33", "业务主键": "biz_key",
            "自然键来源": "ERP", "维度类型": "SCD2", "所属主题域": "客户",
            "生效标记": "待生效", "登记时间": "2026-11-26",
        })
        again = _active_of("DIM-H33")[0]
        assert again["沿用标记"] == "可沿用"
        assert again["分段进度"] == "已登记1段"
        assert again["分段说明列表"]  # 分段说明保留

    def test_segment_notes_invalidated_when_structure_changed(self, dim, handoff):
        """补正改了业务主键：补正前分段说明需重填，但已分配键段继续可用。"""
        _submit_dim(dim, "DIM-H34", "门店维度H34")
        receipt = _receipts_of("DIM-H34")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        handoff.run_action(receipt["id"], "登记分段", remark="门店键段一段")
        handoff.run_action(receipt["id"], "退回补正", remark="业务主键不对")
        dim.create_entry({
            "维度编号": "DIM-H34", "维度名称": "门店维度H34", "业务主键": "store_code",
            "自然键来源": "ERP", "维度类型": "SCD2", "所属主题域": "测试",
            "生效标记": "待生效", "登记时间": "2026-11-26",
        })
        again = _active_of("DIM-H34")[0]
        assert again["沿用标记"] == "需重填"
        assert again["分段进度"] == "已登记0段"
        assert again["分段说明列表"] == []
        # 补正前的分段说明在履历里留痕
        assert any("作废" in h for h in again["交接履历"])
        # 已经分配的门店键段继续可用
        segs = [r for r in store.rows("surrogate_key") if r.get("所属维度") == "门店维度H34"]
        assert len(segs) == 1
        # 下一轮重新领取后可继续分段，新键段接在旧段之后
        handoff.run_action(again["id"], "领取交接", remark="代理键操作员·钱")
        entry, _ = handoff.run_action(again["id"], "登记分段", remark="补正后门店键段")
        assert entry["status"] == "分段登记中"
        segs = [r for r in store.rows("surrogate_key") if r.get("所属维度") == "门店维度H34"]
        assert len(segs) == 2
        assert int(segs[1]["键段起点"]) == int(segs[0]["键段终点"]) + 1

    def test_full_customer_journey_single_active_registration(self, dim, handoff):
        """客户维度全旅程：提交→领取→分段→退回→补正重提→再领取→完成，
        全程只有一份可继续的分段登记。"""
        _submit_dim(dim, "DIM-H35", "客户维度H35")
        receipt = _receipts_of("DIM-H35")[0]
        handoff.run_action(receipt["id"], "领取交接", remark="代理键操作员·赵")
        handoff.run_action(receipt["id"], "登记分段", remark="客户键段一段")
        handoff.run_action(receipt["id"], "退回补正", remark="自然键来源待确认")
        _submit_dim(dim, "DIM-H35", "客户维度H35")
        assert len(_active_of("DIM-H35")) == 1
        again = _active_of("DIM-H35")[0]
        assert again["沿用标记"] == "可沿用"
        handoff.run_action(again["id"], "领取交接", remark="代理键操作员·钱")
        handoff.run_action(again["id"], "登记分段", remark="客户键段二段")
        entry, _ = handoff.run_action(again["id"], "完成交接")
        assert entry["status"] == "已完成"
        assert len(_active_of("DIM-H35")) == 0
        # 回执履历完整记录历次交接
        history = entry["交接履历"]
        for keyword in ("生成交接回执", "领取交接", "登记分段", "退回", "补正重提", "完成交接"):
            assert any(keyword in h for h in history), keyword
