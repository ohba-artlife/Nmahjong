"""正規化 JSON と id（SHA-256）。

正規化＝キー辞書順・区切りは "," と ":" のみ（空白なし）・UTF-8・非 ASCII はそのまま。
全層の id はこの関数で作る（牌山の id だけは 牌表 id ‖ order のバイト列から作る）。
"""
import hashlib
import json
from typing import Any


class ValidationError(Exception):
    """検証失敗。message は人が読む 1 行。"""


def _norm_numbers(obj: Any) -> Any:
    """整数値の浮動小数（49.0）は整数（49）として書く。JS の JSON.stringify と同じ表現にするため。"""
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError("NaN／Infinity は JSON にできない")
        return int(obj) if obj.is_integer() else obj
    if isinstance(obj, dict):
        return {k: _norm_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_norm_numbers(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> bytes:
    """キー辞書順・空白なし・非 ASCII そのまま・整数値の小数は整数で。Python と JS で同じバイト列になる。"""
    return json.dumps(_norm_numbers(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_id(obj: Any) -> str:
    """'sha256:' + 正規化 JSON の SHA-256（16 進 64 桁）。"""
    return "sha256:" + sha256_hex(canonical_json(obj))


def id_hex64(id_str: str) -> str:
    """'sha256:…' から 64 桁だけを取り出す。形式が違えば ValidationError。"""
    if not isinstance(id_str, str) or not id_str.startswith("sha256:"):
        raise ValidationError(f"id は 'sha256:' で始まる文字列: {id_str!r}")
    h = id_str[7:]
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise ValidationError(f"id の 16 進 64 桁が不正: {id_str!r}")
    return h


def without(obj: dict, *keys: str) -> dict:
    return {k: v for k, v in obj.items() if k not in keys}
