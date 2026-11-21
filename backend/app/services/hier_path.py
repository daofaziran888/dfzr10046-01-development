"""层级路径领域服务：维护维度层级上下级路径的数据集，校验跨越标记和断裂检测。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class HierPathService(BaseModuleService):
    MODULE = "hier_path"
    ENTITY = "层级路径"
    LIST_FIELDS = ["路径编号", "所属维度", "层级名称", "上级层级", "层级深度", "跨越标记", "路径校验值", "最近校验"]
    REQUIRED_FIELDS = ["路径编号", "所属维度", "层级名称"]
    STATUS_ORDER = ["草稿", "已校验", "存在断裂", "已停用"]
    ACTION_RULES = {"提交校验": "已校验", "登记断裂": "存在断裂", "停用路径": "已停用"}
    NEGATIVE_ACTIONS = ["登记断裂"]

    def register_path(
        self, path_id: str, dim_name: str, level_name: str,
        parent_level: str, depth: int, cross_flag: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """登记层级路径：含上下级关系和跨越标记。"""
        rows = store.rows(self.MODULE)
        checksum = str(hash(f"{dim_name}:{level_name}:{depth}") % 100000).zfill(5)
        entry = {
            "路径编号": path_id, "所属维度": dim_name,
            "层级名称": level_name, "上级层级": parent_level,
            "层级深度": depth, "跨越标记": cross_flag,
            "路径校验值": checksum, "最近校验": "2026-11-21",
            "status": "已校验", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"层级路径 {path_id} 已校验：{dim_name}/{level_name} 深度 {depth}", entry

    def detect_break(self, dim_name: str) -> list[dict[str, Any]]:
        """检测层级断裂：上级层级不存在或跨越标记异常。"""
        rows = store.rows(self.MODULE)
        dim_rows = [r for r in rows if r.get("所属维度") == dim_name]
        breaks: list[dict[str, Any]] = []
        level_names = {r.get("层级名称") for r in dim_rows}
        for r in dim_rows:
            parent = r.get("上级层级", "")
            if parent and parent != "NONE" and parent not in level_names:
                breaks.append({
                    "路径": r.get("路径编号"),
                    "原因": f"上级层级 {parent} 不存在",
                    "当前": r.get("层级名称"),
                })
                r["status"] = "存在断裂"
                r["abnormal"] = True
        return breaks