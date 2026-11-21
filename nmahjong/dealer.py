"""進行役（4 層）。山を持ち、配牌・ツモ・鳴きの優先・流局・点棒の移動・連荘・終了・精算まで 1 対局を進める。

    d = Dealer(rs, ts, players={0: 打ち手, 1: 打ち手, …})        # 打ち手は gateway の FunctionPlayer／ProcessPlayer など
    rec = d.play(walls=lambda k, state: wall.build(ts, f"seed-{k}"))  # k 局目の山を返す関数（山の列でもよい）
    d.walls                                                         # 使った山 {id: wall}

使う部品：記録係（recorder）＝出来事を確かめて積む、接続口（gateway）＝打ち手とのやり取り、判定（judge）＝役と符、scoring＝点数と精算。
進行役が決めるのは、山から出る出来事（ツモ・嶺上・カンドラ）、誰に何を聞くか、反応の優先（ロン＞ポン・カン＞チー、頭ハネ・ダブロン）、
流局（荒牌・九種九牌・四風連打・四家立直・四槓・三家和）、局の結果（和了の点・ノーテン罰符・立直棒）、次の局（連荘・本場・供託）、
対局の終わり（規定局数・飛び・延長・和了止め・聴牌止め・本場の上限）、最終の順位と精算。どれも ruleset の設定に従う。
"""
import copy
import time
from typing import Callable, Dict, List, Optional

from . import gateway as GW, judge as J, observe as O, recorder as RC, ruleset as R, scoring as S
from .canon import ValidationError

WIND_ORDER = "ESWN"
_INFO = ("abort", "dora")


def unsupported(rs: dict) -> List[str]:
    """このルールの設定のうち、進行役がまだ従えないもの（空なら全部従える）。"""
    norm = R.normalize(rs)
    g, fl, end, sc = norm["game_rules"], norm["game_rules"]["flow"], norm["end"], norm["game_rules"]["scoring"]
    out = []
    if fl.get("wareme") and norm["players"] != 4:
        out.append("flow.wareme：四人打ち以外のわれめ（開門の家の決め方が四人打ちのものしか無い）")
    if fl["atozuke"] == "forbidden":
        out.append("flow.atozuke＝forbidden：先付け（片和了は可）の決め方の出典が無い。後付けありとして進める。片和了も不可の完全先付けは kanzen_sakizuke")
    nk = g.get("nuki") or {}
    if nk.get("enabled"):
        if nk.get("forbid_keep"):
            out.append("nuki.forbid_keep＝true：抜く牌を手に残すことを止める決まりは無い。残せるとして進める")
        if nk.get("pao"):
            out.append("nuki.pao＝true：抜きドラの責任払いは数えない")
    for c in norm["settlement"]["chips"]:
        if c.get("on") in ("kan", "nuki", "call", "yakitori"):
            out.append(f"settlement.chips の on＝{c['on']}：和了と飛び以外の祝儀は数えない")
    return out


class Dealer:
    def __init__(self, rs: dict, ts: dict, players: Optional[Dict[int, object]] = None, decide: Optional[Callable] = None,
                 player_info: Optional[List[dict]] = None, source: Optional[dict] = None, parent: Optional[dict] = None,
                 strict: bool = True, check_legal: bool = True, allow_unsupported: bool = False,
                 choose: Optional[Callable] = None, clock: Optional[Callable] = None):
        """players：席 → 打ち手（接続口ごしに聞く）。decide(seat, phase, at) -> 行動：接続口を通さずに直接決める関数（確認用）。
        strict=False：打ち手の壊れた応答・打てない手を既定の行動（ツモ切り／見送り）に置き換えて続ける。
        allow_unsupported=False：まだ従えない設定（unsupported(rs)）があるルールでは始めない。True：その設定を書いてある代わりの扱いで進める。
        choose(kind, seat, scores) -> bool：ルールが「選べる」としている所での選択。kind＝"agari_yame"・"tenpai_yame"（最終局で親がトップ。止めるなら True。
        既定は止める）、"agari_yame_not_top"（親がトップでないが止めてもよいルール。既定は続ける）。
        clock() -> 秒：時間制限（end.time_limit_sec）に使う時計。既定は time.monotonic。"""
        self._choose = choose
        self._clock = clock or time.monotonic
        self._t0 = None
        self.rs, self.ts = rs, ts
        self.norm = R.normalize(rs)
        self.unsupported = unsupported(rs)
        if self.unsupported and not allow_unsupported:
            raise ValidationError("進行役がまだ従えない設定がある：" + "／".join(self.unsupported))
        self.g = self.norm["game_rules"]
        self.fl = self.g["flow"]
        self.sc = self.g["scoring"]
        self.M, self.N = self.norm["players"], self.norm["hand_size"]
        self.rc = RC.Recorder(rs, ts, players=player_info, source=source or {"kind": "generated", "from": "nmahjong.dealer", "ref": None},
                              check_legal=check_legal, parent=parent)
        self.gw = GW.Gateway(self.rc, players or {}, strict=strict)
        self._decide = decide
        self.walls = self.rc.walls
        self.log: List[str] = []           # 進行役が自分で決めたことの記録（終了の理由など）

    # ==== 対局 ==============================================================================
    def play(self, walls, dice: Optional[Callable] = None, max_rounds: int = 1000, **top) -> dict:
        """1 対局を最後まで進めて、対局（record）を返す。walls：k 局目の山を返す関数 (k, state) -> wall、または山の列。"""
        st_rule = self.norm["settlement"]
        state = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [st_rule["start_points"]] * self.M}
        k = 0
        end = "finished"
        self._t0 = self._clock()
        while True:
            wall = walls(k, state) if callable(walls) else walls[k]
            if dice is not None:
                state["dice"] = list(dice(k, state))
            elif self.norm["wall_rules"]["break"]["by"] == "dice":
                h = int(wall["id"][-8:], 16)                  # サイコロの目は山の id から決める（同じ山なら同じ目）
                state["dice"] = [h % 6 + 1, (h // 6) % 6 + 1]
            if self.fl.get("wareme"):
                state["wareme"] = self.wareme_seat(state)
            result, info = self.play_round(state, wall)
            nxt, why = self.next_state(state, result, info, k)
            if nxt is None:
                self.log.append(f"終了：{why}")
                if why == "時間制限":
                    end = "time_limit"
                break
            state = nxt
            k += 1
            if k >= max_rounds:
                raise ValidationError(f"{max_rounds} 局を超えた（終了の条件を確かめる）")
        self.gw.flush()
        rec = self.rc.finish(end=end, **top)
        self.gw.flush()
        return rec

    # ==== 山 ================================================================================
    def _order(self):
        return self.rc._wall["order"]

    def _live_end0(self) -> int:
        return len(self._order()) - self.norm["wall_rules"]["dead_wall"]

    def _next_tile(self) -> Optional[int]:
        rc = self.rc
        return self._order()[rc._pos] if rc._pos < rc._live_end else None

    def _rinshan_tile(self) -> Optional[int]:
        rc = self.rc
        rin = self.norm["wall_rules"].get("rinshan")
        if rin == "live":
            return self._next_tile()
        if rc._rin_i < len(rin):
            return self._order()[self._live_end0() + rin[rc._rin_i]]
        return self._order()[rc._live_end - 1]

    def _dora_tile(self, n: int) -> Optional[int]:
        """n 枚目（0 始まり）のドラ表示牌。"""
        wr = self.norm["wall_rules"]
        di = wr.get("dora_indicator", [])
        offs = list(di) + list(wr.get("kan_dora", []))
        return self._order()[self._live_end0() + offs[n]] if n < len(offs) else None

    # ==== 局 ================================================================================
    def _evs(self):
        return self.rc.rec["rounds"][-1]["events"]

    def _anchor(self) -> int:
        evs = self._evs()
        a = len(evs) - 1
        while a > 1 and evs[a]["t"] in _INFO:
            a -= 1
        return a

    def _state(self):
        rnd = self.rc.rec["rounds"][-1]
        return O.replay(rnd, self.norm, self.rc._wall, len(rnd["events"]) - 1)

    def _winnable(self, seat: int, frm: int, tile: int) -> bool:
        rnd = self.rc.rec["rounds"][-1]
        ctx = J.context_at(self.rc.rec, rnd["index"], len(rnd["events"]) - 1, seat, frm, tile, self.rs, self.ts, self.walls, ura=[])
        return bool(J.judge(self.rs, self.ts, ctx).get("ok"))

    def _legal(self, seat: int, phase: str, at: int) -> List[dict]:
        """打てる手。和了は、役がある（縛りを満たす）ときだけ残す。"""
        obs, legal, _ = self.gw.legal(seat, phase, at)
        out = []
        for a in legal:
            if a["type"] == "tsumo" and not self._winnable(seat, seat, obs["drawn"]):
                continue
            if a["type"] == "ron" and not self._winnable(seat, obs["last_discard"]["who"], obs["last_discard"]["tile"]):
                continue
            out.append(a)
        return out

    def _ask(self, seat: int, phase: str, at: int) -> dict:
        """seat に判断を求める。見送りしか無ければ聞かない。"""
        if self._decide is not None:
            return self._decide(seat, phase, at) or {"type": "pass"}
        legal = self._legal(seat, phase, at)
        if not any(a["type"] != "pass" for a in legal):
            return {"type": "pass"}
        return self.gw.ask(seat, phase, at, legal=legal)

    def _ask_rob(self, kanner: int, tile: int, at: int, kind: str = "kakan") -> List[int]:
        """カン・抜きの牌へのロン（槍槓）を他家に聞く。ロンする席を巡目順に返す。"""
        out = []
        for k in range(1, self.M):
            s = (kanner + k) % self.M
            if self._decide is not None:
                a = self._decide(s, "C", at) or {"type": "pass"}
            else:
                obs, _, _ = self.gw.legal(s, "A", at)
                if not O.can_rob(self.norm, self.ts, obs, kind, tile) or not self._winnable(s, kanner, tile):
                    continue
                a = self.gw.ask(s, "C", at, legal=[{"type": "ron"}, {"type": "pass"}])
            if a["type"] == "ron":
                out.append(s)
        return out

    def _reveal(self, n: int) -> None:
        for _ in range(n):
            t = self._dora_tile(sum(1 for e in self._evs() if e["t"] == "dora"))
            if t is not None:
                self.rc.push({"t": "dora", "tile": t})

    def play_round(self, state: dict, wall: dict):
        """1 局を進める。戻り値は (result, info)。info＝{"dealer_tenpai", "abort"} など次の局を決める材料。"""
        rc, M = self.rc, self.M
        rc.start_round(state, wall)
        oya = state["oya"]
        d = self.g["dora"]
        timing = d.get("kan_timing") or {}
        self._sticks: List[int] = []         # この局で立直が成立した席（成立順）
        pending = 0                          # 打牌のあとにめくるカンドラの数
        seat = oya
        draw = "normal"
        while True:
            # ---- ツモ ----
            if draw == "normal":
                t = self._next_tile()
                if t is None:
                    return self._end_exhaustive(state)
                rc.push({"t": "draw", "who": seat, "tile": t})
            elif draw == "rinshan":
                t = self._rinshan_tile()
                if t is None:
                    return self._end_exhaustive(state)
                rc.push({"t": "draw", "who": seat, "tile": t, "rinshan": True})
                if after_rinshan:
                    self._reveal(after_rinshan)
            after_rinshan = 0
            at = self._anchor()
            # ---- 自分の番：宣言（A）----
            a = {"type": "pass"}
            if draw is not None:
                a = self._ask(seat, "A", at)
            t = a["type"]
            if t == "tsumo":
                self.gw.apply(seat, a, at)
                return self._end_win(state, [seat], seat)
            if t == "draw_declare":
                self.gw.apply(seat, a, at)
                return self._end_abort(state, a.get("reason") or "nine_terminals", show=[seat])
            if t in ("kan", "nuki"):
                self.gw.apply(seat, a, at)
                kan_at = len(self._evs()) - 1
                kind = a.get("kind") if t == "kan" else "nuki"
                if kind == "kakan" or t == "nuki" or (kind == "ankan" and self.fl.get("kokushi_ankan_chankan")):
                    tile = a["tile"] if t == "nuki" else self._added_tile(a, kan_at)
                    rons = self._ask_rob(seat, tile, kan_at, kind)
                    if rons:
                        rons = self._limit_rons(rons)
                        if rons is None:
                            self.rc.push({"t": "draw_end", "reason": "three_ron"})
                            return self._end_abort(state, "three_ron", show=[])
                        for s in rons:
                            self.rc.push({"t": "win", "who": s, "from": seat, "tile": tile})
                        return self._end_win(state, rons, seat)
                if pending:                                   # 前のカンのぶん（打牌待ち）は、次のカン・抜きでめくる
                    self._reveal(pending)
                    pending = 0
                if t == "kan" and d.get("kan"):
                    when = timing.get(kind, "immediate")
                    if when == "immediate":
                        self._reveal(1)
                    elif when == "after_rinshan":
                        after_rinshan = 1
                    else:
                        pending += 1
                draw = "rinshan"
                continue
            if t == "riichi":
                if pending:
                    self._reveal(pending)
                    pending = 0
                self.gw.apply(seat, a, at)
                riichi = True
            else:
                # ---- 打牌（B）----
                a = self._ask(seat, "B", at)
                if a["type"] != "discard":
                    raise ValidationError(f"seat {seat} の打牌が得られない: {a}")
                if pending:
                    self._reveal(pending)
                    pending = 0
                self.gw.apply(seat, a, at)
                riichi = False
            dat = self._anchor()
            # ---- 他家の反応（C）：ロン ＞ ポン・カン ＞ チー ----
            answers = []
            for k in range(1, M):
                s = (seat + k) % M
                r = self._ask(s, "C", dat)
                if r["type"] != "pass":
                    answers.append((s, r))
            rons = [s for s, r in answers if r["type"] == "ron"]
            if riichi and self.fl["riichi"].get("stick_if_ronned"):
                self._sticks.append(seat)                     # 宣言した時点で棒を出すルール
                riichi = False
            if rons:
                rons = self._limit_rons(rons)
                if rons is None:
                    self.rc.push({"t": "draw_end", "reason": "three_ron"})
                    return self._end_abort(state, "three_ron", show=[])
                tile = self._evs()[dat]["tile"]
                for s in rons:
                    self.rc.push({"t": "win", "who": s, "from": seat, "tile": tile})
                return self._end_win(state, rons, seat)
            if riichi:
                self._sticks.append(seat)
            ab = self._abort_after_discard(seat)
            if ab:
                self.rc.push({"t": "draw_end", "reason": ab[0]})
                return self._end_abort(state, ab[0], show=ab[1])
            call = next(((s, r) for s, r in answers if r["type"] in ("pon", "kan")), None) or next(((s, r) for s, r in answers if r["type"] == "chi"), None)
            if call:
                s, r = call
                self.gw.apply(s, r, dat)
                seat = s
                if r["type"] == "kan":
                    if d.get("kan"):
                        when = timing.get("minkan", "after_discard")
                        if when == "immediate":
                            self._reveal(1)
                        elif when == "after_rinshan":
                            after_rinshan = 1
                        else:
                            pending += 1
                    draw = "rinshan"
                else:
                    draw = None
                continue
            seat = (seat + 1) % M
            draw = "normal"

    def _added_tile(self, a: dict, kan_at: int) -> int:
        """カンで足した 1 枚（加槓＝ポンに足した牌、暗槓＝どれでも同じ牌種なので先頭）。"""
        if a.get("kind") != "kakan":
            return a["tiles"][0]
        rnd = self.rc.rec["rounds"][-1]
        before = O.replay(rnd, self.norm, self.rc._wall, kan_at - 1)
        seat = rnd["events"][kan_at]["who"]
        pon = next(m for m in before.melds[seat] if m["kind"] == "pon" and set(m["tiles"]) <= set(a["tiles"]))
        return next(x for x in a["tiles"] if x not in pon["tiles"])

    def _limit_rons(self, rons: List[int]) -> Optional[List[int]]:
        """同時のロンの扱い。None＝三家和で流局。"""
        fl = self.fl
        if len(rons) >= 3:
            if fl.get("triple_ron") == "draw":
                return None
            if fl.get("triple_ron") == "head":
                return rons[:1]
            return rons
        if len(rons) == 2 and not fl.get("double_ron"):
            return rons[:1]
        return rons

    def _abort_after_discard(self, seat: int):
        """打牌が通ったあとの途中流局。(理由, 手牌を見せる席) か None。"""
        ry = self.fl.get("ryukyoku") or {}
        st = self._state()
        M = self.M
        if ry.get("four_riichi") and M == 4 and all(st.riichi):
            return ("four_riichi", list(range(M)))
        if ry.get("four_winds") and M == 4 and st.calls == 0 and not any(st.nuki) and all(len(dd) == 1 for dd in st.discards):
            ks = {O.kind_of(self.ts, dd[0]["tile"]) for dd in st.discards}
            if len(ks) == 1 and next(iter(ks)) in ("E", "S", "W", "N"):
                return ("four_winds", [])
        if ry.get("four_kans") and st.kans == 4:
            owners = [s for s in range(M) if sum(1 for m in st.melds[s] if m["kind"] in ("ankan", "minkan", "kakan")) > 0]
            if len(owners) >= 2:
                return ("four_kans", [])
        return None

    # ==== 局の結果 ==========================================================================
    def wareme_seat(self, state: dict) -> int:
        """割れ目（開門の家）の席。出目の合計を親から反時計回りに数える：5・9＝親、2・6・10＝下家、3・7・11＝対面、4・8・12＝上家。
        サイコロを使わないルール（break.by＝fixed）では親。"""
        dice = state.get("dice")
        return (state["oya"] + sum(dice) - 1) % self.M if dice else state["oya"]

    def _base_deltas(self) -> List[int]:
        kp = self.sc["kyotaku_points"]
        d = [0] * self.M
        for s in self._sticks:
            d[s] -= kp
        return d

    def _end_win(self, state: dict, winners: List[int], frm: int):
        rc, M, sc = self.rc, self.M, self.sc
        rnd = rc.rec["rounds"][-1]
        evs = rnd["events"]
        first = next(i for i, e in enumerate(evs) if e["t"] == "win")
        oya = state["oya"]
        hp, kp = sc["honba_points"], sc["kyotaku_points"]
        wins = []
        scores = list(state["scores"])
        for j, w in enumerate(winners):
            e = evs[first + j]
            ctx = J.context_at(rc.rec, rnd["index"], first - 1, w, e["from"], e["tile"], self.rs, self.ts, self.walls)
            res = J.judge(self.rs, self.ts, ctx)
            if not res.get("ok"):
                raise ValidationError(f"seat {w} の和了を判定できない：{res.get('reason')}")
            tsumo = ctx["tsumo"]
            additive = sc["table"] == "additive"
            if additive:
                # 足し算の点数：本場は式の中で数える。ロンは放銃者が、ツモは残りの全員が、それぞれ同じ点を払う
                melds_all = self._melds_of(w, first)
                kinds = [O.kind_of(self.ts, t) for t in list(ctx["hand"]) + [t for m in melds_all if m["kind"] != "nuki" for t in m["tiles"]]]
                menzen = not any(m["kind"] in ("chi", "pon", "minkan", "kakan") for m in melds_all)
                karasu = S.karasu_kind(kinds, len(ctx.get("nuki") or []), menzen, self.g.get("nuki") or {})
                each, breakdown = S.additive_points(res["han"], res.get("yakuman", 0), w == oya, state["honba"], karasu, sc)
                total, parts = (each * (M - 1), [each] * (M - 1)) if tsumo else (each, [each])
            else:
                total, parts = S.total_points(res["fu"], res["han"], res.get("yakuman", 0), w == oya, tsumo, M, sc)
            deltas = self._base_deltas() if j == 0 else [0] * M
            before_hand = list(deltas)
            split = self.fl.get("kyotaku_to") == "split"        # 複数和了：kamicha＝本場と供託は最初（上家取り）の和了者だけ。split＝本場は各自、供託は等分
            honba = state["honba"] if (j == 0 or split) else 0
            if additive:
                honba = 0                                       # 本場は点の式に入っている
            standard = sc["payment"] == "standard"
            if tsumo and additive:
                others = [(w + k) % M for k in range(1, M)]
                pay = {s: each for s in others}
                for s in others:
                    deltas[s] -= each
                    deltas[w] += each
            elif tsumo:
                others = [(w + k) % M for k in range(1, M)]
                if standard:
                    per_h = hp // 3
                    if w == oya:
                        pay = {s: parts[0] for s in others}
                    else:
                        child = [s for s in others if s != oya]
                        pay = {oya: parts[0]}
                        for s, p in zip(child, parts[1:]):
                            pay[s] = p
                    for s, p in pay.items():
                        deltas[s] -= p + per_h * honba
                        deltas[w] += p + per_h * honba
                else:
                    s = others[0]
                    deltas[s] -= total + hp * honba
                    deltas[w] += total + hp * honba
            else:
                h = (hp // 3) * (M - 1) * honba if standard else hp * honba     # 通常の払い：1 人 100 点ぶん × 払う人数（4 人で 300、3 人で 200）
                deltas[e["from"]] -= total + h
                deltas[w] += total + h
            liable, share = self._pao(w, first, res)
            if liable is not None and liable != w:
                deltas = self._pao_deltas(deltas, state, j, w, e["from"], liable, share, total, honba, tsumo)
            wm = state.get("wareme") if self.fl.get("wareme") else None
            if wm is not None:
                # われめ：割れ目の席の和了は全員の払いが 2 倍、割れ目の席の払いは 2 倍。本場・供託・飛びの罰符は倍にしない
                if liable is not None and liable != w:
                    hand = self._pao_deltas(None, state, 1, w, e["from"], liable, share, total, 0, tsumo)
                else:
                    hand = [0] * M
                    if not tsumo:
                        hand[e["from"]] = -total
                    elif standard:
                        for s, p in pay.items():
                            hand[s] = -p
                    else:
                        hand[others[0]] = -total
                for s in range(M):
                    if s != w and hand[s] < 0 and (w == wm or s == wm):
                        deltas[s] += hand[s]
                        deltas[w] -= hand[s]
            if res.get("reverse"):
                # 逆ポッチ：和了は成立するが、点（本場を含む）は和了者が払う側になる。供託はふつうどおり和了者が取る
                deltas = [b - (d - b) for d, b in zip(deltas, before_hand)]
            sticks = state["kyotaku"] + len(self._sticks)
            if split:
                deltas[w] += kp * (sticks // len(winners) + (sticks % len(winners) if j == 0 else 0))     # 割り切れない分は上家
            elif j == 0:
                deltas[w] += kp * sticks
            win = {"who": w, "from": e["from"], "tile": e["tile"], "hand": sorted(ctx["hand"]),
                   "melds": self._melds_of(w, first),
                   "yaku": res["yaku"], "fu": res["fu"], "han": res["han"], "points": total, "deltas": deltas}
            if res.get("yakuman"):
                win["yakuman"] = res["yakuman"]
            if additive:
                win["fu"] = 0
                win["additive"] = breakdown
            if (ctx["riichi"] or ctx["open_riichi"]) and self.g["dora"].get("ura"):
                win["ura_indicators"] = list(ctx["ura_indicators"])
            if liable is not None and liable != w:
                win["pao"] = liable
            if res.get("reverse"):
                win["reverse"] = True
            chip_rules = self.norm["settlement"]["chips"]
            if chip_rules:
                # 祝儀：和了者の手牌と副露（抜いた牌を含む）で数える。ロンは放銃者、ツモは全員（payer＝loser）。逆ポッチは払う側
                ms = self._melds_of(w, first)
                wc = S.win_chips(chip_rules, self.ts, list(ctx["hand"]) + [t for m in ms for t in m["tiles"]], res["yaku"], res.get("yakuman", 0), tsumo,
                                 not any(m["kind"] in ("chi", "pon", "minkan", "kakan") for m in ms), e["tile"])
                win["chips"] = S.chip_deltas(wc, w, e["from"], M, bool(res.get("reverse")))
            wins.append(win)
            scores = [a + b for a, b in zip(scores, deltas)]
        result = {"wins": wins, "draw": None, "scores": scores}
        pen = self._tobi_penalty(scores, winners[0], [x for x in range(M) if x not in winners])
        if pen:
            for p in pen:                                       # 飛ばした和了（上家取りの和了者）の増減に入れる
                wins[0]["deltas"][p["from"]] -= p["points"]
                wins[0]["deltas"][p["to"]] += p["points"]
                scores[p["from"]] -= p["points"]
                scores[p["to"]] += p["points"]
            result["tobi_penalty"] = pen
        tc = [{"from": s, "to": winners[0], "chips": sum(c["count"] for c in self.norm["settlement"]["chips"] if c.get("on") == "tobi")}
              for s in range(M) if s not in winners and self._busted(scores[s])]
        tc = [x for x in tc if x["chips"]]
        if tc:
            for x in tc:                                        # 飛びの祝儀：飛んだ人が、飛ばした和了（上家取りの和了者）に払う
                wins[0]["chips"][x["from"]] -= x["chips"]
                wins[0]["chips"][x["to"]] += x["chips"]
            result["tobi_chips"] = tc
        rc.end_round(result)
        self.gw.flush()
        return result, {"kind": "win", "winners": winners, "dealer_won": oya in winners}

    def _busted(self, x: int) -> bool:
        tb = self.norm["end"].get("tobi") or {}
        at = tb.get("at", 0)
        return bool(tb.get("enabled")) and (x < at or (x == at and bool(tb.get("exact_zero_is_tobi"))))

    def _tobi_penalty(self, scores: List[int], to: Optional[int], payers: List[int]) -> List[dict]:
        """飛びの罰符（end.tobi.penalty_points）。飛んだ席（payers のうち持ち点が飛びの条件に当たる席）が、飛ばした席 to に払う。
        to＝None のときは払わない。戻り値は [{"from", "to", "points"}]（増減への反映は呼ぶ側）。"""
        tb = self.norm["end"].get("tobi") or {}
        P = tb.get("penalty_points") or 0
        if not P or to is None or tb.get("penalty_to", "none") == "none":
            return []
        return [{"from": s, "to": to, "points": P} for s in payers if s != to and self._busted(scores[s])]

    def _pao(self, w: int, upto: int, res: dict):
        """包（責任払い）。(責任のある席, 役満の倍数のうち包にあたる分の割合) か (None, 0)。
        大三元＝三元牌の副露 3 つめを鳴かせた人、大四喜＝風牌の副露 4 つめを鳴かせた人、四槓子＝4 つめの大明槓をさせた人。"""
        names = self.g["pao"].get("yakuman") or []
        ym = {y["name"]: y["yakuman"] for y in res["yaku"] if "yakuman" in y}
        if not ym or not names:
            return None, 0
        melds = [m for m in self._melds_of(w, upto) if m["kind"] != "nuki"]
        kind = lambda m: O.kind_of(self.ts, m["tiles"][0])   # noqa: E731
        opened = lambda m: m["kind"] in ("pon", "minkan", "kakan")   # noqa: E731
        liable, mult = None, 0
        for name, group, need in (("daisangen", ("P", "F", "C"), 3), ("daisuushii", ("E", "S", "W", "N"), 4)):
            if name in ym and name in names:
                ms = [m for m in melds if kind(m) in group]
                if len(ms) == need and all(opened(m) for m in ms) and ms[-1]["from"] != w:
                    liable, mult = ms[-1]["from"], mult + ym[name]
        if "suukantsu" in ym and "suukantsu" in names:
            ks = [m for m in melds if m["kind"] in ("ankan", "minkan", "kakan")]
            if len(ks) == 4 and ks[-1]["kind"] == "minkan" and ks[-1]["from"] != w:
                liable, mult = ks[-1]["from"], mult + ym["suukantsu"]
        if liable is None:
            return None, 0
        return liable, mult / sum(ym.values())

    def _pao_deltas(self, deltas, state, j, w, frm, liable, share, total, honba, tsumo):
        """包のある和了の点の動き。ツモ＝責任者が全部払う（複合役満のほかの役満の分も）。
        ロン＝pao.ron が split なら包にあたる役満の分を放銃者と半分ずつ（ほかの役満の分は放銃者）、
        split_all なら複合役満を含む全部を半分ずつ、full なら包にあたる分を責任者が全部。
        本場の分は pao.honba_kyotaku（discarder＝放銃者、liable＝責任者）。"""
        M, sc, pao = self.M, self.sc, self.g["pao"]
        hp = sc["honba_points"]
        d = self._base_deltas() if j == 0 else [0] * M
        hon = ((hp // 3) * (M - 1) if sc["payment"] == "standard" else hp) * honba
        if tsumo:
            d[liable] -= total + hon
        else:
            ron = pao.get("ron", "split")
            part = total if ron == "split_all" else int(total * share)     # 包にあたる分
            rest = total - part
            if ron in ("split", "split_all"):
                half = part // 2
                d[liable] -= half
                d[frm] -= part - half + rest
            else:
                d[liable] -= part
                d[frm] -= rest
            d[frm if pao.get("honba_kyotaku", "discarder") == "discarder" else liable] -= hon
        d[w] += total + hon
        return d

    def _melds_of(self, seat: int, upto: int) -> List[dict]:
        """和了者の副露を、出来事の順に（抜きも 1 つとして入れる）。加槓はポンを置き換える。"""
        out: List[dict] = []
        evs = self._evs()
        for e in evs[:upto]:
            if e.get("who") != seat:
                continue
            if e["t"] in ("chi", "pon"):
                out.append({"kind": e["t"], "tiles": list(e["tiles"]), "from": e["from"]})
            elif e["t"] == "kan":
                if e["kind"] == "kakan":
                    m = next(m for m in out if m["kind"] == "pon" and set(m["tiles"]) <= set(e["tiles"]))
                    m["kind"], m["tiles"] = "kakan", list(e["tiles"])
                else:
                    out.append({"kind": e["kind"], "tiles": list(e["tiles"]), "from": e.get("from", seat)})
            elif e["t"] == "nuki":
                out.append({"kind": "nuki", "tiles": [e["tile"]], "from": seat})
        return out

    def tenpai(self, st, seat: int) -> bool:
        hand = st.hands[seat]
        return bool(O.tenpai_waits(self.ts, hand, len(st.melds[seat]), self.N))

    def _end_exhaustive(self, state: dict):
        rc, M, sc = self.rc, self.M, self.sc
        st = self._state()
        nm = self.g.get("nagashi_mangan") or {}
        ten = [self.tenpai(st, s) for s in range(M)]
        deltas = self._base_deltas()
        reason = "exhaustive"
        nagashi = []
        if nm.get("enabled"):
            for s in range(M):
                ds = st.discards[s]
                if ds and all(O._is_terminal_or_honor(O.kind_of(self.ts, x["tile"])) and not x["called"] for x in ds):
                    nagashi.append(s)
        oya = state["oya"]
        as_ = nm.get("as", "tenpai_settlement")
        if nagashi:
            # as：tenpai_settlement・draw_mangan＝流局の扱いで満貫のツモの額、yakuman＝流局の扱いで役満のツモの額、
            #     win＝和了の扱い（満貫のツモの額に、本場と供託も取る。連荘は親が流し満貫のときだけ）
            reason = "nagashi_mangan"
            for j, w in enumerate(nagashi):
                if sc["table"] == "additive":       # 足し算の点数：満貫は 5 翻ぶん、役満は役満の点を、残りの全員がそれぞれ払う
                    each, _ = S.additive_points(0 if as_ == "yakuman" else 5, 1 if as_ == "yakuman" else 0, w == oya, state["honba"], None, sc)
                    parts = [each] * (M - 1)
                else:
                    _, parts = S.total_points(30, 5, 1 if as_ == "yakuman" else 0, w == oya, True, M, sc)
                others = [(w + k) % M for k in range(1, M)]
                if w == oya:
                    pay = {s: parts[0] for s in others}
                else:
                    pay = {oya: parts[0]}
                    for s, p in zip([s for s in others if s != oya], parts[1:]):
                        pay[s] = p
                hon = (sc["honba_points"] // 3) * state["honba"] if (as_ == "win" and j == 0 and sc["payment"] == "standard") else 0
                for s, p in pay.items():
                    deltas[s] -= p + hon
                    deltas[w] += p + hon
                if as_ == "win" and j == 0:
                    deltas[w] += sc["kyotaku_points"] * (state["kyotaku"] + len(self._sticks))
        if not nagashi or (nm.get("noten_penalty") and as_ != "win"):
            total = sc["noten_penalty"]
            n = sum(ten)
            if total and 0 < n < M:
                unit = total // 3 if M <= 4 else total // (M - 1)          # 4 人麻雀の 1000 点単位（3000 のとき）
                if M == 4:
                    gain, loss = total // n, total // (M - n)
                elif M == 3:
                    gain, loss = (2 * unit) // n if n == 1 else unit, unit if n == 1 else 2 * unit
                else:
                    gain = loss = total
                for s in range(M):
                    deltas[s] += gain if ten[s] else -loss
        self.rc.push({"t": "draw_end", "reason": reason})
        scores = [a + b for a, b in zip(state["scores"], deltas)]
        # 飛びの罰符：ノーテン罰符（流し満貫の払い）で飛んだとき、聴牌者（流し満貫の人）のうち、飛んだ席から見て最初の席へ
        tb = self.norm["end"].get("tobi") or {}
        pen = []
        if tb.get("penalty_to") == "tenpai_players" and tb.get("on_noten_penalty", True):
            takers = nagashi if nagashi else [s for s in range(M) if ten[s]]
            for s in range(M):
                if s in takers or deltas[s] >= 0:
                    continue
                to = next(((s + k) % M for k in range(1, M) if (s + k) % M in takers), None)
                pen += self._tobi_penalty(scores, to, [s])
            for p in pen:
                deltas[p["from"]] -= p["points"]
                deltas[p["to"]] += p["points"]
                scores[p["from"]] -= p["points"]
                scores[p["to"]] += p["points"]
        draw = {"reason": reason, "tenpai": ten, "hands": [sorted(st.hands[s]) if ten[s] else None for s in range(M)], "deltas": deltas}
        result = {"wins": [], "draw": draw, "scores": scores}
        if pen:
            result["tobi_penalty"] = pen
        rc.end_round(result)
        self.gw.flush()
        info = {"kind": "draw", "reason": reason, "dealer_tenpai": ten[oya], "any_tenpai": any(ten), "nagashi": nagashi}
        if nagashi and as_ == "win":
            info["nagashi_win"] = True
        return result, info

    def _end_abort(self, state: dict, reason: str, show: List[int]):
        """途中流局。show＝手牌を見せる席（九種九牌の宣言者、四家立直の全員）。"""
        rc, M = self.rc, self.M
        st = self._state()
        deltas = self._base_deltas()
        ten = [s in show for s in range(M)]
        draw = {"reason": reason, "tenpai": ten, "hands": [sorted(st.hands[s]) if ten[s] else None for s in range(M)], "deltas": deltas}
        result = {"wins": [], "draw": draw, "scores": [a + b for a, b in zip(state["scores"], deltas)]}
        rc.end_round(result)
        self.gw.flush()
        return result, {"kind": "abort", "reason": reason}

    # ==== 次の局・対局の終わり ================================================================
    def next_state(self, state: dict, result: dict, info: dict, k: int):
        """局の結果から次の局の state を作る。対局が終わるなら (None, 理由)。"""
        norm, fl, M = self.norm, self.fl, self.M
        end = norm["end"]
        oya = state["oya"]
        scores = list(result["scores"])
        kp = self.sc["kyotaku_points"]
        rule = dict(fl["renchan"])
        rule.update((rule.get("by_bakaze") or {}).get(state["bakaze"], {}))
        if info["kind"] == "win":
            renchan = info["dealer_won"] and rule.get("dealer_win", True)
            honba = state["honba"] + 1 if renchan else 0
            kyotaku = 0
        elif info["kind"] == "abort":
            renchan = bool(fl.get("renchan_on_abort", True))
            honba = state["honba"] + 1
            kyotaku = state["kyotaku"] + len(self._sticks)
        elif info.get("nagashi_win"):                        # 流し満貫を和了の扱いにするルール：親が流し満貫なら連荘、供託は取られている
            renchan = oya in info["nagashi"] and rule.get("dealer_win", True)
            honba = state["honba"] + 1 if renchan else 0
            kyotaku = 0
        else:
            dt = info["dealer_tenpai"]
            renchan = bool(rule.get("draw")) or (dt and rule.get("dealer_tenpai", True)) or (not info["any_tenpai"] and rule.get("all_noten")) \
                or (not dt and rule.get("dealer_noten", False))
            if info.get("nagashi") and not (self.g.get("nagashi_mangan") or {}).get("renchan_if_dealer_tenpai", True):
                renchan = False                                 # 流し満貫の局は親が流れるルール
            honba = state["honba"] + 1
            kyotaku = state["kyotaku"] + len(self._sticks)
        # ---- 終わるか ----
        tobi = end.get("tobi") or {}
        if tobi.get("enabled"):
            at = tobi.get("at", 0)
            by_noten = info["kind"] == "draw" and not tobi.get("on_noten_penalty", True)      # ノーテン罰符の払いでは飛ばないルール
            if not by_noten and any(x < at or (x == at and tobi.get("exact_zero_is_tobi")) for x in scores):
                return None, "飛び"
        cold = end.get("cold_points")
        if cold is not None and max(scores) >= cold:
            return None, "コールド"
        limit = end.get("time_limit_sec")
        if limit is not None and self._t0 is not None and self._clock() - self._t0 >= limit:
            return None, "時間制限"                           # その局を終えて終了
        length = norm["length"]
        winds = {"one": 0, "east": 1, "east_south": 2, "full": 4}.get(length)
        total = norm.get("rounds_total")
        bi = WIND_ORDER.index(state["bakaze"])
        last_regular = (length == "one") or (winds is not None and winds > 0 and bi == winds - 1 and state["kyoku"] == M) \
            or (length == "custom" and total is not None and bi * M + state["kyoku"] >= total)
        in_extension = winds is not None and winds > 0 and bi >= winds
        ext = end.get("extension") or {}
        top = max(scores)
        dealer_top = scores[oya] == top and sum(1 for x in scores if x == top) == 1
        reached = (not ext.get("enabled")) or top >= ext.get("until_points", 0)
        mh = end.get("max_honba")
        if mh is not None and honba > mh:
            return None, "本場の上限"
        if length == "one":
            return None, "1 局"
        if in_extension and reached and not (renchan and ext.get("renchan_first")):
            return None, "延長：規定の点に届いた"         # renchan_first：親が連荘したら連荘を優先し、下の和了止め・聴牌止めだけで終わる
        if last_regular or in_extension:
            if renchan:
                ay, ty = end.get("agari_yame") or {}, end.get("tenpai_yame") or {}
                # forced＝トップなら必ず止める。forced でなければ choose に聞く（既定は止める）。
                # others_may_continue＝トップでない親も、止めるか続けるかを選べる（既定は続ける）
                ask = lambda kind, default: default if self._choose is None else bool(self._choose(kind, oya, list(scores)))   # noqa: E731
                if info["kind"] == "win" and ay.get("enabled") and reached:
                    if dealer_top and (ay.get("forced") or ask("agari_yame", True)):
                        return None, "和了止め"
                    middle = any(x > scores[oya] for x in scores) and any(x < scores[oya] for x in scores)   # トップでもラスでもない
                    if not dealer_top and middle and ay.get("others_may_continue") and ask("agari_yame_not_top", False):
                        return None, "和了止め"
                if info["kind"] == "draw" and ty.get("enabled") and dealer_top and reached and (info.get("dealer_tenpai") or not ty.get("require_tenpai", True)):
                    if ty.get("forced") or ask("tenpai_yame", True):
                        return None, "聴牌止め"
            else:
                is_last_wind_round = state["kyoku"] == M
                if last_regular and reached:
                    return None, "規定の局数"
                if in_extension and is_last_wind_round:
                    played_ext = bi - winds + 1
                    if ext.get("once") or played_ext * M >= ext.get("max_rounds", M) or bi >= 3:
                        return None, "延長の上限"
                if last_regular and not ext.get("enabled"):
                    return None, "規定の局数"
        # ---- 次の局 ----
        if fl.get("next_dealer") == "winner":
            # 和了した人が次の親（場と局は進まない）。親が和了すれば本場が増え、子が和了すれば 0 に戻る。流局は上の連荘の決まりどおり
            if total is not None and k + 1 >= total:
                return None, "規定の局数"
            if info["kind"] == "win":
                no = info["winners"][0]
                return {"bakaze": state["bakaze"], "kyoku": state["kyoku"], "honba": state["honba"] + 1 if no == oya else 0,
                        "kyotaku": kyotaku, "oya": no, "scores": scores}, None
            # 流局：本場は「親が続けて和了した回数」なので増やさない。親が替わるなら 0 に戻す
            no = oya if renchan else (oya + 1) % M
            return {"bakaze": state["bakaze"], "kyoku": state["kyoku"], "honba": state["honba"] if renchan else 0, "kyotaku": kyotaku, "oya": no, "scores": scores}, None
        if renchan:
            nb, nk, no = state["bakaze"], state["kyoku"], oya
        else:
            no = (oya + 1) % M
            nk = state["kyoku"] + 1
            nb = state["bakaze"]
            if nk > M:
                nk = 1
                nb = WIND_ORDER[(bi + 1) % 4]
        return {"bakaze": nb, "kyoku": nk, "honba": honba, "kyotaku": kyotaku, "oya": no, "scores": scores}, None


# ---- 確認用：出来上がった対局を、同じ山・同じ判断で進行役に進め直させる -------------------------------

def replay_with_dealer(rec: dict, rs: dict, ts: dict, walls: Dict[str, dict], through_gateway: bool = False, check_legal: bool = False) -> Dealer:
    """記録の山と、記録どおりの判断（各席の実際の行動）を与えて、進行役に 1 対局を進めさせる。
    山から出る出来事・反応の優先・局の結果・次の局・終了・精算は、進行役が自分で決める。戻り値の .rc.rec が進め直した対局。
    through_gateway=True：判断を接続口ごし（状況を送り、応答を受け取る）に求める。False：記録から直接取る（速い）。"""
    norm = R.normalize(rs)
    M = norm["players"]
    extra = {k: copy.deepcopy(v) for k, v in rec.items() if k not in ("format", "version", "id", "source", "ruleset", "players", "end", "parent", "rounds", "final")}
    if through_gateway:
        d = Dealer(rs, ts, players={s: GW.ReplayPlayer(rec, ts, s) for s in range(M)}, player_info=copy.deepcopy(rec["players"]),
                   source=copy.deepcopy(rec["source"]), parent=copy.deepcopy(rec.get("parent")), check_legal=True)
    else:
        def decide(seat, phase, at):
            ri = len(d.rc.rec["rounds"]) - 1
            return O.actual_action(rec, ri, at, seat, phase)
        d = Dealer(rs, ts, decide=decide, player_info=copy.deepcopy(rec["players"]), source=copy.deepcopy(rec["source"]),
                   parent=copy.deepcopy(rec.get("parent")), check_legal=check_legal)
    rounds = rec["rounds"]
    # 切断・復帰の印（abort、resume つき）は対局の進行ではないので、記録にある位置へそのまま入れる
    push0 = d.rc.push

    def sync():
        cur = d.rc.rec["rounds"][-1]
        src = rounds[cur["index"]]["events"] if cur["index"] < len(rounds) else []
        while len(cur["events"]) < len(src) and src[len(cur["events"])]["t"] == "abort" and src[len(cur["events"])].get("resume"):
            push0(copy.deepcopy(src[len(cur["events"])]))

    def push(ev):
        sync()
        push0(ev)
        sync()
    d.rc.push = push

    def wall_of(k, state):
        if k >= len(rounds):
            raise ValidationError(f"進行役が {k + 1} 局目に進んだが、記録は {len(rounds)} 局で終わっている")
        return walls[rounds[k]["wall"]["id"]]

    def dice_of(k, state):
        if k >= len(rounds):
            raise ValidationError(f"進行役が {k + 1} 局目に進んだが、記録は {len(rounds)} 局で終わっている（次の局 {state}）")
        return rounds[k]["state"]["dice"]
    has_dice = "dice" in rounds[0]["state"]
    d.play(wall_of, dice=dice_of if has_dice else None, **extra)
    return d


def differences(a: dict, b: dict, merge_dora: bool = False) -> Optional[str]:
    """2 つの対局（record）の進行と結果を比べる。同じなら None、違えば最初の違いの文。
    並び順だけの違いは見ない（和了の手牌・副露・役の並び）。役満の符は比べない。merge_dora=True：抜きドラ・カンドラを「ドラ」にまとめて比べる（天鳳の書き方）。"""
    from collections import Counter

    def nw(w):
        w = dict(w)
        w["melds"] = sorted(w.get("melds") or [], key=lambda m: m["tiles"])
        w["hand"] = sorted(w["hand"])
        c: Counter = Counter()
        for y in w.get("yaku") or []:
            n = "dora" if merge_dora and y["name"] in ("kan_dora", "nuki_dora") else y["name"]
            if y.get("yakuman") or y.get("han"):
                c[(n, "yakuman" in y)] += y.get("yakuman") or y.get("han")
        w["yaku"] = sorted(c.items())
        if w.get("yakuman"):
            w["fu"] = None
        return w

    for k, (ra, rb) in enumerate(zip(a["rounds"], b["rounds"])):
        if ra["state"] != rb["state"]:
            return f"round {k} の始まり（state）が違う：{ra['state']} ／ {rb['state']}"
        if ra["events"] != rb["events"]:
            i = next((i for i, (x, y) in enumerate(zip(ra["events"], rb["events"])) if x != y), min(len(ra["events"]), len(rb["events"])))
            return f"round {k} の出来事 {i} 番目が違う：{ra['events'][i:i + 1]} ／ {rb['events'][i:i + 1]}"
        x, y = ra.get("result") or {}, rb.get("result") or {}
        wa, wb = [nw(w) for w in x.get("wins") or []], [nw(w) for w in y.get("wins") or []]
        if wa != wb:
            for p, q in zip(wa, wb):
                for key in sorted(set(p) | set(q)):
                    if p.get(key) != q.get(key):
                        return f"round {k} の和了（seat {p.get('who')}）の {key} が違う：{p.get(key)} ／ {q.get(key)}"
            return f"round {k} の和了の数が違う：{len(wa)} ／ {len(wb)}"
        if x.get("draw") != y.get("draw"):
            return f"round {k} の流局が違う：{x.get('draw')} ／ {y.get('draw')}"
        if x.get("scores") != y.get("scores"):
            return f"round {k} の結果の持ち点が違う：{x.get('scores')} ／ {y.get('scores')}"
    if len(a["rounds"]) != len(b["rounds"]):
        return f"局の数が違う：{len(a['rounds'])} ／ {len(b['rounds'])}"
    for key in ("final", "end"):
        if a.get(key) != b.get(key):
            return f"{key} が違う：{a.get(key)} ／ {b.get(key)}"
    return None
