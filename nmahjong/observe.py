"""局面（observe）と合法手（legal_actions）。overview.md §6、annotation.md §2.3.1。

observe(record, round_index, at, seat, rs, ts, walls) → 局面のスナップショット（seat に見えない手牌は出さない）
observe_full(...)                                   → 全員の手牌を含む（visibility=full 用）
legal_actions(rs, ts, obs)                          → 取れる行動の一覧（annotation 2.3.1 の形）

判定する範囲（1.0）：
  ・和了（tsumo／ron）は「和了形」だけ（(N−1)/3 面子＋雀頭、七対子、国士）。役の有無は判定しない
  ・フリテン（自分の河に待ち牌）、立直の条件（門前・点・ツモ番・海底・フリテン立直）、送りカン（ankan_after）、
    最大カン数、チー禁止、喰い替え、抜き、九種九牌、海底での鳴き禁止
  ・agari_form=custom:* の牌表では和了・立直・九種は列挙しない（実装側定義）
"""
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from . import ruleset as R
from .canon import ValidationError

SUITS = "mps"
HONORS = ("E", "S", "W", "N", "P", "F", "C")


# ---- 牌の種類 --------------------------------------------------------------------------

def kind_of(ts: dict, tid: int) -> str:
    return ts["tiles"][tid]["kind"]


def _is_number(kind: str) -> bool:
    return len(kind) == 2 and kind[0].isdigit() and kind[1] in SUITS


def _is_terminal_or_honor(kind: str) -> bool:
    return kind in HONORS or (_is_number(kind) and kind[0] in "19")


# ---- 局面の再生 ------------------------------------------------------------------------

class State:
    def __init__(self, M: int):
        self.M = M
        self.hands: List[List[int]] = [[] for _ in range(M)]
        self.melds: List[List[dict]] = [[] for _ in range(M)]
        self.discards: List[List[dict]] = [[] for _ in range(M)]   # {"tile", "tsumogiri", "riichi", "called"}
        self.riichi: List[bool] = [False] * M
        self.riichi_pending: Optional[int] = None
        self.nuki: List[List[int]] = [[] for _ in range(M)]
        self.dora_indicators: List[int] = []
        self.kans = 0
        self.draws = 0                 # 山から引いた枚数（嶺上を除く）
        self.calls = 0                 # 鳴き・カンの回数（九種九牌の「第一ツモ」判定）
        self.drawn: Optional[Tuple[int, int]] = None   # (who, tile) 直前のツモ
        self.last_discard: Optional[Tuple[int, int]] = None   # (who, tile)
        self.just_called: Optional[Tuple[int, dict]] = None   # (who, meld) 鳴き直後で打牌前
        self.first_draw_done = [False] * M
        self.ended = False

    def remove(self, who: int, tiles: List[int]):
        for t in tiles:
            try:
                self.hands[who].remove(t)
            except ValueError:
                raise ValidationError(f"seat {who} の手牌に牌 {t} が無い（再生失敗）")


def _initial_hands(rnd: dict, norm: dict, wall: Optional[dict]) -> List[List[int]]:
    M, N = norm["players"], norm["hand_size"]
    oya = rnd["state"]["oya"]
    evs = rnd["events"]
    if wall is None:
        hands = evs[0].get("hands")
        if not hands:
            raise ValidationError("wall が無く deal.hands も無いので局面を再生できない")
        return [list(h) for h in hands]
    order = wall["order"]
    hands = [[] for _ in range(M)]
    for s in range(M):
        hands[(oya + s) % M] = list(order[s * N:(s + 1) * N])
    return hands


def replay(rnd: dict, norm: dict, wall: Optional[dict], upto: int) -> State:
    """events[0..upto] を適用した状態。upto は含む。"""
    M = norm["players"]
    st = State(M)
    st.hands = _initial_hands(rnd, norm, wall)
    evs = rnd["events"]
    if upto < 0 or upto >= len(evs):
        raise ValidationError(f"at={upto} が events の範囲外")
    for i in range(upto + 1):
        e = evs[i]
        t = e["t"]
        if t == "deal":
            continue
        if t == "dora":
            st.dora_indicators.append(e["tile"])
        elif t == "draw":
            w = e["who"]
            st.hands[w].append(e["tile"])
            st.drawn = (w, e["tile"])
            st.just_called = None
            if not e.get("rinshan"):
                st.draws += 1
            st.first_draw_done[w] = True
        elif t == "discard":
            w = e["who"]
            st.remove(w, [e["tile"]])
            is_riichi = bool(e.get("riichi")) or st.riichi_pending == w
            st.discards[w].append({"tile": e["tile"], "tsumogiri": bool(e.get("tsumogiri")), "riichi": is_riichi, "called": False})
            if is_riichi:
                st.riichi[w] = True
            st.riichi_pending = None
            st.last_discard = (w, e["tile"])
            st.drawn = None
            st.just_called = None
        elif t in ("chi", "pon"):
            w, frm = e["who"], e["from"]
            called = st.last_discard[1] if st.last_discard else None
            own = [x for x in e["tiles"] if x != called]
            if len(own) != len(e["tiles"]) - 1:
                own = e["tiles"][:-1]
            st.remove(w, own)
            if st.discards[frm]:
                st.discards[frm][-1]["called"] = True
            meld = {"kind": t, "tiles": list(e["tiles"]), "from": frm, "called": called}
            st.melds[w].append(meld)
            st.calls += 1
            st.just_called = (w, meld)
            st.drawn = None
        elif t == "kan":
            w, kind = e["who"], e["kind"]
            if kind == "ankan":
                st.remove(w, e["tiles"])
                st.melds[w].append({"kind": "ankan", "tiles": list(e["tiles"]), "from": w})
            elif kind == "minkan":
                frm = e["from"]
                called = st.last_discard[1] if st.last_discard else None
                own = [x for x in e["tiles"] if x != called]
                st.remove(w, own)
                if st.discards[frm]:
                    st.discards[frm][-1]["called"] = True
                st.melds[w].append({"kind": "minkan", "tiles": list(e["tiles"]), "from": frm, "called": called})
            else:   # kakan
                pon = None
                for m in st.melds[w]:
                    if m["kind"] == "pon" and set(m["tiles"]) <= set(e["tiles"]):
                        pon = m
                        break
                if pon is None:
                    raise ValidationError(f"seat {w} の加槓に対応するポンが無い")
                added = [x for x in e["tiles"] if x not in pon["tiles"]]
                st.remove(w, added)
                pon["kind"] = "kakan"
                pon["tiles"] = list(e["tiles"])
            st.kans += 1
            st.calls += 1
            st.drawn = None
        elif t == "riichi":
            st.riichi_pending = e["who"]
        elif t == "nuki":
            w = e["who"]
            st.remove(w, [e["tile"]])
            st.nuki[w].append(e["tile"])
            st.drawn = None
        elif t in ("win", "draw_end"):
            st.ended = True
        elif t == "abort":
            if not e.get("resume"):
                st.ended = True
        elif t == "chombo":
            pass
        else:
            raise ValidationError(f"events[{i}].t が不明: {t!r}")
    return st


def _remaining(norm: dict, K: int, st: State) -> int:
    M, N = norm["players"], norm["hand_size"]
    live = K - norm["wall_rules"]["dead_wall"]
    # 嶺上が王牌内（配列）のとき、嶺上を 1 枚使うごとに海底が王牌に入り、ツモれる牌が 1 枚減る
    rin = norm["wall_rules"].get("rinshan")
    used = 0 if rin == "live" else st.kans + sum(len(x) for x in st.nuki)
    if norm["wall_rules"].get("rinshan_reserved") and isinstance(rin, list):
        used = max(0, used - len(rin))              # 補充用に取ってある牌を使う間は、ツモれる牌は減らない
    return live - N * M - st.draws - used


def phase_of(evs: List[dict], at: int, seat: int) -> Optional[str]:
    """at の event から判断の種類：A/B（seat 自身の draw）、C（他家の discard）、鳴き直後の打牌も B。"""
    e = evs[at]
    if e["t"] == "draw" and e["who"] == seat:
        return "A"
    if e["t"] == "discard" and e["who"] != seat:
        return "C"
    if e["t"] in ("chi", "pon") and e["who"] == seat:
        return "B"
    return None


def observe(rec: dict, round_index: int, at: int, seat: int, rs: dict, ts: dict,
            walls: Optional[Dict[str, dict]] = None, full: bool = False) -> dict:
    """局面のスナップショット。full=False なら seat 以外の手牌は出さない。"""
    norm = R.normalize(rs)
    M = norm["players"]
    if not (0 <= seat < M):
        raise ValidationError(f"seat {seat} が範囲外")
    rnd = next((r for r in rec["rounds"] if r["index"] == round_index), None)
    if rnd is None:
        raise ValidationError(f"round {round_index} が無い")
    wall = None
    if rnd.get("wall"):
        wall = (walls or {}).get(rnd["wall"]["id"])
        if wall is None:
            raise ValidationError(f"round {round_index} の wall {rnd['wall']['id'][:20]}… が読めない")
    st = replay(rnd, norm, wall, at)
    K = len(ts["tiles"])
    evs = rnd["events"]
    obs = {
        "seat": seat, "round": round_index, "at": at, "phase": phase_of(evs, at, seat),
        "state": dict(rnd["state"]),
        "hand": sorted(st.hands[seat]),
        "melds": [[{k: v for k, v in m.items() if k != "called"} for m in st.melds[s]] for s in range(M)],
        "discards": [[d["tile"] for d in st.discards[s]] for s in range(M)],
        "discard_flags": [[{"tsumogiri": d["tsumogiri"], "riichi": d["riichi"], "called": d["called"]} for d in st.discards[s]] for s in range(M)],
        "riichi": list(st.riichi),
        "nuki": [list(x) for x in st.nuki],
        "dora_indicators": list(st.dora_indicators),
        "remaining": _remaining(norm, K, st),
        "kans": st.kans,
        "drawn": st.drawn[1] if st.drawn and st.drawn[0] == seat else None,
        "last_discard": {"who": st.last_discard[0], "tile": st.last_discard[1]} if st.last_discard else None,
        "just_called": st.just_called[1]["kind"] if st.just_called and st.just_called[0] == seat else None,
        "just_called_tiles": list(st.just_called[1]["tiles"]) if st.just_called and st.just_called[0] == seat else None,
        "just_called_tile": st.just_called[1].get("called") if st.just_called and st.just_called[0] == seat else None,
        "first_turn": (st.calls == 0 and not any(st.nuki) and sum(1 for d in st.discards[seat]) == 0),   # 抜きも鳴きと同じ扱い
        "ended": st.ended,
    }
    # フリテンの判定用：自分の最後の打牌より後に他家が出した牌（同巡フリテン）、立直より後に他家が出した牌（立直後フリテン）。
    # いま反応する相手の牌（at の出来事）は含めない
    passed: List[int] = []
    passed_riichi: List[int] = []
    in_riichi = False
    for i, e in enumerate(evs[:at]):
        t = e["t"]
        if t == "discard" and e["who"] == seat:
            passed = []
            if e.get("riichi") or (i > 0 and evs[i - 1]["t"] == "riichi" and evs[i - 1]["who"] == seat):
                in_riichi = True
        elif e.get("who") != seat and (t == "discard" or t == "nuki" or (t == "kan" and e.get("kind") == "kakan")):
            x = e["tile"] if "tile" in e else None
            if x is None:                      # 加槓：ポンに足した 1 枚
                prev = [m for m in replay(rnd, norm, wall, i - 1).melds[e["who"]] if m["kind"] == "pon" and set(m["tiles"]) <= set(e["tiles"])]
                x = next((y for y in e["tiles"] if not prev or y not in prev[0]["tiles"]), None)
            if x is not None:
                passed.append(x)
                if in_riichi:
                    passed_riichi.append(x)
    obs["passed"] = passed
    obs["passed_riichi"] = passed_riichi
    if full:
        obs["hands"] = [sorted(h) for h in st.hands]
    return obs


def observe_full(rec, round_index, at, seat, rs, ts, walls=None) -> dict:
    return observe(rec, round_index, at, seat, rs, ts, walls, full=True)


# ---- 和了形 ------------------------------------------------------------------------------

def _counts(ts: dict, tiles: List[int]) -> Counter:
    return Counter(kind_of(ts, t) for t in tiles)


def _next_kind(kind: str, d: int) -> Optional[str]:
    n = int(kind[0]) + d
    return f"{n}{kind[1]}" if 1 <= n <= 9 else None


def _melds_from(c: Counter, kinds: List[str], i: int, need: int) -> bool:
    """c から need 個の面子（刻子・順子）が取れるか。kinds は並び順。"""
    if need == 0:
        return all(v == 0 for v in c.values())
    while i < len(kinds) and c[kinds[i]] == 0:
        i += 1
    if i >= len(kinds):
        return False
    k = kinds[i]
    if c[k] >= 3:
        c[k] -= 3
        if _melds_from(c, kinds, i, need - 1):
            c[k] += 3
            return True
        c[k] += 3
    if _is_number(k):
        k2, k3 = _next_kind(k, 1), _next_kind(k, 2)
        if k2 and k3 and c[k2] > 0 and c[k3] > 0:
            c[k] -= 1; c[k2] -= 1; c[k3] -= 1
            ok = _melds_from(c, kinds, i, need - 1)
            c[k] += 1; c[k2] += 1; c[k3] += 1
            if ok:
                return True
    return False


_KIND_ORDER = [f"{n}{s}" for s in SUITS for n in range(1, 10)] + list(HONORS)


_YAO = frozenset(k for k in _KIND_ORDER if _is_terminal_or_honor(k))
_KIND_SET = frozenset(_KIND_ORDER)
_complete_cache: Dict[tuple, bool] = {}


def _complete_kinds(kinds: tuple, meld_count: int, N: int) -> bool:
    """牌種の列（並べ替え済みの組）が和了形か。同じ手を何度も聞かれるので結果を覚えておく。"""
    key = (kinds, meld_count, N)
    hit = _complete_cache.get(key)
    if hit is not None:
        return hit
    c = Counter(kinds)
    ok = False
    need = (N - 1) // 3 - meld_count
    if all(k in _KIND_SET for k in c) and len(kinds) == need * 3 + 2:      # エクストラ牌などは標準形に入らない
        if N == 13 and meld_count == 0:
            if len(c) == 7 and all(v == 2 for v in c.values()):
                ok = True
            elif set(c) == _YAO and len(kinds) == 14:
                ok = True
        if not ok:
            ks = [k for k in _KIND_ORDER if c[k] > 0]
            for pair in ks:
                if c[pair] >= 2:
                    c[pair] -= 2
                    ok = _melds_from(c, ks, 0, need)
                    c[pair] += 2
                    if ok:
                        break
    if len(_complete_cache) > 500000:
        _complete_cache.clear()
    _complete_cache[key] = ok
    return ok


def is_complete(ts: dict, tiles: List[int], meld_count: int, N: int) -> bool:
    """tiles（手牌＋和了牌、副露を除く）が和了形か。標準形＝(N−1)/3 − meld_count 面子＋雀頭。
    13 枚で副露なしなら七対子・国士も和了形。"""
    tl = ts["tiles"]
    return _complete_kinds(tuple(sorted(tl[t]["kind"] for t in tiles)), meld_count, N)


def _almighty_tsumo(g: dict, ts: dict, hand: List[int], drawn: Optional[int], meld_count: int, N: int, riichi: bool) -> bool:
    """ツモった牌が「何にでも使える」印（白ポッチなど）で、その条件（立直中 など）に合い、残りの手が聴牌しているか。"""
    if drawn is None or drawn not in hand:
        return False
    t = ts["tiles"][drawn]
    rules = [o for o in g.get("mark_overrides") or [] if o.get("tile_id") == drawn or ("tile_kind" in o and o["tile_kind"] == t["kind"] and o.get("mark") == t.get("mark"))][:1]
    if not rules and t.get("mark") is not None and t["mark"] in (g.get("marks") or {}):
        rules = [g["marks"][t["mark"]]]
    for r in rules:
        w = r.get("when") or {}
        if "almighty" in r.get("effects", []) and w.get("how", "any") != "ron" and (w.get("state", "any") != "riichi" or riichi):
            rest = list(hand)
            rest.remove(drawn)
            return bool(waits(ts, rest, meld_count, N))
    return False


def waits(ts: dict, hand: List[int], meld_count: int, N: int) -> Set[str]:
    """手牌（3k+1 枚）に加えると和了形になる牌の種類。"""
    out = set()
    if len(hand) % 3 != 1:
        return out
    tl = ts["tiles"]
    base = [tl[t]["kind"] for t in hand]
    have = ts.get("_kinds")
    if have is None:
        have = frozenset(t["kind"] for t in tl)
    for k in _KIND_ORDER:
        if k in have and _complete_kinds(tuple(sorted(base + [k])), meld_count, N):
            out.add(k)
    return out


def tenpai_waits(ts: dict, hand: List[int], meld_count: int, N: int) -> Set[str]:
    """聴牌として数える待ち。waits のうち、自分の手牌（副露を除く）で 4 枚とも使っている牌種を除く。
    空なら聴牌ではない（自分で使い切った牌だけを待つ形は聴牌にしない。副露で使っている分は数えない）。"""
    tl = ts["tiles"]
    held: Dict[str, int] = {}
    for t in hand:
        held[tl[t]["kind"]] = held.get(tl[t]["kind"], 0) + 1
    total: Dict[str, int] = ts.get("_kind_counts")
    if total is None:
        total = {}
        for x in tl:
            total[x["kind"]] = total.get(x["kind"], 0) + 1
    return {k for k in waits(ts, hand, meld_count, N) if held.get(k, 0) < total.get(k, 0)}


# ---- 合法手 ------------------------------------------------------------------------------

def _menzen(melds: List[dict]) -> bool:
    return all(m["kind"] == "ankan" for m in melds)


def _furiten(ts: dict, obs: dict, ws: Set[str]) -> bool:
    """フリテン：待ちの牌が、自分の河にある／自分の最後の打牌より後に他家から出ている（同巡）／立直より後に他家から出ている。"""
    own = {kind_of(ts, t) for t in obs["discards"][obs["seat"]]}
    own |= {kind_of(ts, t) for t in obs.get("passed", [])}
    own |= {kind_of(ts, t) for t in obs.get("passed_riichi", [])}
    return bool(ws & own)


def _kuikae_kinds(ts: dict, mode: str, call: str, called: int, meld_tiles: List[int]) -> Set[str]:
    """鳴いた直後の打牌で禁止される種類（喰い替え）。call＝chi／pon、called＝鳴いた牌、meld_tiles＝できた面子の 3 枚。"""
    if mode == "allowed":
        return set()
    ck = kind_of(ts, called)
    out = {ck}
    if mode == "forbidden" and call == "chi":
        nums = sorted(int(kind_of(ts, t)[0]) for t in meld_tiles)
        if int(ck[0]) == nums[0]:
            nk = _next_kind(ck, 3)
            if nk:
                out.add(nk)
        elif int(ck[0]) == nums[2]:
            nk = _next_kind(ck, -3)
            if nk:
                out.add(nk)
    return out


def _kuikae_forbidden(ts: dict, obs: dict, norm: dict) -> Set[str]:
    """鳴き直後の打牌で禁止される種類。"""
    if not obs.get("just_called") or obs.get("just_called_tile") is None:
        return set()
    return _kuikae_kinds(ts, norm["game_rules"]["flow"]["kuikae"], obs["just_called"], obs["just_called_tile"], obs["just_called_tiles"])


def _call_leaves_discard(ts: dict, norm: dict, hand: List[int], call: str, called: int, meld_tiles: List[int]) -> bool:
    """この鳴きをしたあとに、切れる牌が手に残るか。残らない鳴き（喰い替えしかできない鳴き）はできない。"""
    forbid = _kuikae_kinds(ts, norm["game_rules"]["flow"]["kuikae"], call, called, meld_tiles)
    rest = list(hand)
    for t in meld_tiles:
        if t != called:
            rest.remove(t)
    return any(kind_of(ts, t) not in forbid for t in rest)


def can_rob(norm: dict, ts: dict, obs: dict, kind: str, tile: int) -> bool:
    """カン・抜きで見せた牌 tile を、obs の席がロンできるか（槍槓。形とフリテンだけを見る。役の有無は見ない）。
    kind は "kakan"／"ankan"／"nuki"。加槓と抜きの牌はロンできる。暗槓の牌は、ルールが認めていて
    （flow.kokushi_ankan_chankan）、国士無双の形のときだけ。大明槓の牌はロンできない。norm は R.normalize(rs)。"""
    g = norm["game_rules"]
    if g["agari_form"] != "standard" or kind not in ("kakan", "ankan", "nuki"):
        return False
    N = norm["hand_size"]
    seat = obs["seat"]
    hand = list(obs["hand"])
    melds = obs["melds"][seat]
    if kind == "ankan":
        if not g["flow"].get("kokushi_ankan_chankan") or melds or N != 13:
            return False
        if len(hand) != 13 or {kind_of(ts, t) for t in hand + [tile]} != _YAO:
            return False
    if not is_complete(ts, hand + [tile], len(melds), N):
        return False
    return not _furiten(ts, obs, waits(ts, hand, len(melds), N))


def legal_actions(rs: dict, ts: dict, obs: dict, phase: Optional[str] = None) -> List[dict]:
    """annotation 2.3.1 の形で列挙。obs は observe() の戻り値（seat 視点）。
    phase を省略すると obs["phase"]（draw → A）。打牌の選択は phase="B" で同じ局面から取る。"""
    norm = R.normalize(rs)
    g = norm["game_rules"]
    fl = g["flow"]
    M, N = norm["players"], norm["hand_size"]
    seat = obs["seat"]
    hand = list(obs["hand"])
    melds = obs["melds"][seat]
    standard = g["agari_form"] == "standard"
    phase = phase or obs.get("phase")
    acts: List[dict] = []
    if obs.get("ended") or phase is None:
        return acts
    if phase == "B" and obs.get("phase") == "C":
        return acts
    my_riichi = obs["riichi"][seat]
    remaining = obs["remaining"]
    scores = obs["state"]["scores"]

    def kinds_count(tiles):
        return _counts(ts, tiles)

    if phase == "A":
        drawn = obs["drawn"]
        # ツモ和了（和了形のみ）
        if standard and (is_complete(ts, hand, len(melds), N) or _almighty_tsumo(g, ts, hand, drawn, len(melds), N, my_riichi)):
            acts.append({"type": "tsumo"})
        # 九種九牌
        if standard and fl["ryukyoku"]["nine_terminals"] and obs["first_turn"] and not melds:
            yao = {kind_of(ts, t) for t in hand if _is_terminal_or_honor(kind_of(ts, t))}
            if len(yao) >= 9:
                acts.append({"type": "draw_declare", "reason": "nine_terminals"})
        # 抜き（海底では不可：抜くと嶺上から 1 枚補うので、ツモれる牌が残っていないと抜けない。カンと同じ）
        nk = g["nuki"]
        if nk["enabled"] and remaining >= 1:
            for t in sorted(set(hand)):
                if kind_of(ts, t) in nk["tiles"]:
                    acts.append({"type": "nuki", "tile": t})
        # カン（海底では不可、最大回数）
        my_kans = sum(1 for m in melds if m["kind"] in ("ankan", "minkan", "kakan"))
        per_ok = fl["max_kans_per_player"] is None or my_kans < fl["max_kans_per_player"]
        can_kan = remaining >= 1 and obs["kans"] < fl["max_kans"] and per_ok
        if can_kan:
            c = kinds_count(hand) if "ankan" in fl["kan_kinds"] else {}
            for k, v in c.items():
                if v == 4:
                    tiles = sorted(t for t in hand if kind_of(ts, t) == k)
                    if my_riichi:
                        mode = fl["riichi"]["ankan_after"]
                        if mode == "none":
                            continue
                        if drawn is None or kind_of(ts, drawn) != k:
                            continue
                        if mode == "if_shape_unchanged" and standard:
                            before = [t for t in hand if t != drawn]
                            after = [t for t in hand if kind_of(ts, t) != k]
                            if waits(ts, before, len(melds), N) != waits(ts, after, len(melds) + 1, N):
                                continue
                    acts.append({"type": "kan", "kind": "ankan", "tiles": tiles})
            for m in (melds if "kakan" in fl["kan_kinds"] else []):
                if m["kind"] == "pon":
                    pk = kind_of(ts, m["tiles"][0])
                    for t in sorted(set(hand)):
                        if kind_of(ts, t) == pk:
                            if my_riichi and (drawn is None or t != drawn):
                                continue
                            acts.append({"type": "kan", "kind": "kakan", "tiles": sorted(m["tiles"] + [t])})
        # 立直
        rr = fl["riichi"]
        if standard and not my_riichi and _menzen(melds):
            ok_points = scores[seat] >= rr["min_points"] or rr["below_min"] == "allowed"
            ok_draw = rr["without_draw"] or remaining >= M
            ok_houtei = rr["on_houtei"] or remaining >= 1
            if ok_points and ok_draw and ok_houtei:
                seen = set()
                for t in sorted(hand):
                    key = (kind_of(ts, t), ts["tiles"][t].get("mark"))
                    if key in seen:
                        continue
                    seen.add(key)
                    rest = list(hand)
                    rest.remove(t)
                    ws = waits(ts, rest, len(melds), N)
                    if not tenpai_waits(ts, rest, len(melds), N):
                        continue
                    if not rr["furiten_riichi"] and _furiten(ts, obs, ws):
                        continue
                    acts.append({"type": "riichi", "tile": t})
                    if fl["open_riichi"]["enabled"]:
                        acts.append({"type": "riichi", "tile": t, "open": True})
        acts.append({"type": "pass"})
        return acts

    if phase == "B":
        return _discards(ts, obs, norm, hand, my_riichi)

    # phase C：他家の打牌への反応
    ld = obs["last_discard"]
    if not ld or ld["who"] == seat:
        return acts
    tile = ld["tile"]
    k = kind_of(ts, tile)
    # ロン（和了形・フリテンでない）
    if standard and is_complete(ts, hand + [tile], len(melds), N):
        ws = waits(ts, hand, len(melds), N)
        if not _furiten(ts, obs, ws):
            acts.append({"type": "ron"})
    if remaining >= 1 and not my_riichi:
        same = sorted(t for t in hand if kind_of(ts, t) == k)
        if len(same) >= 2 and fl["pon"]:
            # ポン：赤の有無で候補が変わり得るので、組み合わせを種類（印）で区別
            seen = set()
            for i in range(len(same)):
                for j in range(i + 1, len(same)):
                    key = tuple(sorted((ts["tiles"][same[i]].get("mark"), ts["tiles"][same[j]].get("mark")), key=str))
                    if key in seen:
                        continue
                    seen.add(key)
                    tiles = sorted([same[i], same[j], tile])
                    if _call_leaves_discard(ts, norm, hand, "pon", tile, tiles):
                        acts.append({"type": "pon", "tiles": tiles})
        my_kans = sum(1 for m in melds if m["kind"] in ("ankan", "minkan", "kakan"))
        if (len(same) >= 3 and obs["kans"] < fl["max_kans"] and "minkan" in fl["kan_kinds"]
                and (fl["max_kans_per_player"] is None or my_kans < fl["max_kans_per_player"])):
            acts.append({"type": "kan", "kind": "minkan", "tiles": sorted(same[:3] + [tile])})
        if fl["chi"] and _is_number(k) and ld["who"] == (seat - 1) % M:
            n = int(k[0])
            byk: Dict[str, List[int]] = {}
            for t in hand:
                byk.setdefault(kind_of(ts, t), []).append(t)
            for a, b in ((-2, -1), (-1, 1), (1, 2)):
                ka, kb = _next_kind(k, a), _next_kind(k, b)
                if ka and kb and byk.get(ka) and byk.get(kb):
                    seen = set()
                    for ta in byk[ka]:
                        for tb in byk[kb]:
                            key = (ts["tiles"][ta].get("mark"), ts["tiles"][tb].get("mark"))
                            if key in seen:
                                continue
                            seen.add(key)
                            tiles = sorted([ta, tb, tile])
                            if _call_leaves_discard(ts, norm, hand, "chi", tile, tiles):
                                acts.append({"type": "chi", "tiles": tiles})
    acts.append({"type": "pass"})
    return acts


def _discards(ts: dict, obs: dict, norm: dict, hand: List[int], my_riichi: bool) -> List[dict]:
    out = []
    if my_riichi:
        d = obs.get("drawn")
        return [{"type": "discard", "tile": d}] if d is not None else []
    forbid = _kuikae_forbidden(ts, obs, norm)
    for t in sorted(set(hand)):
        if kind_of(ts, t) in forbid:
            continue
        out.append({"type": "discard", "tile": t})
    return out


def action_key(a: dict) -> tuple:
    """候補の同一性（type と牌）。"""
    t = a.get("type")
    if t in ("discard", "riichi", "nuki"):
        return (t, a.get("tile"), bool(a.get("open")))
    if t in ("chi", "pon"):
        return (t, tuple(sorted(a.get("tiles", []))))
    if t == "kan":
        return (t, a.get("kind"), tuple(sorted(a.get("tiles", []))))
    if t == "draw_declare":
        return (t, a.get("reason"))
    return (t,)


def actual_action(rec: dict, round_index: int, at: int, seat: int, phase: str) -> Optional[dict]:
    """record の次の event から、判断点で実際に選ばれた行動を作る（annotation 3.2-9）。"""
    rnd = next((r for r in rec["rounds"] if r["index"] == round_index), None)
    if rnd is None:
        return None
    evs = rnd["events"]
    j = at + 1
    while j < len(evs) and ((evs[j]["t"] == "abort" and evs[j].get("resume")) or evs[j]["t"] == "dora"):
        j += 1                                   # 切断→復帰の印、めくられたカンドラは判断に関係ない
    nxt = evs[j] if j < len(evs) else None
    if phase in ("A", "B"):
        if nxt is None:
            return None
        if nxt["t"] == "win" and nxt["who"] == seat and nxt["from"] == seat:
            return {"type": "tsumo"}
        if nxt["t"] == "kan" and nxt["who"] == seat:
            return {"type": "kan", "kind": nxt["kind"], "tiles": sorted(nxt["tiles"])}
        if nxt["t"] == "nuki" and nxt["who"] == seat:
            return {"type": "nuki", "tile": nxt["tile"]}
        if nxt["t"] == "riichi" and nxt["who"] == seat:
            d = evs[j + 1] if j + 1 < len(evs) else None
            if d and d["t"] == "discard":
                a = {"type": "riichi", "tile": d["tile"]}
                if nxt.get("open"):
                    a["open"] = True
                return a
            return None
        if nxt["t"] == "draw_end":
            return {"type": "draw_declare", "reason": nxt.get("reason")}
        if nxt["t"] == "discard" and nxt["who"] == seat:
            return {"type": "pass"} if phase == "A" else {"type": "discard", "tile": nxt["tile"]}
        return None
    # C
    if nxt is None:
        return {"type": "pass"}
    if nxt["t"] in ("chi", "pon") and nxt["who"] == seat:
        return {"type": nxt["t"], "tiles": sorted(nxt["tiles"])}
    if nxt["t"] == "kan" and nxt["who"] == seat and nxt["kind"] == "minkan":
        return {"type": "kan", "kind": "minkan", "tiles": sorted(nxt["tiles"])}
    if nxt["t"] == "draw_end" and nxt.get("reason") == "three_ron":
        return {"type": "ron"}                                # 三家和の流局：和了の出来事は残らないが、他家の全員がロンと言っている
    k = j
    while k < len(evs) and evs[k]["t"] == "win":             # 同じ打牌への複数のロン（ダブロン・トリロン）
        if evs[k]["who"] == seat and evs[k]["from"] != seat:
            return {"type": "ron"}
        k += 1
    return {"type": "pass"}
