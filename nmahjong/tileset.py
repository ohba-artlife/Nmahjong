"""牌表 tileset（nmahjong-tileset 1.0）— 生成・検証・id・表示名。仕様 tileset.md。"""
import json
import os
import re
from typing import Dict, Iterable, List, Optional

from .canon import ValidationError, sha256_id, id_hex64

FORMAT = "nmahjong-tileset"
VERSION = "1.0"

SUITS = "mps"
HONORS = ["E", "S", "W", "N", "P", "F", "C"]
NUM_KINDS = [f"{n}{s}" for s in SUITS for n in range(1, 10)]
KINDS = set(NUM_KINDS) | set(HONORS) | {"ex"}
COPIES = 4
COUNT_PER_COLOR = {"m": 36, "p": 36, "s": 36, "z": 28}
NAME_RE = re.compile(r"^(m?p?s?z?)(?:-x(\d+))?(?:-e(\d+))?$")

# mjai の文字表記（表示・読み込み用）
_HONOR_Z = {"E": "1z", "S": "2z", "W": "3z", "N": "4z", "P": "5z", "F": "6z", "C": "7z"}
_Z_HONOR = {v: k for k, v in _HONOR_Z.items()}


def parse_name(name: str):
    """name → (colors, x, e)。不正なら ValidationError。"""
    m = NAME_RE.match(name or "")
    if not m or not m.group(1):
        raise ValidationError(f"牌表の name が不正: {name!r}（{{色}}[-x枚数][-e枚数]）")
    colors, x, e = m.group(1), int(m.group(2) or 0), int(m.group(3) or 0)
    return colors, x, e


def expected_count(name: str) -> int:
    colors, x, e = parse_name(name)
    return sum(COUNT_PER_COLOR[c] for c in colors) - x + e


def full_kinds(colors: str) -> List[str]:
    kinds: List[str] = []
    for c in colors:
        if c in SUITS:
            kinds += [f"{n}{c}" for n in range(1, 10)]
        elif c == "z":
            kinds += HONORS
    return kinds


def build(name: str, exclude_kinds: Iterable[str] = (), marks: Optional[Dict[int, str]] = None,
          extras: Iterable[str] = (), mark_by_kind: Optional[Dict[str, List[str]]] = None) -> dict:
    """牌表を作る。

    name: `mpsz`、`mpsz-x28` など。x・e の枚数は exclude_kinds／extras と一致していなければならない
    exclude_kinds: 除く牌種（各 4 枚除く）。例 三麻 ["2m",…,"8m"]
    marks: {番号: 印}（番号は除外・詰め後の番号）
    mark_by_kind: {"5m": ["red"]} のように牌種ごとに「枚目 0 から順に」印を付ける（番号を数えずに済む）
    extras: エクストラの名前の列（kind "ex"）。1 要素 1 枚
    """
    colors, x, e = parse_name(name)
    ex_set = set(exclude_kinds)
    tiles = []
    for kind in full_kinds(colors):
        if kind in ex_set:
            continue
        for copy in range(COPIES):
            t = {"id": len(tiles), "kind": kind}
            if mark_by_kind and kind in mark_by_kind and copy < len(mark_by_kind[kind]):
                t["mark"] = mark_by_kind[kind][copy]
            tiles.append(t)
    for nm in extras:
        tiles.append({"id": len(tiles), "kind": "ex", "name": nm})
    if marks:
        for tid, mk in marks.items():
            tiles[tid]["mark"] = mk
    if len(ex_set) * COPIES != x:
        raise ValidationError(f"name の x={x} と除外 {len(ex_set)}種×4 が合わない")
    if len(list(extras)) != e:
        raise ValidationError(f"name の e={e} とエクストラ {len(list(extras))} 枚が合わない")
    ts = {"format": FORMAT, "version": VERSION, "name": name, "tiles": tiles}
    ts["id"] = compute_id(ts)
    return ts


def compute_id(ts: dict) -> str:
    return sha256_id(ts["tiles"])


def validate(ts: dict) -> List[str]:
    """tileset.md §5。戻り値は警告の列（エラーは ValidationError）。"""
    warnings: List[str] = []
    if ts.get("format") != FORMAT:
        raise ValidationError(f"format が {FORMAT} ではない: {ts.get('format')!r}")
    if ts.get("version") != VERSION:
        raise ValidationError(f"version が {VERSION} ではない: {ts.get('version')!r}")
    tiles = ts.get("tiles")
    if not isinstance(tiles, list):
        raise ValidationError("tiles が配列ではない")
    K = len(tiles)
    if not (1 <= K <= 256):
        raise ValidationError(f"K={K} は 1〜256 の外")
    for i, t in enumerate(tiles):
        if not isinstance(t, dict) or t.get("id") != i:
            raise ValidationError(f"tiles[{i}].id が連番ではない: {t!r}")
        if t.get("kind") not in KINDS:
            raise ValidationError(f"tiles[{i}].kind が語彙外: {t.get('kind')!r}")
        for k in ("mark", "name"):
            if k in t and not isinstance(t[k], str):
                raise ValidationError(f"tiles[{i}].{k} が文字列ではない")
        extra = set(t) - {"id", "kind", "mark", "name"}
        if extra:
            raise ValidationError(f"tiles[{i}] に未知の項目: {sorted(extra)}")
    exp = expected_count(ts.get("name", ""))
    if exp != K:
        raise ValidationError(f"name {ts.get('name')!r} から計算した枚数 {exp} ≠ K={K}")
    id_hex64(ts.get("id", ""))
    if ts["id"] != compute_id(ts):
        raise ValidationError("id が tiles のハッシュと一致しない")
    extra = set(ts) - {"format", "version", "name", "id", "tiles"}
    if extra:
        raise ValidationError(f"未知の項目: {sorted(extra)}")
    return warnings


def filename(ts: dict) -> str:
    return f"{ts['name']}_{id_hex64(ts['id'])}.tileset.json"


def ref(ts: dict) -> dict:
    return {"name": ts["name"], "id": ts["id"]}


def K(ts: dict) -> int:
    return len(ts["tiles"])


# ---- 表示名 ------------------------------------------------------------------

def tile_label(ts: dict, tid: int, style: str = "mjai") -> str:
    """番号 → 文字。style: mjai（5mr, E…）／z（0m, 1z…）。印は red のときだけ mjai の r／z の 0 に写す。"""
    t = ts["tiles"][tid]
    kind, mark = t["kind"], t.get("mark")
    if kind == "ex":
        return "ex:" + t.get("name", str(tid))
    if style == "z":
        if kind in _HONOR_Z:
            return _HONOR_Z[kind]
        return ("0" + kind[1]) if mark == "red" and kind[0] == "5" else kind
    return kind + ("r" if mark == "red" and kind[0] == "5" else "")


def parse_label(ts: dict, label: str) -> List[int]:
    """文字 → 候補番号の列（同じ種類の全個体）。'5mr'／'0m' は赤個体だけ。"""
    s = label.strip()
    red = False
    if s in _Z_HONOR:
        kind = _Z_HONOR[s]
    elif len(s) == 2 and s[0] == "0" and s[1] in SUITS:
        kind, red = "5" + s[1], True
    elif len(s) == 3 and s.endswith("r"):
        kind, red = s[:2], True
    else:
        kind = s
    if kind not in KINDS:
        raise ValidationError(f"牌の表記が不正: {label!r}")
    out = [t["id"] for t in ts["tiles"] if t["kind"] == kind and (not red or t.get("mark") == "red")]
    if not out:
        raise ValidationError(f"牌表に無い牌: {label!r}")
    return out


# ---- 同梱の牌表 ----------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "tilesets")


def bundled() -> List[dict]:
    out = []
    if os.path.isdir(_DATA_DIR):
        for fn in sorted(os.listdir(_DATA_DIR)):
            if fn.endswith(".tileset.json"):
                with open(os.path.join(_DATA_DIR, fn), encoding="utf-8") as f:
                    out.append(json.load(f))
    return out


def find(name: Optional[str] = None, id: Optional[str] = None, search_dirs: Iterable[str] = ()) -> dict:
    """id（正）または name で牌表を探す。同梱 → search_dirs の順。name だけで複数あれば ValidationError。"""
    cands = list(bundled())
    for d in search_dirs:
        if d and os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.endswith(".tileset.json"):
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        cands.append(json.load(f))
    if id:
        for ts in cands:
            if ts.get("id") == id:
                return ts
        raise ValidationError(f"牌表 id {id} が見つからない")
    # 同梱の別名（mpsz-nored 等）。別名は定義の鍵で、name とは別
    defs = bundled_definitions()
    if name in defs and name != defs[name]["name"]:
        return build(**defs[name])
    hits = [ts for ts in cands if ts.get("name") == name]
    if not hits:
        raise ValidationError(f"牌表 name {name!r} が見つからない")
    ids = {ts["id"] for ts in hits}
    if len(ids) > 1:
        # 同梱の既定（定義の鍵 == name のもの）があればそれ。赤 3 枚入りが既定
        if name in defs:
            return build(**defs[name])
        raise ValidationError(f"牌表 name {name!r} は複数ある（id で指定）: " + ", ".join(sorted(ids)))
    return hits[0]


def bundled_definitions() -> Dict[str, dict]:
    """同梱牌表の定義（build の引数）。ファイル生成と試験で共有する。"""
    red3 = {"5m": ["red"], "5p": ["red"], "5s": ["red"]}
    sanma_ex = [f"{n}m" for n in range(2, 9)]
    return {
        "mpsz": dict(name="mpsz", mark_by_kind=red3),                       # 天鳳の 0〜135、赤 16・52・88
        "mpsz-nored": dict(name="mpsz"),                                      # 赤なし（競技ルール用）
        "mpsz-x28": dict(name="mpsz-x28", exclude_kinds=sanma_ex, mark_by_kind=red3),  # 三麻（2m〜8m 除外）
        "mpsz-x28-nored": dict(name="mpsz-x28", exclude_kinds=sanma_ex),
        "mpsz-x28-allred": dict(name="mpsz-x28", exclude_kinds=sanma_ex,
                                mark_by_kind={"5p": ["red"] * 4, "5s": ["red"] * 4}),    # 関西の三麻（5 筒・5 索が全部赤）
        "m": dict(name="m", mark_by_kind={"3m": ["red"], "5m": ["red"], "7m": ["red"]}),  # 4 枚麻雀の別版 nm-2p-4-room（赤 3・5・7）
        "m-nored": dict(name="m"),                                            # N 枚麻雀 nm-2p-*-m（萬子、赤なし）
        "mps": dict(name="mps"),
        "mpsz-pocchi": dict(name="mpsz", mark_by_kind={"5m": ["red", "gold"], "5p": ["red", "gold"], "5s": ["red", "gold"],
                                                        "P": ["pocchi", "reverse_pocchi"]}),   # 赤 3 金 3 白ポッチ 逆ポッチ
        "mpsz-e8": dict(name="mpsz-e8", mark_by_kind=red3,
                        extras=["梅", "蘭", "菊", "竹", "春", "夏", "秋", "冬"]),  # 花牌 8 枚の例
    }
