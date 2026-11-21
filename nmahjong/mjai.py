"""record ⇄ mjai イベント列（observation.md）。mjai を正とし、拡張は tile・ruleset・request_action の 3 点。

to_mjai(rec, rs, ts, walls, seat=None) → JSON にできる dict の列（1 要素＝1 行）。seat を与えると他家の手牌・ツモは "?"。
from_mjai_action(resp, ts, obs)       → annotation 2.3.1 の行動（mjai 応答 dahai/chi/pon/daiminkan/kakan/ankan/reach/hora/none/ryukyoku）。
"""
from typing import Dict, List, Optional

from . import observe as O
from . import ruleset as R
from . import tileset as TS
from .canon import ValidationError

BAKAZE = {"E": "E", "S": "S", "W": "W", "N": "N"}


def _pai(ts: dict, tid: Optional[int]) -> str:
    if tid is None:
        return "?"
    try:
        return TS.tile_label(ts, tid, "mjai")
    except Exception:
        return "?"


def _ev(**kw) -> dict:
    return {k: v for k, v in kw.items() if v is not None}


def to_mjai(rec: dict, rs: dict, ts: dict, walls: Optional[Dict[str, dict]] = None, seat: Optional[int] = None) -> List[dict]:
    norm = R.normalize(rs)
    M, N = norm["players"], norm["hand_size"]
    out: List[dict] = []
    names = [p.get("name", f"seat{p['seat']}") for p in sorted(rec["players"], key=lambda p: p["seat"])]
    out.append(_ev(type="start_game", id=rec.get("id"), names=names, ruleset={"name": rs.get("name"), "id": rs.get("id")}))
    for rnd in rec["rounds"]:
        st = rnd["state"]
        wall = (walls or {}).get(rnd["wall"]["id"]) if rnd.get("wall") else None
        hands = O._initial_hands(rnd, norm, wall)
        evs = rnd["events"]
        dora0 = next((e["tile"] for e in evs if e["t"] == "dora"), None)
        tehais = []
        for s in range(M):
            if seat is None or s == seat:
                tehais.append([_pai(ts, t) for t in hands[s]])
            else:
                tehais.append(["?"] * N)
        out.append(_ev(type="start_kyoku", bakaze=st["bakaze"], kyoku=st["kyoku"], honba=st["honba"], kyotaku=st["kyotaku"],
                       oya=st["oya"], dora_marker=_pai(ts, dora0), tehais=tehais, scores=list(st["scores"]),
                       tiles=[list(hands[s]) if (seat is None or s == seat) else None for s in range(M)]))
        last_discard = None
        riichi_pending = None
        first_dora = True
        for e in evs:
            t = e["t"]
            if t == "deal":
                continue
            if t == "dora":
                if first_dora:
                    first_dora = False
                    continue
                out.append(_ev(type="dora", dora_marker=_pai(ts, e["tile"]), tile=e["tile"]))
            elif t == "draw":
                hidden = seat is not None and e["who"] != seat
                out.append(_ev(type="tsumo", actor=e["who"], pai="?" if hidden else _pai(ts, e["tile"]),
                               tile=None if hidden else e["tile"]))
            elif t == "discard":
                out.append(_ev(type="dahai", actor=e["who"], pai=_pai(ts, e["tile"]), tile=e["tile"], tsumogiri=bool(e.get("tsumogiri"))))
                if riichi_pending == e["who"] or e.get("riichi"):
                    out.append(_ev(type="reach_accepted", actor=e["who"]))
                    riichi_pending = None
                last_discard = (e["who"], e["tile"])
            elif t == "riichi":
                out.append(_ev(type="reach", actor=e["who"], open=True if e.get("open") else None))
                riichi_pending = e["who"]
            elif t in ("chi", "pon"):
                called = last_discard[1] if last_discard else None
                consumed = [x for x in e["tiles"] if x != called]
                out.append(_ev(type=t, actor=e["who"], target=e["from"], pai=_pai(ts, called), tile=called,
                               consumed=[_pai(ts, x) for x in consumed], consumed_tiles=consumed))
            elif t == "kan":
                if e["kind"] == "minkan":
                    called = last_discard[1] if last_discard else None
                    consumed = [x for x in e["tiles"] if x != called]
                    out.append(_ev(type="daiminkan", actor=e["who"], target=e["from"], pai=_pai(ts, called), tile=called,
                                   consumed=[_pai(ts, x) for x in consumed], consumed_tiles=consumed))
                elif e["kind"] == "ankan":
                    out.append(_ev(type="ankan", actor=e["who"], consumed=[_pai(ts, x) for x in e["tiles"]], consumed_tiles=list(e["tiles"])))
                else:
                    # 加槓：足した 1 枚は record に明示が無いので、同種 4 枚の最後の 1 枚を pai とする（表示用）
                    added = e["tiles"][-1]
                    consumed = [x for x in e["tiles"] if x != added]
                    out.append(_ev(type="kakan", actor=e["who"], pai=_pai(ts, added), tile=added,
                                   consumed=[_pai(ts, x) for x in consumed], consumed_tiles=consumed))
            elif t == "nuki":
                out.append(_ev(type="nukidora", actor=e["who"], pai=_pai(ts, e["tile"]), tile=e["tile"]))
            elif t == "win":
                w = next((x for x in (rnd.get("result") or {}).get("wins", []) if x["who"] == e["who"]), None)
                out.append(_ev(type="hora", actor=e["who"], target=e["from"], pai=_pai(ts, e["tile"]), tile=e["tile"],
                               deltas=w.get("deltas") if w else None, scores=(rnd.get("result") or {}).get("scores")))
            elif t == "draw_end":
                out.append(_ev(type="ryukyoku", reason=e.get("reason"), deltas=((rnd.get("result") or {}).get("draw") or {}).get("deltas"),
                               scores=(rnd.get("result") or {}).get("scores")))
            elif t == "abort":
                out.append(_ev(type="abort", reason=e.get("reason"), actor=e.get("who"), resume=e.get("resume")))
            elif t == "chombo":
                out.append(_ev(type="chombo", actor=e.get("who"), kind=e.get("kind")))
        out.append({"type": "end_kyoku"})
    out.append(_ev(type="end_game", scores=rec.get("final", {}).get("scores"), settled=rec.get("final", {}).get("settled")))
    return out


def _tile_from(ts: dict, hand: List[int], pai: Optional[str], tile: Optional[int], used: List[int]) -> int:
    if tile is not None:
        if tile not in hand or tile in used:
            raise ValidationError(f"tile {tile} は手牌に無い")
        return tile
    if pai is None:
        raise ValidationError("pai か tile が必要")
    cands = TS.parse_label(ts, pai)
    for t in sorted(hand):
        if t in cands and t not in used:
            return t
    # 赤でない指定（例 5m）が赤しか無い手牌に来たら赤を使う
    for t in sorted(hand):
        if TS.tile_label(ts, t, "mjai").rstrip("r") == pai.rstrip("r") and t not in used:
            return t
    raise ValidationError(f"{pai} が手牌に無い")


def from_mjai_action(resp: dict, ts: dict, obs: dict) -> dict:
    """mjai 応答 → annotation 2.3.1 の行動。obs は observe() の戻り値（応答者の視点）。"""
    t = resp.get("type")
    hand = list(obs["hand"])
    if t == "none":
        return {"type": "pass"}
    if t == "dahai":
        return {"type": "discard", "tile": _tile_from(ts, hand, resp.get("pai"), resp.get("tile"), [])}
    if t == "reach":
        a = {"type": "riichi"}
        if resp.get("open"):
            a["open"] = True
        if "pai" in resp or "tile" in resp:
            a["tile"] = _tile_from(ts, hand, resp.get("pai"), resp.get("tile"), [])
        return a
    if t == "hora":
        return {"type": "tsumo" if resp.get("actor") == resp.get("target") else "ron"}
    if t == "ryukyoku":
        return {"type": "draw_declare", "reason": resp.get("reason", "nine_terminals")}
    if t in ("chi", "pon", "daiminkan"):
        ld = obs.get("last_discard")
        if not ld:
            raise ValidationError("直前の打牌が無い")
        used: List[int] = []
        consumed_tiles = resp.get("consumed_tiles")
        if consumed_tiles is None:
            consumed_tiles = []
            for p in resp.get("consumed", []):
                x = _tile_from(ts, hand, p, None, used)
                used.append(x)
                consumed_tiles.append(x)
        tiles = sorted(consumed_tiles + [ld["tile"]])
        if t == "daiminkan":
            return {"type": "kan", "kind": "minkan", "tiles": tiles}
        return {"type": t, "tiles": tiles}
    if t == "ankan":
        consumed_tiles = resp.get("consumed_tiles")
        if consumed_tiles is None:
            used: List[int] = []
            consumed_tiles = []
            for p in resp.get("consumed", []):
                x = _tile_from(ts, hand, p, None, used)
                used.append(x)
                consumed_tiles.append(x)
        return {"type": "kan", "kind": "ankan", "tiles": sorted(consumed_tiles)}
    if t == "kakan":
        added = _tile_from(ts, hand, resp.get("pai"), resp.get("tile"), [])
        k = O.kind_of(ts, added)
        for m in obs["melds"][obs["seat"]]:
            if m["kind"] == "pon" and O.kind_of(ts, m["tiles"][0]) == k:
                return {"type": "kan", "kind": "kakan", "tiles": sorted(m["tiles"] + [added])}
        raise ValidationError("加槓できるポンが無い")
    if t == "nukidora":
        return {"type": "nuki", "tile": _tile_from(ts, hand, resp.get("pai"), resp.get("tile"), [])}
    raise ValidationError(f"mjai 応答 type {t!r} は未対応")


def request_action(obs: dict, legal: List[dict], ts: dict, request_id: str, time: Optional[dict] = None) -> dict:
    """RiichiLab と同形の request_action。possible_actions は mjai 形（pai 併記）。"""
    pa = []
    for a in legal:
        t = a["type"]
        if t == "discard":
            pa.append({"type": "dahai", "pai": _pai(ts, a["tile"]), "tile": a["tile"]})
        elif t == "riichi":
            pa.append(_ev(type="reach", pai=_pai(ts, a["tile"]), tile=a["tile"], open=True if a.get("open") else None))
        elif t in ("tsumo", "ron"):
            pa.append({"type": "hora"})
        elif t == "pass":
            pa.append({"type": "none"})
        elif t in ("chi", "pon"):
            ld = obs.get("last_discard") or {}
            cons = [x for x in a["tiles"] if x != ld.get("tile")]
            pa.append({"type": t, "pai": _pai(ts, ld.get("tile")), "tile": ld.get("tile"), "consumed": [_pai(ts, x) for x in cons], "consumed_tiles": cons})
        elif t == "kan":
            if a["kind"] == "minkan":
                ld = obs.get("last_discard") or {}
                cons = [x for x in a["tiles"] if x != ld.get("tile")]
                pa.append({"type": "daiminkan", "pai": _pai(ts, ld.get("tile")), "tile": ld.get("tile"), "consumed": [_pai(ts, x) for x in cons], "consumed_tiles": cons})
            elif a["kind"] == "ankan":
                pa.append({"type": "ankan", "consumed": [_pai(ts, x) for x in a["tiles"]], "consumed_tiles": list(a["tiles"])})
            else:
                added = next((x for x in a["tiles"] if x in obs["hand"]), a["tiles"][-1])
                cons = [x for x in a["tiles"] if x != added]
                pa.append({"type": "kakan", "pai": _pai(ts, added), "tile": added, "consumed": [_pai(ts, x) for x in cons], "consumed_tiles": cons})
        elif t == "nuki":
            pa.append({"type": "nukidora", "pai": _pai(ts, a["tile"]), "tile": a["tile"]})
        elif t == "draw_declare":
            pa.append({"type": "ryukyoku", "reason": a.get("reason")})
    return _ev(type="request_action", request_id=request_id, time=time or {"grace_ms": 0, "bank_ms": 0, "deadline_ms": 0}, possible_actions=pa)
