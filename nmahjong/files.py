"""ファイルの読み書き（overview.md §4：同名で中身の id が違えば上書きしない）。"""
import json
import os
from typing import Any, Optional

from .canon import ValidationError


def load(path: str) -> Any:
    if path == "-":
        import sys
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dumps(obj: Any, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def save(obj: Any, directory: str, filename: str, pretty: bool = True) -> str:
    """directory/filename に書く。既にあり中身の id が違えば ValidationError（上書きしない）。"""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    if os.path.exists(path):
        try:
            old = load(path)
        except Exception:
            old = None
        if not (isinstance(old, dict) and old.get("id") == obj.get("id")):
            raise ValidationError(f"同名ファイルがあり id が違う（上書きしない）: {path}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(obj, pretty))
    return path


def detect_format(obj: Any) -> Optional[str]:
    if isinstance(obj, dict) and isinstance(obj.get("format"), str) and obj["format"].startswith("nmahjong-"):
        return obj["format"][len("nmahjong-"):]
    return None
