"""同梱の評価器（最小）。annotation.md §6 の nm-basic（勝率）は 1 枚・4 枚麻雀の全探索が要るので別途。
ここでは器と検証を実際に通すための評価器を置く：

nm-waits（visibility actor）：打牌（phase B）ごとに「その牌を切った後の待ちの種類数」を候補の値 waits（count）に出す。
  聴牌しない打牌は 0。役の有無は見ない。局面の値 remaining（count）に残りツモ数。
"""
from typing import Dict, List, Optional

from . import annotation as A
from . import observe as O
from . import ruleset as R

EVALUATORS = ("nm-waits",)


def _meta(evaluator: str, run_at: Optional[str] = None) -> dict:
    ev = {"name": "nm-waits", "version": "0.1", "visibility": "actor",
          "metrics": [{"name": "waits", "scope": "candidate", "kind": "count", "higher_is_better": True, "primary": True, "unit": "種"},
                      {"name": "remaining", "scope": "point", "kind": "count", "unit": "枚"}],
          "params": {"verdict": {"o": 0, "d": 1}}}
    if run_at:
        ev["run_at"] = run_at
    return ev


def point_at(rec: dict, rnd: dict, at: int, rs: dict, ts: dict, walls: Optional[Dict[str, dict]], norm: dict,
             seats: Optional[List[int]] = None):
    """events[at] の判断点の評価。戻り値：point（dict）／None（評価の対象でない）／False（まだ決まっていない：続きの出来事が要る）。"""
    M, N = norm["players"], norm["hand_size"]
    evs = rnd["events"]
    e = evs[at]
    if e["t"] != "draw":
        return None
    seat = e["who"]
    if seats and seat not in seats:
        return None
    nxt = [x for x in evs[at + 1:] if x["t"] not in ("dora", "abort")]
    if not nxt:
        return False                                   # このツモへの行動がまだ届いていない
    if nxt[0]["t"] == "riichi" and len(nxt) < 2:
        return False                                   # 立直の宣言だけ届いた（宣言牌の打牌を待つ）
    if O.actual_action(rec, rnd["index"], at, seat, "A") != {"type": "pass"}:
        return None
    actual = O.actual_action(rec, rnd["index"], at, seat, "B")
    if not actual or actual["type"] != "discard":
        return None
    obs = O.observe(rec, rnd["index"], at, seat, rs, ts, walls)
    legal = O.legal_actions(rs, ts, obs, "B")
    if not legal:
        return None
    melds = len(obs["melds"][seat])
    cands = []
    for a in legal:
        rest = list(obs["hand"])
        rest.remove(a["tile"])
        w = len(O.waits(ts, rest, melds, N)) if norm["game_rules"]["agari_form"] == "standard" else 0
        cands.append({"type": "discard", "tile": a["tile"], "values": {"waits": w}})
    vals = [c["values"]["waits"] for c in cands]
    best = vals.index(max(vals))
    ai = next(i for i, c in enumerate(cands) if O.action_key(c) == O.action_key(actual))
    loss = vals[best] - vals[ai]
    verdict = "o" if loss <= 0 else "d" if loss <= 1 else "x"
    return {"round": rnd["index"], "at": at, "phase": "B", "actor": seat, "actual": actual,
            "candidates": cands, "estimates": {"remaining": obs["remaining"]},
            "best": best, "loss": loss, "verdict": verdict, "note": None}


def annotate(rec: dict, rs: dict, ts: dict, walls: Optional[Dict[str, dict]] = None,
             evaluator: str = "nm-waits", seats: Optional[List[int]] = None, run_at: Optional[str] = None) -> dict:
    """出来上がった対局に、まとめて評価を付ける。"""
    if evaluator not in EVALUATORS:
        raise ValueError(f"評価器 {evaluator} は同梱していない（{EVALUATORS}）")
    norm = R.normalize(rs)
    points = []
    for rnd in rec["rounds"]:
        for at in range(len(rnd["events"])):
            p = point_at(rec, rnd, at, rs, ts, walls, norm, seats)
            if p:
                points.append(p)
    ann = {"format": A.FORMAT, "version": A.VERSION, "record": {"id": rec["id"]}, "evaluator": _meta(evaluator, run_at), "points": points}
    return A.finalize(ann)


class LiveAnnotator:
    """行動が届くたびに評価を付ける。記録係につなぐと、出来事が 1 つ積まれるたびに、新しく決まった判断点を評価する。

        live = LiveAnnotator(rs, ts)              # on_point=関数 を渡すと、評価が 1 つ付くたびに呼ばれる（その場で見せる用）
        live.attach(recorder)                     # 記録係（進行役なら dealer.rc）につなぐ
        …対局を進める…
        ann = live.finish(recorder.rec)           # 対局が閉じたあと（id が決まったあと）に評価ファイルにする

    記録係を使わないときは、出来事を積むたびに live.update(rec, walls) を呼ぶ。戻り値は新しく付いた評価の列。
    まとめて付けた評価（annotate）と同じ結果になる。"""

    def __init__(self, rs: dict, ts: dict, evaluator: str = "nm-waits", seats: Optional[List[int]] = None,
                 run_at: Optional[str] = None, on_point=None):
        if evaluator not in EVALUATORS:
            raise ValueError(f"評価器 {evaluator} は同梱していない（{EVALUATORS}）")
        self.rs, self.ts, self.evaluator, self.seats, self.run_at = rs, ts, evaluator, seats, run_at
        self.norm = R.normalize(rs)
        self.points: List[dict] = []
        self.on_point = on_point
        self._round = 0          # 次に見る局（rounds の位置）
        self._at = 0             # その局の、次に見る出来事の位置
        self._walls: Optional[Dict[str, dict]] = None

    def attach(self, recorder) -> "LiveAnnotator":
        self._walls = recorder.walls
        recorder.listeners.append(lambda rec: self.update(rec, recorder.walls))
        return self

    def update(self, rec: dict, walls: Optional[Dict[str, dict]] = None) -> List[dict]:
        new: List[dict] = []
        rounds = rec["rounds"]
        while self._round < len(rounds):
            rnd = rounds[self._round]
            evs = rnd["events"]
            closed = "result" in rnd and rnd["result"] is not None
            while self._at < len(evs):
                p = point_at(rec, rnd, self._at, self.rs, self.ts, walls, self.norm, self.seats)
                if p is False and not closed:
                    break                              # 続きの出来事を待つ
                if p:
                    new.append(p)
                self._at += 1
            if self._at < len(evs) or not closed:
                break
            self._round += 1
            self._at = 0
        self.points += new
        if self.on_point:
            for p in new:
                self.on_point(p)
        return new

    def finish(self, rec: dict, walls: Optional[Dict[str, dict]] = None) -> dict:
        self.update(rec, walls if walls is not None else self._walls)
        ann = {"format": A.FORMAT, "version": A.VERSION, "record": {"id": rec["id"]}, "evaluator": _meta(self.evaluator, self.run_at),
               "points": self.points}
        return A.finalize(ann)
