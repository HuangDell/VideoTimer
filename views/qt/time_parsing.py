"""Time parsing helpers for editable interval cells."""
from __future__ import annotations

def parse_time_text(text: str) -> float:
    parts = text.strip().split(":")
    if len(parts) == 1:
        try:
            return max(0.0, float(parts[0]))
        except ValueError as exc:
            raise ValueError("请输入秒数或 HH:MM:SS.mmm") from exc
    if len(parts) != 3:
        raise ValueError("请输入 HH:MM:SS.mmm")
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError as exc:
        raise ValueError("请输入 HH:MM:SS.mmm") from exc
    if hours < 0 or minutes < 0 or seconds < 0:
        raise ValueError("时间不能为负数")
    return hours * 3600 + minutes * 60 + seconds
