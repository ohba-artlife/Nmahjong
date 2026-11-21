"""天鳳 mjlog（XML）→ Nmahjong の wall（局ごと）＋record。docs/overview.md §10（SHUFFLE 付きの四麻・三麻）。

牌番号は天鳳の 0〜135 ＝ 牌表 mpsz。役番号 → 役名は TENHOU_YAKU。
"""
import gzip
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

from .. import ruleset as R, tileset as TS, wall as W
from ..canon import ValidationError, sha256_id
from . import shuffle as SH

# 天鳳の役番号（AGARI.yaku／yakuman）→ 役名（vocab.json）
TENHOU_YAKU = {
    0: "menzen_tsumo", 1: "riichi", 2: "ippatsu", 3: "chankan", 4: "rinshan", 5: "haitei", 6: "houtei", 7: "pinfu", 8: "tanyao",
    9: "iipeikou", 10: "yakuhai_seat", 11: "yakuhai_seat", 12: "yakuhai_seat", 13: "yakuhai_seat",
    14: "yakuhai_round", 15: "yakuhai_round", 16: "yakuhai_round", 17: "yakuhai_round",
    18: "yakuhai_haku", 19: "yakuhai_hatsu", 20: "yakuhai_chun", 21: "double_riichi", 22: "chiitoitsu", 23: "chanta", 24: "ittsu",
    25: "sanshoku", 26: "sanshoku_doukou", 27: "sankantsu", 28: "toitoi", 29: "sanankou", 30: "shousangen", 31: "honroutou",
    32: "ryanpeikou", 33: "junchan", 34: "honitsu", 35: "chinitsu", 36: "renhou", 37: "tenhou", 38: "chiihou", 39: "daisangen",
    40: "suuankou", 41: "suuankou_tanki", 42: "tsuuiisou", 43: "ryuuiisou", 44: "chinroutou", 45: "chuuren", 46: "junsei_chuuren",
    47: "kokushi", 48: "kokushi13", 49: "daisuushii", 50: "shousuushii", 51: "suukantsu", 52: "dora", 53: "ura_dora", 54: "aka_dora",
}
YAKUMAN_IDS = set(range(37, 52))
RYUUKYOKU_TYPE = {None: "exhaustive", "yao9": "nine_terminals", "kaze4": "four_winds", "kan4": "four_kans",
                  "reach4": "four_riichi", "ron3": "three_ron", "nm": "nagashi_mangan"}


def read_tags(path: str) -> List[Tuple[str, Dict[str, str]]]:
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8")
    root = ET.fromstring(text)
    return [(t.tag, dict(t.attrib)) for t in root]


def decode_meld(m: int, who: int, players: int = 4) -> dict:
    """天鳳 N.m → {kind, tiles[], from(seat), called}。"""
    rel = m & 3
    from_seat = (who + rel) % 4          # 相対位置は三麻でも 4 席の並びで数える（席 3 が空席）
    if m & 0x4:  # chi
        t = m >> 10
        r = t % 3
        t //= 3
        base = (t // 7) * 9 + (t % 7)
        tiles = [base * 4 + ((m >> 3) & 3), (base + 1) * 4 + ((m >> 5) & 3), (base + 2) * 4 + ((m >> 7) & 3)]
        return {"kind": "chi", "tiles": tiles, "from": from_seat, "called": tiles[r]}
    if m & 0x18:  # pon / kakan
        t = m >> 9
        r = t % 3
        t //= 3
        unused = (m >> 5) & 3
        four = [t * 4 + i for i in range(4)]
        three = [x for i, x in enumerate(four) if i != unused]
        if m & 0x8:
            return {"kind": "pon", "tiles": three, "from": from_seat, "called": three[r]}
        return {"kind": "kakan", "tiles": four, "from": from_seat, "called": four[unused]}
    if m & 0x20:  # nuki（三麻の北）
        return {"kind": "nuki", "tiles": [m >> 8], "from": who, "called": m >> 8}
    t = m >> 8
    base = t // 4
    four = [base * 4 + i for i in range(4)]
    if rel == 0:
        return {"kind": "ankan", "tiles": four, "from": who, "called": None}
    return {"kind": "minkan", "tiles": four, "from": from_seat, "called": t}


def _ints(s: str) -> List[int]:
    return [int(x) for x in s.split(",") if x != ""]


def ruleset_name_for_type(gtype: int, exact: bool = False) -> str:
    """GO.type のビットから同梱ルール名を選ぶ。0x08=東南（無ければ東風）、0x02=赤なし、0x04=喰断なし、0x10=三麻。
    exact＝精算を丸めない版（owari に小数がある牌譜。2026-11 の一般卓で確認）。"""
    if gtype & 0x10:
        return "tenhou-3p"
    if gtype & 0x02 or gtype & 0x04:
        raise ValidationError(f"GO.type={gtype:#x}（赤なし／喰断なし）の同梱ルールは未作成")
    name = "tenhou-4p-hanchan-red" if gtype & 0x08 else "tenhou-4p-tonpu-red"
    return name + "-exact" if exact else name


def owari_has_fraction(values: List[float]) -> bool:
    """owari（点, pt の並び）の pt に小数があるか。あれば精算を丸めていない。"""
    return any(abs(v - round(v)) > 1e-9 for v in values[1::2])


def import_mjlog(path: str, ts: Optional[dict] = None, rs: Optional[dict] = None, source_ref: Optional[str] = None):
    """戻り値 (record, walls[]). ts／rs を省略すると同梱 mpsz と tenhou-4p-hanchan-red。"""
    tags = read_tags(path)
    attrs = dict(tags)
    seed = None
    for tag, a in tags:
        if tag == "SHUFFLE":
            seed = a.get("seed")
    go = next((a for t, a in tags if t == "GO"), {})
    gtype = int(go.get("type", "0"))
    players = 3 if gtype & 0x10 else 4
    if rs is None:
        ow = next((a["owari"] for t, a in tags if t in ("AGARI", "RYUUKYOKU") and "owari" in a), None)
        exact = bool(ow) and players == 4 and owari_has_fraction(_ints_f(ow))
        rs = R.find(name=ruleset_name_for_type(gtype, exact))
    ts = ts or TS.find(id=rs["tileset"]["id"])
    un = next((a for t, a in tags if t == "UN" and "n0" in a), {})
    names = [unquote(un.get(f"n{i}", "")) for i in range(players)]
    dans = _ints(un["dan"]) if "dan" in un else [None] * players
    rates = [float(x) for x in un["rate"].split(",")] if "rate" in un else [None] * players
    plist = []
    for i in range(players):
        p = {"seat": i, "name": names[i], "external": [{"system": "tenhou", "id": names[i]}]}
        if dans[i] is not None:
            p["ranks"] = [{"system": "tenhou-rank", "value": dans[i]}]
        if rates[i] is not None:
            p["rating"] = {"system": "tenhou-rate", "value": rates[i]}
        plist.append(p)

    rounds = []
    walls = []
    cur = None
    last_draw = {}
    pending_rinshan = set()
    owari = None
    k = -1
    for tag, a in tags:
        if tag == "INIT":
            k += 1
            sv = _ints(a["seed"])
            oya = int(a["oya"])
            scores = [x * 100 for x in _ints(a["ten"])][:players]   # 三麻でも 4 個入っている
            wall = None
            if seed:
                wall = W.build_tenhou(ts, seed, k, oya, players, 13, meta={"source": "tenhou", "ref": source_ref})
                walls.append(wall)
            cur = {"index": k, "wall": {"id": wall["id"]} if wall else None,
                   "state": {"bakaze": "ESWN"[sv[0] // 4], "kyoku": sv[0] % 4 + 1, "honba": sv[1], "kyotaku": sv[2],
                             "oya": oya, "scores": scores, "dice": [sv[3] + 1, sv[4] + 1]},
                   "events": [{"t": "deal"}, {"t": "dora", "tile": sv[5]}],
                   "result": None, "_hands": [_ints(a[f"hai{i}"]) for i in range(players)]}
            if not wall:
                cur["events"][0]["hands"] = cur["_hands"]
            rounds.append(cur)
            last_draw = {}
            pending_rinshan = set()
            continue
        if cur is None:
            continue
        m = re.fullmatch(r"([TUVW])(\d+)", tag)
        if m:
            who = "TUVW".index(m.group(1))
            tile = int(m.group(2))
            ev = {"t": "draw", "who": who, "tile": tile}
            if who in pending_rinshan:
                ev["rinshan"] = True
                pending_rinshan.discard(who)
            cur["events"].append(ev)
            last_draw[who] = tile
            continue
        m = re.fullmatch(r"([DEFG])(\d+)", tag)
        if m:
            who = "DEFG".index(m.group(1))
            tile = int(m.group(2))
            ev = {"t": "discard", "who": who, "tile": tile, "tsumogiri": last_draw.get(who) == tile}
            if cur["events"] and cur["events"][-1].get("t") == "riichi" and cur["events"][-1]["who"] == who:
                ev["riichi"] = True
            cur["events"].append(ev)
            last_draw.pop(who, None)
            continue
        if tag == "N":
            who = int(a["who"])
            md = decode_meld(int(a["m"]), who, players)
            if md["kind"] in ("chi", "pon", "minkan"):
                last_draw.pop(who, None)         # 鳴いた直後の打牌はツモ切りではない（前に引いて残していた牌を切っても手出し）
            if md["kind"] in ("chi", "pon"):
                cur["events"].append({"t": md["kind"], "who": who, "from": md["from"], "tiles": md["tiles"]})
            elif md["kind"] == "nuki":
                cur["events"].append({"t": "nuki", "who": who, "tile": md["tiles"][0]})
                pending_rinshan.add(who)
            else:
                ev = {"t": "kan", "who": who, "kind": md["kind"], "tiles": md["tiles"]}
                if md["kind"] == "minkan":
                    ev["from"] = md["from"]
                cur["events"].append(ev)
                pending_rinshan.add(who)
            continue
        if tag == "REACH":
            if a.get("step") == "1":
                cur["events"].append({"t": "riichi", "who": int(a["who"])})
            continue
        if tag == "DORA":
            cur["events"].append({"t": "dora", "tile": int(a["hai"])})
            continue
        if tag == "AGARI":
            who = int(a["who"]); frm = int(a["fromWho"])
            ten = _ints(a["ten"])
            sc = _ints(a["sc"])
            # sc は（立直棒を引いた後の持ち点, 増減）。record の deltas は局開始時からの増減（立直棒・供託込み）。
            # ダブロンは AGARI が 2 つ続き、2 つ目の sc は 1 つ目の結果を起点にしているので、直前の和了後の点を基準にする
            after = [sc[2 * i] * 100 + sc[2 * i + 1] * 100 for i in range(players)]   # 4 人分あっても先頭 players 人
            basis = cur["result"]["scores"] if cur["result"] else cur["state"]["scores"]
            deltas = [after[i] - basis[i] for i in range(players)]
            yaku = []
            han = 0
            yakuman = 0
            if "yaku" in a:
                ys = _ints(a["yaku"])
                for yid, h in zip(ys[::2], ys[1::2]):
                    if h == 0:
                        continue
                    yaku.append({"name": TENHOU_YAKU[yid], "han": h})
                    han += h
            if "yakuman" in a:
                for yid in _ints(a["yakuman"]):
                    yaku.append({"name": TENHOU_YAKU[yid], "yakuman": 1})
                    yakuman += 1
            melds = [decode_meld(int(x), who, players) for x in a["m"].split(",")] if a.get("m") else []
            win = {"who": who, "from": frm, "tile": int(a["machi"]), "hand": _ints(a["hai"]),
                   "melds": [{"kind": md["kind"], "tiles": md["tiles"], "from": md["from"]} for md in melds],
                   "yaku": yaku, "fu": ten[0], "han": han, "points": ten[1], "deltas": deltas}
            if yakuman:
                win["yakuman"] = yakuman
            if "doraHaiUra" in a:
                win["ura_indicators"] = _ints(a["doraHaiUra"])
            if "paoWho" in a:
                win["pao"] = int(a["paoWho"])
            cur["events"].append({"t": "win", "who": who, "from": frm, "tile": int(a["machi"])})
            res = cur["result"] or {"wins": [], "draw": None}
            res["wins"].append(win)
            res["scores"] = after
            cur["result"] = res
            if "owari" in a:
                owari = _ints_f(a["owari"])
            continue
        if tag == "RYUUKYOKU":
            sc = _ints(a["sc"])
            after = [sc[2 * i] * 100 + sc[2 * i + 1] * 100 for i in range(players)]
            deltas = [after[i] - cur["state"]["scores"][i] for i in range(players)]
            reason = RYUUKYOKU_TYPE.get(a.get("type"), "exhaustive")
            tenpai = [f"hai{i}" in a for i in range(players)]
            hands = [_ints(a[f"hai{i}"]) if f"hai{i}" in a else None for i in range(players)]
            cur["events"].append({"t": "draw_end", "reason": reason})
            cur["result"] = {"wins": [], "draw": {"reason": reason, "tenpai": tenpai, "hands": hands, "deltas": deltas},
                             "scores": after}
            if "owari" in a:
                owari = _ints_f(a["owari"])
            continue
        if tag == "BYE":
            if cur is None or cur["result"] is not None:   # 局の結果が出た後の切断は対局に影響しない
                continue
            cur["events"].append({"t": "abort", "reason": "disconnect", "who": int(a["who"]), "resume": True})
            continue
    for r in rounds:
        r.pop("_hands", None)
    if not rounds or rounds[-1]["result"] is None:
        raise ValidationError("最終局に結果が無い（途中で切れた牌譜）")
    final_scores = list(rounds[-1]["result"]["scores"])
    nrs = R.normalize(rs)
    from .. import scoring as S
    leftover = nrs["settlement"]["start_points"] * players - sum(final_scores)
    if leftover > 0 and nrs["game_rules"]["flow"]["riichi"]["stick_at_end"] == "to_first":
        rk = S.ranks(final_scores, tie=nrs["settlement"]["tie"])
        tops = [i for i in range(players) if rk[i] == 1]
        for i in tops:
            final_scores[i] += leftover // len(tops)
    rec = {"format": "nmahjong-record", "version": "1.0",
           "source": {"kind": "imported", "from": "tenhou", "ref": source_ref},
           "ruleset": R.ref(rs), "players": plist, "end": "finished", "parent": None, "rounds": rounds,
           "final": {"scores": final_scores}}
    rec["final"]["rank"] = S.ranks(final_scores, tie=nrs["settlement"]["tie"])
    if owari:
        rec["final"]["settled"] = [owari[2 * i + 1] for i in range(players)]
    else:
        rec["final"]["settled"] = S.settle(final_scores, nrs["settlement"])
    if players == 3:
        _map_tiles(rec, SH.tenhou_to_x28)
    rec["id"] = sha256_id({k: v for k, v in rec.items() if k != "id"})
    return rec, walls


_TILE_KEYS = ("tile", "tiles", "hand", "hands", "ura_indicators")


def _map_tiles(obj, fn):
    """record 内の牌番号（天鳳 136 系）を牌表の番号に写す。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _TILE_KEYS:
                obj[k] = _map_val(v, fn)
            else:
                _map_tiles(v, fn)
    elif isinstance(obj, list):
        for x in obj:
            _map_tiles(x, fn)


def _map_val(v, fn):
    if isinstance(v, int) and not isinstance(v, bool):
        return fn(v)
    if isinstance(v, list):
        return [_map_val(x, fn) for x in v]
    return v


def _ints_f(s: str) -> List[float]:
    return [float(x) for x in s.split(",")]
