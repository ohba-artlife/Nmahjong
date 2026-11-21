"""記録係：出来事を 1 つずつ受け取り、その場で確かめながら対局（record）を積む（overview.md §0・§6.3 の apply）。

使い方：
    rec = Recorder(ruleset, tileset, players=[...], source={...})
    rec.start_round(state, wall)          # state＝{bakaze, kyoku, honba, kyotaku, oya, scores}。deal と最初の dora は自動で積む
    rec.push({"t": "draw", "who": 0, "tile": 52})
    rec.push({"t": "discard", "who": 0, "tile": 52, "tsumogiri": True})
    …
    rec.end_round(result)                 # result＝{wins, draw, scores}（役・符・点数は渡す側が持ってくる。進行役は judge で出す）
    record = rec.finish()                 # final を計算し、id を付け、対局全体を検証して返す

push が確かめること：
- ツモ：山の次の牌か（牌山があるとき）。嶺上はルールの位置どおりか
- 打牌・立直・カン・ポン・チー・抜き・和了：その席の、その時点の合法手（observe → legal_actions）に入っているか
- 手牌に無い牌を切る・鳴く、局が終わったあとの出来事
- 槍槓（加槓・抜きの牌へのロン。暗槓の牌は、ルールが認める国士無双だけ）：O.can_rob
確かめないこと：見送り（出来事にならない）、役と符の中身（judge.py）。確かめなかった点は warnings に残す。
違反は ValidationError。違反した出来事は積まれない（積む前の状態のまま）。
"""
import copy
from typing import Dict, List, Optional

from . import observe as O, record as REC, ruleset as R, scoring as S
from .canon import ValidationError

_INFO = ("abort", "dora")                             # 誰の判断でもない出来事（切断・復帰の印、カンドラ）


class Recorder:
    def __init__(self, rs: dict, ts: dict, players: Optional[List[dict]] = None, source: Optional[dict] = None,
                 check_legal: bool = True, parent: Optional[dict] = None):
        self.rs, self.ts = rs, ts
        self.norm = R.normalize(rs)
        self.M, self.N = self.norm["players"], self.norm["hand_size"]
        self.check_legal = check_legal
        self.walls: Dict[str, dict] = {}
        self.warnings: List[str] = []
        self.rec = {"format": REC.FORMAT, "version": REC.VERSION,
                    "source": source or {"kind": "generated", "from": "nmahjong.recorder", "ref": None},
                    "ruleset": R.ref(rs),
                    "players": players or [{"seat": s, "name": f"seat{s}", "external": []} for s in range(self.M)],
                    "end": "finished", "parent": parent, "rounds": []}
        self._open = False          # 局の途中か
        self._riichi_at = None      # 立直の宣言を積んだ位置（次の打牌とあわせて確かめる）
        self._pos = 0               # 山の次のツモ位置
        self._live_end = 0
        self._rin_i = 0
        self._wall = None
        self.listeners: List = []   # 出来事が積まれるたび・局が閉じるたびに呼ぶ関数 f(rec)（逐次の評価など）

    def _notify(self) -> None:
        for f in self.listeners:
            f(self.rec)

    # ---- 局の始まり・終わり ----------------------------------------------------------------
    def start_round(self, state: dict, wall: Optional[dict] = None, dora: Optional[int] = None) -> dict:
        if self._open:
            raise ValidationError("前の局が終わっていない（end_round が先）")
        for k in ("bakaze", "kyoku", "honba", "kyotaku", "oya", "scores"):
            if k not in state:
                raise ValidationError(f"state.{k} が無い")
        if len(state["scores"]) != self.M or not (0 <= state["oya"] < self.M):
            raise ValidationError("state.scores の長さか oya が人数と合わない")
        wr = self.norm["wall_rules"]
        evs = [{"t": "deal"}]
        if wall is not None:
            if wall["tileset"]["id"] != self.ts["id"]:
                raise ValidationError("牌山の牌表がルールの牌表と違う")
            self.walls[wall["id"]] = wall
            order = wall["order"]
            self._live_end = len(order) - wr["dead_wall"]
            self._pos = self.N * self.M
            exp = order[self._live_end + wr["dora_indicator"][0]] if wr.get("dora_indicator") else None
            if dora is not None and exp is not None and dora != exp:
                raise ValidationError(f"ドラ表示牌 {dora} が牌山の {exp} と違う")
            dora = exp if dora is None else dora
        if dora is not None:
            evs.append({"t": "dora", "tile": dora})
        self._wall = wall
        self._rin_i = 0
        self._riichi_at = None
        rnd = {"index": len(self.rec["rounds"]), "wall": {"id": wall["id"]} if wall is not None else None,
               "state": copy.deepcopy(state), "events": evs}
        self.rec["rounds"].append(rnd)
        self._open = True
        return rnd

    def end_round(self, result: dict) -> dict:
        rnd = self._cur()
        if not rnd["events"] or rnd["events"][-1]["t"] not in ("win", "draw_end", "abort", "chombo"):
            raise ValidationError("局を閉じる出来事（win／draw_end／abort／chombo）がまだ積まれていない")
        for k in ("wins", "draw", "scores"):
            if k not in result:
                raise ValidationError(f"result.{k} が無い")
        rnd["result"] = copy.deepcopy(result)
        self._open = False
        self._notify()
        return rnd

    def finish(self, final: Optional[dict] = None, end: str = "finished", **top) -> dict:
        """対局を閉じる。final を省くと最後の局の持ち点から順位と精算を計算する（残った供託は stick_at_end に従う）。"""
        if self._open:
            raise ValidationError("局が終わっていない（end_round が先）")
        if not self.rec["rounds"]:
            raise ValidationError("局が 1 つも無い")
        rec = self.rec
        rec["end"] = end
        rec.update(top)
        if final is None:
            st = self.norm["settlement"]
            last = rec["rounds"][-1]
            scores = list(last["result"]["scores"])
            left = sum(last["state"]["scores"]) + last["state"]["kyotaku"] * self.norm["game_rules"]["scoring"]["kyotaku_points"] - sum(scores)
            if left > 0 and self.norm["game_rules"]["flow"]["riichi"]["stick_at_end"] == "to_first":
                scores[S.ranks(scores, tie=st["tie"]).index(1)] += left
            final = {"scores": scores, "rank": S.ranks(scores, tie=st["tie"]), "settled": S.settle(scores, st)}
            if st["chips"]:                                      # 祝儀の規則があるルール：各和了の祝儀の合計
                M = len(scores)
                final["chips"] = [sum(w["chips"][s] for r in rec["rounds"] for w in r["result"].get("wins") or [] if isinstance(w.get("chips"), list)) for s in range(M)]
        rec["final"] = final
        rec["id"] = REC.compute_id(rec)
        self.warnings += REC.validate(rec, self.rs, self.ts, self.walls)
        return rec

    # ---- 出来事を 1 つ積む -----------------------------------------------------------------
    def push(self, ev: dict) -> None:
        rnd = self._cur()
        evs = rnd["events"]
        t = ev.get("t")
        if t not in REC.EVENT_TYPES or t == "deal":
            raise ValidationError(f"出来事の種類が不正: {t!r}")
        if evs[-1]["t"] in ("draw_end", "chombo") or (evs[-1]["t"] == "win" and t not in ("win",) + _INFO):
            raise ValidationError(f"局が終わっている（{evs[-1]['t']} のあとに {t}）")
        if "who" in ev and not (isinstance(ev["who"], int) and 0 <= ev["who"] < self.M):
            raise ValidationError(f"who が範囲外: {ev.get('who')!r}")
        at = len(evs) - 1
        while at > 1 and evs[at]["t"] in _INFO:                 # 切断・復帰の印、めくられたカンドラは判断の基準にしない
            at -= 1
        if t in _INFO:
            evs.append(copy.deepcopy(ev))
            self._notify()
            return
        if t == "draw":
            self._check_draw(ev, evs)
        elif t == "riichi":
            self._legal_self(ev, evs, at, need=None)            # 自分の番かだけ見る。中身は次の打牌で
            self._riichi_at = at
        elif t == "discard":
            if self._riichi_at is not None:
                r = evs[self._riichi_at + 1]
                if r["who"] != ev["who"]:
                    raise ValidationError("立直を宣言した人と打牌した人が違う")
                a = {"type": "riichi", "tile": ev["tile"]}
                if r.get("open"):
                    a["open"] = True
                self._legal(ev["who"], self._riichi_at, "A", a)
                self._riichi_at = None
            else:
                self._legal_self(ev, evs, at, need={"type": "discard", "tile": ev["tile"]}, phase="B")
        elif t == "kan":
            a = {"type": "kan", "kind": ev.get("kind"), "tiles": sorted(ev.get("tiles", []))}
            if ev.get("kind") == "minkan":
                self._legal(ev["who"], self._last_discard_at(evs), "C", a)
            else:
                self._legal_self(ev, evs, at, need=a, phase="A")
        elif t in ("chi", "pon"):
            self._legal(ev["who"], self._last_discard_at(evs), "C", {"type": t, "tiles": sorted(ev.get("tiles", []))})
        elif t == "nuki":
            self._legal_self(ev, evs, at, need={"type": "nuki", "tile": ev["tile"]}, phase="A")
        elif t == "win":
            self._check_win(ev, evs)
        elif t == "draw_end":
            self._check_draw_end(ev, evs, at)
        if self._riichi_at is not None and t not in ("riichi",):
            raise ValidationError("立直の宣言のあとは打牌が続く")
        evs.append(copy.deepcopy(ev))
        try:                                                    # 手牌に無い牌を動かしていないか（再生できるか）
            O.replay(rnd, self.norm, self._wall, len(evs) - 1)
        except ValidationError:
            evs.pop()
            if t == "riichi":
                self._riichi_at = None
            raise
        self._notify()

    # ---- 中身 ----------------------------------------------------------------------------
    def _cur(self) -> dict:
        if not self._open:
            raise ValidationError("局が始まっていない（start_round が先）")
        return self.rec["rounds"][-1]

    def _last_discard_at(self, evs) -> int:
        for i in range(len(evs) - 1, -1, -1):
            if evs[i]["t"] == "discard":
                return i
            if evs[i]["t"] not in ("win",) + _INFO:
                break
        raise ValidationError("直前が打牌ではない（鳴き・ロンは打牌に対してだけ）")

    def _obs(self, seat: int, at: int) -> dict:
        return O.observe(self.rec, self.rec["rounds"][-1]["index"], at, seat, self.rs, self.ts, self.walls)

    def _legal(self, seat: int, at: int, phase: str, action: dict) -> None:
        if not self.check_legal:
            return
        obs = self._obs(seat, at)
        legal = O.legal_actions(self.rs, self.ts, obs, phase=phase)
        if self._key(action) not in {self._key(a) for a in legal}:
            raise ValidationError(f"seat {seat} の {action} は合法手に無い（時点 {at}、候補 {len(legal)} 件）")

    def _key(self, a: dict) -> tuple:
        """候補との照合の鍵。牌の番号ではなく「牌種と印」で比べる（同じ牌種・同じ印の牌は、どの 1 枚を使っても同じ行動。
        legal_actions は立直・鳴きの候補を牌種の組ごとに 1 つだけ挙げる）。"""
        tiles = self.ts["tiles"]
        if a.get("type") in ("discard", "riichi", "nuki") and isinstance(a.get("tile"), int):
            t = tiles[a["tile"]]
            return (a["type"], t["kind"], t.get("mark"), bool(a.get("open")))
        if a.get("type") in ("chi", "pon", "kan"):               # 鳴き・カンも、使う牌の牌種と印の組で比べる
            return (a["type"], a.get("kind"), tuple(sorted((tiles[x]["kind"], tiles[x].get("mark") or "") for x in a.get("tiles", []))))
        return O.action_key(a)

    def _legal_self(self, ev, evs, at, need, phase="A") -> None:
        seat = ev["who"]
        ph = O.phase_of(evs, at, seat)
        if ph not in ("A", "B"):
            raise ValidationError(f"seat {seat} の番ではない（直前は {evs[at]['t']}）")
        if need is None:
            return
        if ph == "B" and phase == "A":
            raise ValidationError(f"鳴いた直後は打牌だけ（{ev['t']} は不可）")
        self._legal(seat, at, phase, need)

    def _check_draw(self, ev, evs) -> None:
        last = next((e for e in reversed(evs) if e["t"] not in _INFO), evs[0])
        if last["t"] == "draw":
            raise ValidationError("ツモが 2 回続いている")
        if self._wall is None:
            return
        order = self._wall["order"]
        wr = self.norm["wall_rules"]
        if ev.get("rinshan"):
            rin = wr.get("rinshan")
            if rin == "live":
                exp = order[self._pos] if self._pos < self._live_end else None
                self._pos += 1
            else:
                live_end0 = len(order) - wr["dead_wall"]
                if self._rin_i < len(rin):
                    o = rin[self._rin_i]
                    exp = order[live_end0 + o] if o >= 0 else order[live_end0 + o]
                    shrink = 0 if wr.get("rinshan_reserved") else 1      # 補充用に取ってある牌を使う間は、ツモれる牌は減らない
                else:
                    exp = order[self._live_end - 1]
                    shrink = 1
                self._rin_i += 1
                self._live_end -= shrink
            back = ("rin",)
        else:
            exp = order[self._pos] if self._pos < self._live_end else None
            self._pos += 1
            back = ("pos",)
        if exp is None or ev.get("tile") != exp:
            if back == ("pos",) or wr.get("rinshan") == "live":
                self._pos -= 1
            else:
                self._rin_i -= 1
                self._live_end += shrink
            raise ValidationError(f"ツモ牌 {ev.get('tile')} が牌山の次の牌 {exp} と違う" if exp is not None else "牌山にツモれる牌が残っていない")

    def _check_win(self, ev, evs) -> None:
        who, frm = ev.get("who"), ev.get("from")
        if frm == who:
            at = len(evs) - 1
            while at > 1 and evs[at]["t"] in _INFO:
                at -= 1
            self._legal_self(ev, evs, at, need={"type": "tsumo"}, phase="A")
            return
        i = next((k for k in range(len(evs) - 1, -1, -1) if evs[k]["t"] not in ("win",) + _INFO), None)
        last = evs[i] if i is not None else None
        if last is not None and last["t"] in ("kan", "nuki"):
            # 槍槓：加槓・抜きの牌へのロン。暗槓の牌は、ルールが認める国士無双だけ（O.can_rob）
            kind = last.get("kind") if last["t"] == "kan" else "nuki"
            shown = [last["tile"]] if last["t"] == "nuki" else list(last.get("tiles", []))
            if frm != last["who"] or ev.get("tile") not in shown:
                raise ValidationError(f"seat {who} のロンは、直前のカン・抜き（seat {last['who']}）の牌に対するものではない")
            if self.check_legal and not O.can_rob(self.norm, self.ts, self._obs(who, i), kind, ev["tile"]):
                raise ValidationError(f"seat {who} の槍槓（{kind} の牌へのロン）は合法手に無い（時点 {i}）")
            return
        self._legal(who, self._last_discard_at(evs), "C", {"type": "ron"})

    def _check_draw_end(self, ev, evs, at) -> None:
        if ev.get("reason") == "exhaustive" and self._wall is not None and self._pos < self._live_end and evs[-1]["t"] != "draw":
            raise ValidationError(f"山が {self._live_end - self._pos} 枚残っているのに荒牌流局")


def replay_record(rec: dict, rs: dict, ts: dict, walls: Optional[Dict[str, dict]] = None, check_legal: bool = True) -> Recorder:
    """出来上がった対局を 1 手ずつ記録係に流し込む（TEST T9-5）。戻り値の .rec が積み直した対局、.warnings が確かめなかった点。"""
    r = Recorder(rs, ts, players=copy.deepcopy(rec["players"]), source=copy.deepcopy(rec["source"]),
                 check_legal=check_legal, parent=copy.deepcopy(rec.get("parent")))
    for rnd in rec["rounds"]:
        wall = (walls or {}).get(rnd["wall"]["id"]) if rnd.get("wall") else None
        evs = rnd["events"]
        dora = next((e["tile"] for e in evs[:3] if e["t"] == "dora"), None)
        cur = r.start_round(rnd["state"], wall, dora=dora)
        start = len(cur["events"])
        if [e["t"] for e in evs[:start]] != [e["t"] for e in cur["events"]]:
            cur["events"] = [copy.deepcopy(e) for e in evs[:1]]
            start = 1
        for e in evs[start:]:
            r.push(e)
        r.end_round(rnd["result"])
    extra = {k: copy.deepcopy(v) for k, v in rec.items() if k not in ("format", "version", "id", "source", "ruleset", "players", "end", "parent", "rounds", "final")}
    r.finish(final=copy.deepcopy(rec["final"]), end=rec["end"], **extra)
    return r
