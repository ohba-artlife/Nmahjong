"""和了の役と符の判定（4 層）。ruleset の役・符・ドラの設定に従う。

    ctx = win_context(rec, round_index, event_index, rs, ts, walls)   # 対局の出来事から、その和了の状況を取り出す
    res = judge(rs, ts, ctx)                                          # 役・符・翻を出す

res ＝ {"ok": True, "yaku": [{"name", "han"} | {"name", "yakuman"}], "fu", "han", "yakuman"（役満のときだけ）, "wait", "form"}
役が無い（縛りを満たさない）・和了形でないときは {"ok": False, "reason": …}。

手牌の解釈（面子の切り方・待ちの取り方）が複数あるときは、基本点 → 翻 → 符 の順に高いものを選ぶ。
手牌 N 枚（1・4・7・10・13…）は「(N−1)/3 面子＋雀頭」。13 枚で副露なしなら七対子・国士無双も見る。

ctx の項目（win_context が作る。進行役は自分で作って渡してよい）:
    hand         手の内の牌（和了牌を含む、副露・抜きは含まない）
    melds        副露 [{"kind": chi|pon|minkan|kakan|ankan, "tiles": [...]}]
    tile         和了牌
    tsumo        ツモ和了か
    seat_wind    自風（"E" など）、round_wind 場風
    riichi, double_riichi, ippatsu, open_riichi, haitei, houtei, rinshan, chankan, tenhou, chiihou, renhou   状況（bool）
    dora_indicators, ura_indicators   表示牌（牌の番号）
    nuki         抜いた牌
    honba        本場（翻縛りの判定用）
"""
from collections import Counter
from typing import Dict, List, Optional, Tuple

from . import observe as O, ruleset as R, scoring as S
from .canon import ValidationError

SUITS = "mps"
WINDS = ("E", "S", "W", "N")
DRAGONS = ("P", "F", "C")
HONORS = WINDS + DRAGONS
DRAGON_YAKU = {"P": "yakuhai_haku", "F": "yakuhai_hatsu", "C": "yakuhai_chun"}
GREEN = {"2s", "3s", "4s", "6s", "8s", "F"}
DORA_NAMES = ("dora", "ura_dora", "aka_dora", "kan_dora", "nuki_dora")
# まだ判定していない役（採用されていても付かない）。docs に明記する
UNSUPPORTED = ("nagashi_mangan",)


def _num(k: str) -> bool:
    return len(k) == 2 and k[1] in SUITS and k[0].isdigit()


def _yao(k: str) -> bool:
    return k in HONORS or (_num(k) and k[0] in "19")


def _term(k: str) -> bool:
    return _num(k) and k[0] in "19"


# ---- 役の表 ------------------------------------------------------------------------------

def yaku_table(norm: dict) -> Dict[str, object]:
    """採用している役 → 翻の指定。値：{"closed": n|None, "open": n|None} か {"yakuman": k}。不採用の役は入らない。"""
    y = norm["game_rules"]["yaku"]
    base = R.YAKU_TABLES.get(y["base"], {"yaku": {}, "yakuman": {}})
    raw: Dict[str, object] = {}
    raw.update(base["yaku"])
    for k, v in base["yakuman"].items():
        raw[k] = "yakuman" if v == 1 else f"yakuman:{v}"
    raw.update(y.get("overrides") or {})
    out: Dict[str, object] = {}
    for k, v in raw.items():
        if v is False or v is None:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            out[k] = {"closed": v, "open": v}
        elif isinstance(v, dict):
            out[k] = {"closed": v.get("closed"), "open": v.get("open")}
        elif isinstance(v, str) and v.startswith("yakuman"):
            out[k] = {"yakuman": int(v.split(":")[1]) if ":" in v else 1}
    return out


# ---- ドラ --------------------------------------------------------------------------------

def next_kind(ts: dict, kind: str) -> Optional[str]:
    """表示牌の次の牌種。牌表にある牌種の中で回る（三人打ちの萬子は 1→9→1）。風は東南西北、三元は白發中で回る。"""
    have = {t["kind"] for t in ts["tiles"]}
    if _num(kind):
        ring = [f"{n}{kind[1]}" for n in range(1, 10) if f"{n}{kind[1]}" in have]
    elif kind in WINDS:
        ring = [k for k in WINDS if k in have]
    elif kind in DRAGONS:
        ring = [k for k in DRAGONS if k in have]
    else:
        return None
    return ring[(ring.index(kind) + 1) % len(ring)] if kind in ring else None


def _mark_rules(norm: dict, ts: dict, tid: int) -> List[dict]:
    g = norm["game_rules"]
    m = ts["tiles"][tid].get("mark")
    for o in g.get("mark_overrides") or []:
        if o.get("tile_id") == tid or ("tile_kind" in o and o["tile_kind"] == ts["tiles"][tid]["kind"] and o.get("mark") == m):
            return [o]
    return [g["marks"][m]] if m is not None and m in (g.get("marks") or {}) else []


def _on_win_tile(rule: dict, tid: int, ctx: dict) -> bool:
    """条件に how（tsumo／ron）がある印の効果は、和了牌にだけ働く。how が無い（any）印は、手の内のどの牌にも働く。"""
    return (rule.get("when") or {}).get("how", "any") == "any" or tid == ctx["tile"]


def _when_ok(rule: dict, ctx: dict, menzen: bool) -> bool:
    w = rule.get("when")
    if not w:
        return True
    if w.get("state", "any") == "riichi" and not (ctx.get("riichi") or ctx.get("double_riichi")):
        return False
    how = w.get("how", "any")
    if how == "tsumo" and not ctx["tsumo"]:
        return False
    if how == "ron" and ctx["tsumo"]:
        return False
    if w.get("ippatsu_only") and not ctx.get("ippatsu"):
        return False
    if w.get("rinshan_ok", True) is False and ctx.get("rinshan"):
        return False
    if w.get("haitei_ok", True) is False and (ctx.get("haitei") or ctx.get("houtei")):
        return False
    if w.get("menzen_only") and not menzen:
        return False
    return True


# ---- 手牌の切り方 --------------------------------------------------------------------------

_ORDER = [f"{n}{s}" for s in SUITS for n in range(1, 10)] + list(HONORS)


def _split(c: Counter, kinds: List[str], i: int, need: int, acc: list, out: list) -> None:
    if need == 0:
        if all(c[k] == 0 for k in kinds):
            out.append(list(acc))
        return
    while i < len(kinds) and c[kinds[i]] == 0:
        i += 1
    if i >= len(kinds):
        return
    k = kinds[i]
    if c[k] >= 3:
        c[k] -= 3
        acc.append(("pon", k))
        _split(c, kinds, i, need - 1, acc, out)
        acc.pop()
        c[k] += 3
    if _num(k) and int(k[0]) <= 7:
        k2, k3 = f"{int(k[0]) + 1}{k[1]}", f"{int(k[0]) + 2}{k[1]}"
        if c[k2] > 0 and c[k3] > 0:
            c[k] -= 1; c[k2] -= 1; c[k3] -= 1
            acc.append(("chi", k))
            _split(c, kinds, i, need - 1, acc, out)
            acc.pop()
            c[k] += 1; c[k2] += 1; c[k3] += 1


def decompositions(kinds: List[str], need: int) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """手の内の牌種の列を「need 面子＋雀頭」に切る全部の方法。[(雀頭, [("pon"|"chi", 牌種（順子は最小の牌）)…])]"""
    c = Counter(kinds)
    if any(k not in _ORDER for k in c) or len(kinds) != need * 3 + 2:
        return []
    ks = [k for k in _ORDER if c[k] > 0]
    out = []
    for p in ks:
        if c[p] >= 2:
            c[p] -= 2
            got: list = []
            _split(c, ks, 0, need, [], got)
            c[p] += 2
            out += [(p, g) for g in got]
    return out


def _chi_kinds(k: str) -> List[str]:
    return [f"{int(k[0]) + d}{k[1]}" for d in range(3)]


# ---- 判定 --------------------------------------------------------------------------------

def judge(rs: dict, ts: dict, ctx: dict) -> dict:
    norm = R.normalize(rs)
    g = norm["game_rules"]
    sc = g["scoring"]
    N = norm["hand_size"]
    table = yaku_table(norm)
    kind = lambda t: ts["tiles"][t]["kind"]   # noqa: E731
    melds = ctx.get("melds") or []
    hand = list(ctx["hand"])
    menzen = all(m["kind"] == "ankan" for m in melds)

    # オールマイティの牌（効果が働くもの）は、牌種を総当たりして一番高い解釈を選ぶ
    # 条件に how（tsumo／ron）がある印は「その牌で和了したとき」の効果なので、和了牌にだけ働く（手の内に持っているだけでは普通の牌）
    wild = [t for t in hand if any("almighty" in r.get("effects", []) and _when_ok(r, ctx, menzen) and _on_win_tile(r, t, ctx) for r in _mark_rules(norm, ts, t))]
    if len(wild) > 2:
        raise ValidationError("オールマイティの牌が手の内に 3 枚以上ある和了は判定していない")
    have = [k for k in _ORDER if any(t["kind"] == k for t in ts["tiles"])]
    assigns: List[Dict[int, str]] = [{}]
    for t in wild:
        assigns = [{**a, t: k} for a in assigns for k in have]

    # 抜く牌を手の内・副露に残したままの和了を認めないルール（nuki.win_with_nuki_in_hand＝false）：その牌が無いと和了できない役満だけは認める
    nk = g.get("nuki") or {}
    kept = bool(nk.get("enabled")) and not nk.get("win_with_nuki_in_hand", True) and any(
        kind(t) in nk.get("tiles", []) for t in hand + [t for m in melds for t in m["tiles"]])
    blocked = False
    best = None
    for a in assigns:
        kinds = [a.get(t, kind(t)) for t in hand]
        win_kind = a.get(ctx["tile"], kind(ctx["tile"]))
        for cand in _candidates(norm, table, ctx, kinds, win_kind, melds, kind, menzen, N):
            cand = _finish(norm, ts, table, ctx, cand, hand, melds, kind, menzen)
            if cand is None:
                continue
            if kept and not any(y["name"] in _NUKI_KEPT_OK for y in cand["yaku"]):
                blocked = True
                continue
            key = (S.base_points(cand["fu"], cand["han"], cand.get("yakuman", 0), sc), cand.get("yakuman", 0), cand["han"], cand["fu"])
            if best is None or key > best[0]:
                best = (key, cand)
    if best is None and blocked:
        return {"ok": False, "reason": "抜く牌を手に残したままでは和了できない"}
    if best is None:
        if not any(True for a in assigns for _ in _shapes([a.get(t, kind(t)) for t in hand], melds, kind, N, g)):
            return {"ok": False, "reason": "和了形ではない"}
        return {"ok": False, "reason": "役が無い"}
    if g["flow"]["atozuke"] == "kanzen_sakizuke" and not ctx.get("_no_sakizuke_check") and not best[1].get("yakuman"):
        bad = _yakuless_waits(rs, ts, ctx, hand, melds, kind, N, menzen)
        if bad:
            return {"ok": False, "reason": "完全先付け：役の無い待ち（" + "・".join(bad) + "）がある"}
    return best[1]


_CHANCE = ("ippatsu", "haitei", "houtei", "rinshan", "chankan")
# 抜く牌を手に残したまま和了できる役満（幺九牌・字牌が無いと作れないもの）
_NUKI_KEPT_OK = ("kokushi", "kokushi13", "chinroutou", "tsuuiisou", "tsuuiisou_chiitoi", "shousuushii", "daisuushii")


def _yakuless_waits(rs, ts, ctx, hand, melds, kind, N, menzen) -> List[str]:
    """完全先付け（片和了なし）：この聴牌の待ちのうち、役が付かない牌種。1 つでもあれば、どの牌でも和了できない。
    役は、その牌で同じ和了り方（ロン／ツモ）をしたものとして数え、偶然の役（一発・海底・河底・嶺上・槍槓）とドラは数えない。
    門前のツモは門前清自摸和が付くので、どの待ちにも役がある。"""
    rest = list(hand)
    rest.remove(ctx["tile"])
    by_kind = {}
    for i, t in enumerate(ts["tiles"]):
        by_kind.setdefault(t["kind"], []).append(i)
    bad = []
    for k in sorted(O.waits(ts, rest, len(melds), N), key=lambda x: _ORDER.index(x) if x in _ORDER else 99):
        used = set(rest) | {t for m in melds for t in m["tiles"]}
        tid = next((t for t in by_kind.get(k, []) if t not in used and ts["tiles"][t].get("mark") is None), None)
        if tid is None:
            tid = next((t for t in by_kind.get(k, []) if t not in used), by_kind[k][0])
        c2 = dict(ctx, hand=rest + [tid], tile=tid, _no_sakizuke_check=True, dora_indicators=[], ura_indicators=[], nuki=[])
        for f in _CHANCE:
            c2[f] = False
        if not judge(rs, ts, c2).get("ok"):
            bad.append(k)
    return bad


def _shapes(kinds: List[str], melds: List[dict], kind, N: int, g: dict):
    """和了形の列挙：("standard", 雀頭, 面子の列) ／ ("chiitoi", 対子の列) ／ ("kokushi",)"""
    need = (N - 1) // 3 - len(melds)
    if need >= 0:
        for p, sets in decompositions(kinds, need):
            yield ("standard", p, sets)
    if N == 13 and not melds and len(kinds) == 14:
        c = Counter(kinds)
        if all(v in (2, 4) for v in c.values()) and (len(c) == 7 or g["yaku"].get("chiitoi_four_of_kind")):
            yield ("chiitoi", sorted(c))
        yao = [k for k in _ORDER if _yao(k)]
        if set(c) == set(yao):
            yield ("kokushi",)


def _candidates(norm, table, ctx, kinds, win_kind, melds, kind, menzen, N):
    """形と待ちの取り方ごとに、役の名前の集合と符を出す。"""
    g = norm["game_rules"]
    fu_rule = g["scoring"]["fu"]
    seat, rnd = ctx.get("seat_wind"), ctx.get("round_wind")
    tsumo = ctx["tsumo"]
    all_kinds = list(kinds)
    for m in melds:
        all_kinds += [kind(t) for t in m["tiles"]]
    nuki_kinds = set()
    nk = g.get("nuki") or {}
    if nk.get("enabled"):
        nuki_kinds = set(nk.get("tiles") or [])

    def pair_yakuhai_count(p: str) -> int:
        n = 0
        if p in DRAGONS:
            n += 1
        if p == seat:
            n += 1
        if p == rnd:
            n += 1
        if p in nuki_kinds and nk.get("as_yakuhai") == "common" and p not in (seat, rnd):
            n += 1
        return n

    situ = _situational(g, ctx, menzen)
    whole = _whole_hand(g, all_kinds, menzen)

    for shape in _shapes(kinds, melds, kind, N, g):
        if shape[0] == "kokushi":
            c = Counter(kinds)
            names = set(situ) | {"kokushi13" if c[win_kind] == 2 else "kokushi"}
            if c[win_kind] == 2:
                names.add("kokushi")
            yield {"names": names, "fu": 30 if tsumo else 40, "form": "kokushi", "wait": "kokushi"}
            continue
        if shape[0] == "chiitoi":
            names = set(situ) | set(whole) | {"chiitoitsu"}
            if all(k in HONORS for k in kinds):
                names.add("tsuuiisou_chiitoi")
            # 大車輪：一色の 2〜8 の七対子（既定）。yaku.wheel＝any_suit なら清一色の七対子ならどの並びでも（関西の三人打ち）
            if sorted(set(kinds)) in ([f"{n}{s}" for n in range(2, 9)] for s in SUITS) or (g["yaku"].get("wheel") == "any_suit" and "chinitsu" in whole):
                names.add("daisharin")
            if "honitsu" in whole:                       # 小車輪：混一色の七対子（どの色でも）
                names.add("shousharin")
            yield {"names": names, "fu": 25, "form": "chiitoi", "wait": "tanki"}
            continue
        _, pair, csets = shape
        # 待ちの取り方
        waits = []
        if pair == win_kind:
            waits.append(("tanki", None))
        for j, (t, k) in enumerate(csets):
            if (t, k) in csets[:j]:
                continue
            if t == "pon" and k == win_kind:
                waits.append(("shanpon", j))
            if t == "chi" and win_kind in _chi_kinds(k):
                pos = _chi_kinds(k).index(win_kind)
                n0 = int(k[0])
                if pos == 1:
                    waits.append(("kanchan", j))
                elif (pos == 2 and n0 == 1) or (pos == 0 and n0 == 7):
                    waits.append(("penchan", j))
                else:
                    waits.append(("ryanmen", j))
        for wait, wj in waits:
            sets = []      # {"t": pon|chi|kan, "k": 牌種, "open": bool}
            for j, (t, k) in enumerate(csets):
                sets.append({"t": t, "k": k, "open": (t == "pon" and wait == "shanpon" and wj == j and not tsumo)})
            for m in melds:
                ks = sorted((kind(t) for t in m["tiles"]), key=_ORDER.index)
                if m["kind"] == "chi":
                    sets.append({"t": "chi", "k": ks[0], "open": True})
                elif m["kind"] == "pon":
                    sets.append({"t": "pon", "k": ks[0], "open": True})
                else:
                    sets.append({"t": "kan", "k": ks[0], "open": m["kind"] != "ankan"})
            names = set(situ) | set(whole)
            chis = [s for s in sets if s["t"] == "chi"]
            trips = [s for s in sets if s["t"] != "chi"]
            pyk = pair_yakuhai_count(pair)
            pinfu_shape = len(chis) == len(sets) and len(sets) >= 1 and pyk == 0 and wait == "ryanmen"
            pinfu = pinfu_shape and menzen and (not tsumo or fu_rule["menzen_tsumo_pinfu"])
            if pinfu:
                names.add("pinfu")
            # 役牌
            for s in trips:
                k = s["k"]
                if k in DRAGONS:
                    names.add(DRAGON_YAKU[k])
                if k == seat:
                    names.add("yakuhai_seat")
                if k == rnd:
                    names.add("yakuhai_round")
            tw = [s["k"] for s in trips if s["k"] in WINDS]
            td = [s["k"] for s in trips if s["k"] in DRAGONS]
            if len(td) == 3:
                names.add("daisangen")
            if len(td) == 2 and pair in DRAGONS:
                names.add("shousangen")
            if len(tw) == 4:
                names.add("daisuushii")
            if len(tw) == 3 and pair in WINDS:
                names.add("shousuushii")
            if len(tw) == 3:
                names.add("sanpuu")
            # 順子の役
            ck = Counter(s["k"] for s in chis)
            dup = sum(v // 2 for v in ck.values())
            if dup >= 2:
                names.add("ryanpeikou")
            if dup >= 1:
                names.add("iipeikou")
            for n in "1234567":
                if all(f"{n}{s}" in ck for s in SUITS):
                    names.add("sanshoku")
            for s in SUITS:
                if all(f"{n}{s}" in ck for n in "147"):
                    names.add("ittsu")
            # 刻子の役
            tk = Counter(s["k"] for s in trips)
            for n in "123456789":
                if all(f"{n}{s}" in tk for s in SUITS):
                    names.add("sanshoku_doukou")
            for s in SUITS:
                run = 0
                for n in range(1, 10):
                    run = run + 1 if f"{n}{s}" in tk else 0
                    if run >= 3:
                        names.add("sanrenkou")
                    if run >= 4:
                        names.add("suurenkou")
            if sets and not chis:
                names.add("toitoi")
            closed_trips = [s for s in trips if not s["open"]]
            if len(closed_trips) == 3:
                names.add("sanankou")
            if len(closed_trips) == 4:
                names.add("suuankou")
                if wait == "tanki":
                    names.add("suuankou_tanki")
            kans = [s for s in sets if s["t"] == "kan"]
            if len(kans) == 3:
                names.add("sankantsu")
            if len(kans) == 4:
                names.add("suukantsu")
            # 么九の役（面子＋雀頭ごと）
            if chis:
                each = all(_yao(s["k"]) for s in trips) and all(s["k"][0] in "17" for s in chis) and _yao(pair)
                if each:
                    names.add("chanta" if any(k in HONORS for k in all_kinds) else "junchan")
            # 九蓮宝燈
            if menzen and not melds and len(kinds) == 14 and all(_num(k) for k in kinds) and len({k[1] for k in kinds}) == 1:
                c = Counter(int(k[0]) for k in kinds)
                if c[1] >= 3 and c[9] >= 3 and all(c[n] >= 1 for n in range(2, 9)):
                    if g["flow"].get("chuuren_any_suit", True) or kinds[0][1] == "m":
                        names.add("chuuren")
                        c[int(win_kind[0])] -= 1
                        if c[1] == 3 and c[9] == 3 and all(c[n] == 1 for n in range(2, 9)):
                            names.add("junsei_chuuren")
            # 符
            fu = 20
            for s in sets:
                if s["t"] == "chi":
                    continue
                v = 2 if s["open"] else 4
                if _yao(s["k"]):
                    v *= 2
                if s["t"] == "kan":
                    v *= 4
                fu += v
            if pair in (seat, rnd) and seat == rnd and pair in WINDS:
                fu += fu_rule["double_wind_pair"]
            else:
                fu += 2 * pyk
            if wait in ("tanki", "kanchan", "penchan"):
                fu += 2
            if wait == "tanki" and pyk:
                fu += fu_rule.get("yakuhai_tanki_fu", 0)
            if tsumo:
                if not pinfu and not (ctx.get("rinshan") and fu_rule["rinshan_tsumo_fu"] == 0):
                    fu += 2
            elif menzen:
                fu += 10
            if not menzen and fu == 20:
                fu = fu_rule["open_pinfu_fu"]
            fu = (fu + 9) // 10 * 10
            yield {"names": names, "fu": fu, "form": "standard", "wait": wait}


def _situational(g: dict, ctx: dict, menzen: bool) -> List[str]:
    out = []
    if ctx.get("double_riichi"):
        out += ["double_riichi", "riichi"]
    elif ctx.get("riichi"):
        out.append("riichi")
    if ctx.get("open_riichi"):
        out.append("open_riichi")
    if ctx.get("ippatsu") and g["flow"].get("ippatsu", True):
        out.append("ippatsu")
    if ctx["tsumo"] and menzen:
        out.append("menzen_tsumo")
    for k in ("haitei", "houtei", "rinshan", "chankan", "tenhou", "chiihou", "renhou"):
        if ctx.get(k):
            out.append(k)
    return out


def _whole_hand(g: dict, all_kinds: List[str], menzen: bool) -> List[str]:
    """手牌全体の牌種だけで決まる役。"""
    out = []
    if all(not _yao(k) for k in all_kinds) and (menzen or g["flow"].get("open_tanyao", True)):
        out.append("tanyao")
    suits = {k[1] for k in all_kinds if _num(k)}
    honors = any(k in HONORS for k in all_kinds)
    if len(suits) == 1 and honors:
        out.append("honitsu")
        if suits == {"m"}:
            out.append("manzu_honitsu")
    if len(suits) == 1 and not honors:
        out.append("chinitsu")
    if not suits:
        out.append("tsuuiisou")
    if all(_term(k) for k in all_kinds):
        out.append("chinroutou")
    if all(_yao(k) for k in all_kinds):
        out.append("honroutou")
    if all(k in GREEN for k in all_kinds) and (not g["flow"].get("ryuuiisou_requires_hatsu") or "F" in all_kinds):
        out.append("ryuuiisou")
    return out


# 上位の役が採用されて付くとき、下位は付けない
_SUPERSEDE = [("double_riichi", "riichi"), ("ryanpeikou", "iipeikou"), ("chinitsu", "honitsu"), ("junchan", "chanta"),
              ("kokushi13", "kokushi"), ("junsei_chuuren", "chuuren"), ("suuankou_tanki", "suuankou"), ("suurenkou", "sanrenkou"),
              ("tsuuiisou", "honroutou"), ("chinroutou", "honroutou"), ("tsuuiisou", "honitsu"), ("chinroutou", "junchan"),
              ("manzu_honitsu", "honitsu"), ("daisharin", "chiitoitsu"), ("tsuuiisou_chiitoi", "tsuuiisou"),
              ("shousharin", "chiitoitsu"), ("shousharin", "honitsu"),
              ("daisuushii", "shousuushii"), ("honroutou", "chanta"), ("ryanpeikou", "chiitoitsu")]


def _finish(norm, ts, table, ctx, cand, hand, melds, kind, menzen) -> Optional[dict]:
    """役の名前 → 採用・翻。ドラを足し、縛りを確かめる。"""
    g = norm["game_rules"]
    sc = g["scoring"]
    names = set(cand["names"])

    def han_of(n: str):
        spec = table.get(n)
        if spec is None:
            return None
        if "yakuman" in spec:
            return ("yakuman", spec["yakuman"])
        v = spec["closed"] if menzen else spec["open"]
        return ("han", v) if v else None

    got = {n: han_of(n) for n in names}
    got = {n: v for n, v in got.items() if v is not None}
    if "open_riichi" in got and g["flow"].get("open_riichi", {}).get("enabled"):
        orr = g["flow"]["open_riichi"]
        tot = orr.get("with_double_riichi_han", 3) if "double_riichi" in got else orr.get("han_total", 2)
        got.pop("riichi", None)
        got.pop("double_riichi", None)
        got["open_riichi"] = ("han", tot)
    for hi, lo in _SUPERSEDE:
        if hi in got:
            got.pop(lo, None)
    fu = cand["fu"]
    if cand["form"] == "chiitoi" and "chiitoitsu" in got and sc["fu"]["chiitoi"] == "50fu_1han":
        fu = 50
        got["chiitoitsu"] = ("han", 1)
    if cand["form"] == "chiitoi" and "chiitoitsu" not in got and "daisharin" not in got and "shousharin" not in got and "tsuuiisou_chiitoi" not in got and "tsuuiisou" not in got:
        return None                       # 七対子を採用していないなら、この形は和了ではない
    if cand["form"] == "kokushi" and "kokushi" not in got and "kokushi13" not in got:
        return None
    ym = {n: v[1] for n, v in got.items() if v[0] == "yakuman"}
    if not ym and ctx.get("open_riichi_deal_in"):
        ym = {"open_riichi_deal_in": 1}                 # 役満でない手でも、役満の点を払う
    order = lambda n: (list(R.VOCAB["yaku"]).index(n) if n in R.VOCAB["yaku"] else 100 + list(R.VOCAB["yakuman"]).index(n))   # noqa: E731
    if ym and not sc["limits"].get("stack_with_normal"):
        yaku = [{"name": n, "yakuman": ym[n]} for n in sorted(ym, key=order)]
        return {"ok": True, "yaku": yaku, "fu": fu, "han": 0, "yakuman": sum(ym.values()), "wait": cand["wait"], "form": cand["form"]}
    yaku = [{"name": n, "han": v[1]} for n, v in sorted(got.items(), key=lambda x: order(x[0])) if v[0] == "han"]
    yaku_han = sum(y["han"] for y in yaku)
    # 印の「役」効果（ドラとは別の 1 翻）
    all_tiles = list(hand) + [t for m in melds for t in m["tiles"]]
    mark_dora = 0
    mark_yaku = 0
    reverse = False
    for t in all_tiles:
        for r in _mark_rules(norm, ts, t):
            if not _when_ok(r, ctx, menzen):
                continue
            eff = r.get("effects", [])
            if "dora" in eff:
                mark_dora += r.get("value", 1)
            if "yaku" in eff:
                mark_yaku += r.get("value", 1)
            if "reverse" in eff and _on_win_tile(r, t, ctx):
                reverse = True
    yaku_han += mark_yaku
    sh = sc["shibari"]
    need = sh["han"] if sh.get("from_honba") is not None and ctx.get("honba", 0) >= sh["from_honba"] else 1
    if not ym and yaku_han < need:
        return None
    # ドラ
    d = g["dora"]
    vals = d.get("values") or {}
    nuki = list(ctx.get("nuki") or [])
    count_tiles = [kind(t) for t in all_tiles + nuki]

    def count(inds, first_key, kan_key, ura=False):
        n = 0
        for i, ind in enumerate(inds or []):
            v = vals.get(first_key if i == 0 else kan_key, 1)
            if ura and any(r.get("as_ura_indicator") == "choose_any" for r in _mark_rules(norm, ts, ind)):
                # 裏ドラ表示牌がこの印の牌（白ポッチ）：好きな牌を裏ドラにできる＝手の中でいちばん多い牌種の枚数
                n += max(Counter(count_tiles).values()) * v
                continue
            nk = next_kind(ts, kind(ind))
            n += count_tiles.count(nk) * v
        return n

    extra = []
    if d.get("indicator"):
        n = count(ctx.get("dora_indicators"), "indicator", "kan")
        if n:
            extra.append({"name": "dora", "han": n})
    if d.get("ura") and (ctx.get("riichi") or ctx.get("double_riichi") or ctx.get("open_riichi")):
        n = count(ctx.get("ura_indicators"), "ura", "kan_ura", ura=True)
        if n:
            extra.append({"name": "ura_dora", "han": n})
    if mark_dora:
        extra.append({"name": "aka_dora", "han": mark_dora})
    nkr = g.get("nuki") or {}
    if nkr.get("enabled") and nuki:
        extra.append({"name": "nuki_dora", "han": len(nuki) * nkr.get("value", 1)})
    if mark_yaku:
        yaku.append({"name": "mark_yaku", "han": mark_yaku})
    out_yaku = ([{"name": n, "yakuman": ym[n]} for n in sorted(ym, key=order)] if ym else []) + yaku + extra
    res = {"ok": True, "yaku": out_yaku, "fu": fu, "han": sum(y.get("han", 0) for y in out_yaku), "wait": cand["wait"], "form": cand["form"]}
    if not sc["fu"]["enabled"]:
        res["fu"] = 20                    # 符を数えないルール：記録には 20 と書く（点数表は翻だけで決まる）
    if ym:
        res["yakuman"] = sum(ym.values())
    if reverse:
        res["reverse"] = True
    return res


# ---- 対局の出来事から状況を取り出す --------------------------------------------------------

def _indicators_from_wall(wall: dict, norm: dict, n: int, kind_first: str, kind_kan: str) -> List[int]:
    """山から、表示牌を n 枚ぶん（1 枚目＋カンのぶん）取り出す。"""
    wr = norm["wall_rules"]
    order = wall["order"]
    live_end = len(order) - wr["dead_wall"]
    deadw = order[live_end:]
    offs = list(wr.get(kind_first, [])) + list(wr.get(kind_kan, []))
    return [deadw[o] if o >= 0 else order[live_end + o] for o in offs[:n]]


def win_context(rec: dict, round_index: int, at: int, rs: dict, ts: dict, walls: Optional[Dict[str, dict]] = None) -> dict:
    """round_index 局の events[at]（t＝win）の和了の状況。judge に渡す形。"""
    rnd = next((r for r in rec["rounds"] if r["index"] == round_index), None)
    if rnd is None:
        raise ValidationError(f"round {round_index} が無い")
    evs = rnd["events"]
    e = evs[at]
    if e.get("t") != "win":
        raise ValidationError(f"events[{at}] は和了ではない")
    first_win = at
    while first_win > 0 and evs[first_win - 1]["t"] == "win":
        first_win -= 1
    res_win = next((w for w in (rnd.get("result") or {}).get("wins", []) if w.get("who") == e["who"]), None)
    return context_at(rec, round_index, first_win - 1, e["who"], e["from"], e["tile"], rs, ts, walls,
                      ura=res_win.get("ura_indicators") if res_win else None)


def context_at(rec: dict, round_index: int, upto: int, who: int, frm: int, tile: int, rs: dict, ts: dict,
               walls: Optional[Dict[str, dict]] = None, ura: Optional[List[int]] = None) -> dict:
    """events[0..upto] まで進んだ局面で、who が frm の牌 tile で和了るときの状況（frm＝who ならツモ）。
    和了の出来事を積む前に「和了れるか」を確かめるのにも使う。ura を省くと、立直していれば山から取る。"""
    norm = R.normalize(rs)
    g = norm["game_rules"]
    M = norm["players"]
    rnd = next((r for r in rec["rounds"] if r["index"] == round_index), None)
    if rnd is None:
        raise ValidationError(f"round {round_index} が無い")
    evs = rnd["events"]
    wall = (walls or {}).get(rnd["wall"]["id"]) if rnd.get("wall") else None
    st = O.replay(rnd, norm, wall, upto)
    tsumo = who == frm
    oya = rnd["state"]["oya"]
    hand = list(st.hands[who]) + ([] if tsumo else [tile])
    before = [x for x in evs[:upto + 1] if x["t"] not in ("dora", "abort")]
    last = before[-1] if before else {}
    robbed = (not tsumo) and last.get("t") in ("kan", "nuki")          # カン・抜きの牌でのロン（そのカン・抜きは成立していない）
    chankan = robbed and (last.get("t") == "kan" or bool((g.get("nuki") or {}).get("chan_nuki")))
    K = len(ts["tiles"])
    remaining = O._remaining(norm, K, st)
    last_draw = next((x for x in reversed(before) if x["t"] == "draw" and x["who"] == who), None)
    rinshan = tsumo and bool(last_draw and last_draw.get("rinshan"))
    # 立直・ダブル立直・一発
    riichi = double = ippatsu = open_r = False
    ri = next((i for i, x in enumerate(before) if x["t"] == "riichi" and x["who"] == who), None)
    if ri is not None and st.riichi[who]:
        riichi = True
        open_r = bool(before[ri].get("open"))
        prior = before[:ri]
        double = not any(x["t"] in ("chi", "pon", "kan", "nuki") for x in prior) and not any(x["t"] == "discard" and x["who"] == who for x in prior)
        after = before[ri + 2:]                    # 立直宣言・宣言牌の打牌のあと
        if robbed and after:
            after = after[:-1]                      # ロンされたカン・抜きは成立していない
        ippatsu = not any(x["t"] in ("chi", "pon", "kan", "nuki") for x in after) and not any(x["t"] == "discard" and x["who"] == who for x in after)
    # オープン立直への放銃の役満払い（flow.open_riichi.deal_in＝yakuman）。先に立直していた人は exempt_prior_riichi で外れ、
    # あとから立直した人（追っかけ）は chaser_pays＝false なら外れる
    deal_in = False
    orr = g["flow"].get("open_riichi") or {}
    if open_r and not tsumo and orr.get("enabled") and orr.get("deal_in") == "yakuman":
        fi = next((i for i, x in enumerate(before) if x["t"] == "riichi" and x["who"] == frm), None)
        if fi is None:
            deal_in = True
        elif fi < ri:
            deal_in = not orr.get("exempt_prior_riichi", True)
        else:
            deal_in = bool(orr.get("chaser_pays", True))
    calls = any(x["t"] in ("chi", "pon", "kan", "nuki") for x in before)      # 抜きも鳴きと同じ扱い（一発・ダブル立直・天和などが消える）
    own_discards = any(x["t"] == "discard" and x["who"] == who for x in before)
    any_discards = any(x["t"] == "discard" for x in before)
    own_draws = sum(1 for x in before if x["t"] == "draw" and x["who"] == who)
    ctx = {
        "who": who, "from": frm, "tile": tile, "tsumo": tsumo, "hand": hand,
        "melds": [{"kind": m["kind"], "tiles": list(m["tiles"])} for m in st.melds[who]],
        "seat_wind": norm["winds"][(who - oya) % M], "round_wind": rnd["state"].get("bakaze"),
        "riichi": riichi, "double_riichi": riichi and double, "ippatsu": ippatsu, "open_riichi": open_r, "open_riichi_deal_in": deal_in,
        "rinshan": rinshan, "chankan": chankan,
        "haitei": tsumo and not rinshan and remaining == 0,
        "houtei": (not tsumo) and not robbed and remaining == 0,
        "tenhou": tsumo and who == oya and not calls and not any_discards,
        "chiihou": tsumo and who != oya and not calls and not own_discards and own_draws == 1,
        "renhou": (not tsumo) and not calls and not own_discards and own_draws == 0,
        "nuki": list(st.nuki[who]), "honba": rnd["state"].get("honba", 0),
    }
    # ドラ表示牌：その時点までにめくられた分（dora の出来事）。まだめくられていないカンドラは数えない
    inds = list(st.dora_indicators)
    ctx["dora_indicators"] = inds
    if ura is not None:
        ctx["ura_indicators"] = list(ura)
    elif wall is not None and riichi and g["dora"].get("ura"):
        ctx["ura_indicators"] = ura_indicators(wall, norm, len(inds))
    else:
        ctx["ura_indicators"] = []
    return ctx


def ura_indicators(wall: dict, norm: dict, n_dora: int) -> List[int]:
    """めくられたドラ表示が n_dora 枚のときの裏ドラ表示牌（1 枚目＋カン裏）。"""
    g = norm["game_rules"]
    n_kan = max(0, n_dora - 1) if g["dora"].get("kan_ura") else 0
    return _indicators_from_wall(wall, norm, 1, "ura_indicator", "kan_ura")[:1] + _indicators_from_wall(wall, norm, n_kan, "kan_ura", "kan_ura")


def judge_win(rec: dict, round_index: int, at: int, rs: dict, ts: dict, walls: Optional[Dict[str, dict]] = None) -> dict:
    return judge(rs, ts, win_context(rec, round_index, at, rs, ts, walls))


def same_as_recorded(res: dict, win: dict, merge_dora: bool = False) -> Optional[str]:
    """判定の結果と、記録の result.wins[] の役・符・翻を比べる。同じなら None、違えば何が違うかの文。
    merge_dora=True：ドラの内訳（カンドラ・抜きドラ）を「dora」にまとめて比べる（天鳳の書き方）。"""
    if not res.get("ok"):
        return f"判定：{res.get('reason')}"

    def norm_y(ys):
        c: Counter = Counter()
        for y in ys:
            n = y["name"]
            if merge_dora and n in ("kan_dora", "nuki_dora"):
                n = "dora"
            if "yakuman" in y:
                c[(n, "yakuman")] += y["yakuman"]
            elif y.get("han"):
                c[(n, "han")] += y["han"]
        return c
    a, b = norm_y(res["yaku"]), norm_y(win.get("yaku", []))
    if a != b:
        return f"役が違う：判定 {sorted(a.items())} 記録 {sorted(b.items())}"
    if res.get("yakuman", 0) != win.get("yakuman", 0):
        return f"役満の倍数が違う：判定 {res.get('yakuman', 0)} 記録 {win.get('yakuman', 0)}"
    if not res.get("yakuman"):
        if res["han"] != win.get("han"):
            return f"翻が違う：判定 {res['han']} 記録 {win.get('han')}"
        if "additive" not in win and res["fu"] != win.get("fu"):          # 足し算の点数（additive）の和了は符を使わず、記録の fu は 0
            return f"符が違う：判定 {res['fu']} 記録 {win.get('fu')}"
    return None
