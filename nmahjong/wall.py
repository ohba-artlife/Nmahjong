"""牌山 wall（nmahjong-wall 1.0）— 生成・再現・埋め・検証・id。仕様 wall.md。"""
import hashlib
import struct
from typing import Dict, Iterator, List, Optional

from . import tileset as TS
from .canon import ValidationError, id_hex64
from .tenhou import shuffle as tenhou

FORMAT = "nmahjong-wall"
VERSION = "1.0"
FY = "fy-sha256-v1"
SOURCES = ("generated", "observed", "filled")


# ---- fy-sha256-v1 ---------------------------------------------------------------

def rand_stream(seed: str) -> Iterator[int]:
    """SHA-256(seed_utf8 ‖ counter 4byte big-endian) → 32bit big-endian × 8 の列。尽きたらカウンタ +1。"""
    s = seed.encode("utf-8")
    i = 0
    while True:
        h = hashlib.sha256(s + struct.pack(">I", i)).digest()
        i += 1
        for k in range(0, 32, 4):
            yield struct.unpack(">I", h[k:k + 4])[0]


def fy_sha256_v1(items: List[int], seed: str) -> List[int]:
    """items のコピーを Fisher–Yates（i = K-1 … 1、棄却法）で並べ替える。"""
    order = list(items)
    r = rand_stream(seed)
    for i in range(len(order) - 1, 0, -1):
        bound = i + 1
        limit = (2 ** 32 // bound) * bound
        while True:
            x = next(r)
            if x < limit:
                break
        j = x % bound
        order[i], order[j] = order[j], order[i]
    return order


def compute_id(order: List[int], tileset_id: str) -> str:
    """id = SHA-256( 牌表 id の 32 バイト ‖ order を 1 牌 1 バイトにした列 )。
    牌表が違えば同じ並びでも別の id になる（赤あり mpsz と赤なし mpsz の衝突を防ぐ）。"""
    return "sha256:" + hashlib.sha256(bytes.fromhex(id_hex64(tileset_id)) + bytes(order)).hexdigest()


# ---- 生成 ------------------------------------------------------------------------

def build(ts: dict, seed: str, meta: Optional[dict] = None) -> dict:
    """fy-sha256-v1 で牌山を生成する（source generated）。"""
    K = TS.K(ts)
    order = fy_sha256_v1(list(range(K)), seed)
    w = {"format": FORMAT, "version": VERSION, "tileset": TS.ref(ts), "source": "generated",
         "generation": {"method": FY, "seed": seed}, "order": order, "id": compute_id(order, ts["id"])}
    if meta:
        w["meta"] = meta
    return w


def build_tenhou(ts: dict, seed_attr: str, round_index: int, oya: int,
                 players: int = 4, hand: int = 13, meta: Optional[dict] = None) -> dict:
    """天鳳 seed から局 round_index の山を再現する（source observed、generation 付き）。"""
    K = TS.K(ts)
    if players == 4 and K != 136:
        raise ValidationError("天鳳四麻の再現は K=136 の牌表（mpsz）だけ")
    if players == 3 and K != 108:
        raise ValidationError("天鳳三麻の再現は K=108 の牌表（mpsz-x28）だけ")
    yama, _dice = tenhou.tenhou_wall(seed_attr, round_index, players)
    order = tenhou.to_nm1(yama, oya, players, hand)
    if players == 3:
        order = [tenhou.tenhou_to_x28(t) for t in order]
    w = {"format": FORMAT, "version": VERSION, "tileset": TS.ref(ts), "source": "observed",
         "generation": {"method": tenhou.METHOD, "seed": seed_attr, "round": round_index,
                        "oya": oya, "players": players, "hand": hand},
         "order": order, "id": compute_id(order, ts["id"])}
    if meta:
        w["meta"] = meta
    return w


def build_filled(ts: dict, placed: Dict[int, int], fill_seed: str, meta: Optional[dict] = None) -> dict:
    """見えた位置 placed（位置→番号）を事実とし、残りを fill で埋める（source filled）。"""
    K = TS.K(ts)
    for pos, tid in placed.items():
        if not (0 <= pos < K and 0 <= tid < K):
            raise ValidationError(f"placed の位置または番号が範囲外: {pos}:{tid}")
    seen = set(placed.values())
    if len(seen) != len(placed):
        raise ValidationError("placed に同じ番号が 2 回ある")
    order = fill(K, placed, fill_seed)
    w = {"format": FORMAT, "version": VERSION, "tileset": TS.ref(ts), "source": "filled",
         "observed": _ranges(sorted(placed)), "fill": {"method": FY, "seed": fill_seed},
         "order": order, "id": compute_id(order, ts["id"])}
    if meta:
        w["meta"] = meta
    return w


# ---- 実卓（タグ id の列 → 牌番号 → observed） --------------------------------------------------

TAGMAP_FORMAT = "nmahjong-tagmap"


def validate_tagmap(tm: dict, ts: Optional[dict] = None) -> None:
    """対応表 {format, version, tileset{name,id}, tags{タグ文字列: 牌番号}}。牌番号は重複せず 0〜K−1。"""
    if not isinstance(tm, dict) or tm.get("format") != TAGMAP_FORMAT:
        raise ValidationError("format が nmahjong-tagmap ではない")
    if not isinstance(tm.get("tags"), dict) or not tm["tags"]:
        raise ValidationError("tags が空")
    seen: Dict[int, str] = {}
    for tag, tid in tm["tags"].items():
        if not isinstance(tag, str) or not tag:
            raise ValidationError("タグは空でない文字列")
        if not isinstance(tid, int) or isinstance(tid, bool) or tid < 0:
            raise ValidationError(f"タグ {tag} の牌番号が不正: {tid!r}")
        if tid in seen:
            raise ValidationError(f"牌番号 {tid} にタグが 2 つ（{seen[tid]}, {tag}）")
        seen[tid] = tag
    if ts is not None:
        if tm.get("tileset", {}).get("id") != ts["id"]:
            raise ValidationError("tagmap.tileset.id が牌表と違う")
        K = TS.K(ts)
        if len(tm["tags"]) != K:
            raise ValidationError(f"タグの数 {len(tm['tags'])} ≠ K {K}（全牌にタグが要る）")
        if any(t >= K for t in seen):
            raise ValidationError("牌番号が K 以上")


def build_observed(ts: dict, order: List[int], device: Optional[dict] = None, meta: Optional[dict] = None) -> dict:
    """実卓などが読んだ並び（牌番号の順列）→ wall（source observed、generation なし）。"""
    K = TS.K(ts)
    if sorted(order) != list(range(K)):
        raise ValidationError(f"order が 0〜{K-1} の順列ではない")
    w = {"format": FORMAT, "version": VERSION, "tileset": TS.ref(ts), "source": "observed", "order": list(order)}
    if device:
        w["device"] = device
    w["id"] = compute_id(w["order"], ts["id"])
    if meta:
        w["meta"] = meta
    return w


def build_from_tags(ts: dict, tagmap: dict, tags: List[str], device: Optional[dict] = None, meta: Optional[dict] = None) -> dict:
    """卓が読んだタグ id の列（消費順：先頭が最初に取られる牌）→ 対応表で牌番号に → observed の wall。
    タグが未知・重複・不足ならエラー（部分観測は build_filled を使う）。"""
    validate_tagmap(tagmap, ts)
    order = []
    for i, tag in enumerate(tags):
        if tag not in tagmap["tags"]:
            raise ValidationError(f"{i} 番目のタグ {tag!r} が対応表に無い")
        order.append(tagmap["tags"][tag])
    if len(order) != TS.K(ts):
        raise ValidationError(f"タグの列 {len(order)} 個 ≠ K {TS.K(ts)}")
    if len(set(order)) != len(order):
        raise ValidationError("同じ牌が 2 回読まれている")
    return build_observed(ts, order, device, meta)


def fill(K: int, placed: Dict[int, int], fill_seed: str) -> List[int]:
    """wall.md §5：見えなかった牌を番号昇順 → fy で並べ替え → 空き位置を昇順に詰める。"""
    unseen = sorted(set(range(K)) - set(placed.values()))
    shuffled = fy_sha256_v1(unseen, fill_seed)
    order = [-1] * K
    for pos, tid in placed.items():
        order[pos] = tid
    it = iter(shuffled)
    for pos in range(K):
        if order[pos] < 0:
            order[pos] = next(it)
    return order


def _ranges(positions: List[int]) -> List[List[int]]:
    """昇順の位置列 → 半開区間 [start, end) の列（結合済み）。"""
    out: List[List[int]] = []
    for p in positions:
        if out and out[-1][1] == p:
            out[-1][1] = p + 1
        else:
            out.append([p, p + 1])
    return out


def observed_positions(ranges: List[List[int]]) -> List[int]:
    pos: List[int] = []
    for r in ranges:
        pos += range(r[0], r[1])
    return pos


# ---- 検証 ------------------------------------------------------------------------

def reproduce(w: dict) -> List[int]:
    """generation から order を再構築する。"""
    g = w["generation"]
    K = len(w["order"])
    if g.get("method") == FY:
        return fy_sha256_v1(list(range(K)), g["seed"])
    if g.get("method") == tenhou.METHOD:
        players = int(g.get("players", 4))
        yama, _ = tenhou.tenhou_wall(g["seed"], int(g["round"]), players)
        order = tenhou.to_nm1(yama, int(g["oya"]), players, int(g.get("hand", 13)))
        return [tenhou.tenhou_to_x28(t) for t in order] if players == 3 else order
    raise ValidationError(f"未知の生成法: {g.get('method')!r}")


def validate(w: dict, ts: Optional[dict] = None) -> List[str]:
    """wall.md §7。ts を渡せば K と tileset.id を照合する。戻り値は警告（エラーは ValidationError）。"""
    warnings: List[str] = []
    if w.get("format") != FORMAT:
        raise ValidationError(f"format が {FORMAT} ではない: {w.get('format')!r}")
    if w.get("version") != VERSION:
        raise ValidationError(f"version が {VERSION} ではない: {w.get('version')!r}")
    tref = w.get("tileset")
    if not isinstance(tref, dict) or "name" not in tref or "id" not in tref:
        raise ValidationError("tileset が {name, id} ではない")
    id_hex64(tref["id"])
    order = w.get("order")
    if not isinstance(order, list) or not order:
        raise ValidationError("order が空か配列ではない")
    K = len(order)
    if ts is not None:
        if ts["id"] != tref["id"]:
            raise ValidationError("tileset.id が渡された牌表と一致しない")
        if TS.K(ts) != K:
            raise ValidationError(f"order の長さ {K} ≠ 牌表の K {TS.K(ts)}")
    if any(not isinstance(x, int) or isinstance(x, bool) for x in order):
        raise ValidationError("order に整数以外がある")
    if sorted(order) != list(range(K)):
        raise ValidationError("order が 0〜K-1 の順列ではない")
    src = w.get("source")
    if src not in SOURCES:
        raise ValidationError(f"source が語彙外: {src!r}")
    has = {k: (k in w) for k in ("generation", "observed", "fill", "device")}
    rule = {"generated": dict(generation=True, observed=False, fill=False, device=False),
            "observed": dict(generation=None, observed=False, fill=False, device=None),
            "filled": dict(generation=False, observed=True, fill=True, device=False)}[src]
    for k, req in rule.items():
        if req is True and not has[k]:
            raise ValidationError(f"source={src} では {k} が必須")
        if req is False and has[k]:
            raise ValidationError(f"source={src} では {k} は書けない")
    if has["generation"]:
        if reproduce(w) != order:
            raise ValidationError("generation から再構築した order と一致しない")
    if has["observed"]:
        rng = w["observed"]
        last = -1
        for r in rng:
            if not (isinstance(r, list) and len(r) == 2 and 0 <= r[0] < r[1] <= K and r[0] > last):
                raise ValidationError(f"observed の区間が不正: {r!r}")
            last = r[1]
        placed = {p: order[p] for p in observed_positions(rng)}
        if has["fill"]:
            if w["fill"].get("method") != FY:
                raise ValidationError(f"fill.method が {FY} ではない")
            if fill(K, placed, w["fill"]["seed"]) != order:
                raise ValidationError("fill を再実行した order と一致しない")
    if has["device"]:
        d = w["device"]
        if not isinstance(d, dict) or not isinstance(d.get("id"), str):
            raise ValidationError("device.id が文字列ではない")
        extra = set(d) - {"id", "maker", "model", "firmware", "at"}
        if extra:
            raise ValidationError(f"device に未知の項目: {sorted(extra)}")
    if w.get("id") != compute_id(order, tref["id"]):
        raise ValidationError("id が order のハッシュと一致しない")
    extra = set(w) - {"format", "version", "tileset", "source", "generation", "observed", "fill", "device", "order", "id", "meta"}
    if extra:
        raise ValidationError(f"未知の項目: {sorted(extra)}")
    return warnings


def filename(w: dict) -> str:
    return f"{w['tileset']['name']}_{id_hex64(w['id'])}.wall.json"


# ---- 表現 ------------------------------------------------------------------------

def to_bytes(order: List[int]) -> bytes:
    return bytes(order)


def to_csv(order: List[int]) -> str:
    return ",".join(map(str, order))


def from_bytes(b: bytes) -> List[int]:
    return list(b)


def from_csv(s: str) -> List[int]:
    return [int(x) for x in s.strip().split(",") if x.strip() != ""]
