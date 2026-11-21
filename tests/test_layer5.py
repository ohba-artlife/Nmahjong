"""5 層：逐次の評価（evaluate.LiveAnnotator、試験 T13-1・T13-2）と対戦場（arena、試験 T13-3・T13-4）。"""
import copy
import os
import sys
import unittest

from nmahjong import annotation as A, arena as AR, bots as B, dealer as D, evaluate as E, gateway as GW, recorder as RC, ruleset as R, tileset as TS, wall as W

from corpus import nm_games, sp_game

HERE = os.path.dirname(__file__)


def feed(rec, rs, ts, wm, live):
    """対局の出来事を 1 つずつ記録係に積む。局が閉じる前に付いた評価の数を返す。"""
    r = RC.Recorder(rs, ts, players=copy.deepcopy(rec["players"]), source=copy.deepcopy(rec["source"]), check_legal=False,
                    parent=copy.deepcopy(rec.get("parent")))
    live.attach(r)
    early = 0
    for rnd in rec["rounds"]:
        evs = rnd["events"]
        wall = wm.get(rnd["wall"]["id"]) if rnd.get("wall") else None
        cur = r.start_round(rnd["state"], wall, dora=next((e["tile"] for e in evs[:3] if e["t"] == "dora"), None))
        for e in evs[len(cur["events"]):]:
            r.push(e)
        early += len(live.points)
        r.end_round(rnd["result"])
    extra = {k: copy.deepcopy(v) for k, v in rec.items() if k not in ("format", "version", "id", "source", "ruleset", "players", "end", "parent", "rounds", "final")}
    r.finish(final=copy.deepcopy(rec["final"]), end=rec["end"], **extra)
    return r, early


class TestLiveAnnotation(unittest.TestCase):
    def test_L1_live_equals_batch(self):
        games = [g for n_tiles in (4, 1) for g in nm_games(n_tiles)]
        games.append(sp_game("tenhou-4p-hanchan-red"))
        games.append(sp_game("tenhou-3p"))
        pts = 0
        for rec, walls, rs, ts in games:
            wm = {w["id"]: w for w in walls}
            batch = E.annotate(rec, rs, ts, wm)
            live = E.LiveAnnotator(rs, ts)
            r, early = feed(rec, rs, ts, wm, live)
            ann = live.finish(r.rec)
            self.assertEqual(r.rec["id"], rec["id"])
            self.assertEqual(ann["id"], batch["id"])
            A.validate(ann, rec, rs, ts, wm)
            pts += len(ann["points"])
        self.assertGreater(pts, 300)

    def test_L2_points_arrive_as_actions_arrive(self):
        rec, walls, rs, ts = nm_games(4)[0]
        wm = {w["id"]: w for w in walls}
        seen = []
        live = E.LiveAnnotator(rs, ts, on_point=lambda p: seen.append((p["round"], p["at"])))
        r = RC.Recorder(rs, ts, players=copy.deepcopy(rec["players"]), source=copy.deepcopy(rec["source"]), check_legal=False)
        live.attach(r)
        rnd = rec["rounds"][0]
        cur = r.start_round(rnd["state"], wm[rnd["wall"]["id"]])
        evs = rnd["events"]
        i = len(cur["events"])
        r.push(evs[i])                                      # 最初のツモ：まだ行動が届いていない
        self.assertEqual(seen, [])
        self.assertEqual(evs[i + 1]["t"], "discard")
        r.push(evs[i + 1])                                  # 打牌が届いた：その場で評価が付く
        self.assertEqual(seen, [(0, i)])
        self.assertEqual(live.points[0]["actual"]["tile"], evs[i + 1]["tile"])

    def test_L3_live_with_dealer(self):
        rs = R.find(name="nm-2p-4-mps")
        ts = TS.find(id=rs["tileset"]["id"])
        d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.simple, wants_events=False) for s in range(2)})
        live = E.LiveAnnotator(rs, ts).attach(d.rc)
        rec = d.play(lambda k, st: W.build(ts, f"live-{k}"))
        ann = live.finish(rec)
        self.assertEqual(ann["id"], E.annotate(rec, rs, ts, d.walls)["id"])
        self.assertTrue(ann["points"])


class TestArena(unittest.TestCase):
    def setUp(self):
        self.rs = R.find(name="nm-2p-4-mps")
        self.ts = TS.find(id=self.rs["tileset"]["id"])
        self.ent = {"simple": lambda: GW.FunctionPlayer(B.simple, wants_events=False), "tsumogiri": lambda: GW.FunctionPlayer(B.tsumogiri, wants_events=False)}

    def test_AR1_table_and_determinism(self):
        seen = []
        a = AR.run(self.rs, self.ts, self.ent, games=4, seed="t", on_game=lambda rec, walls, names: seen.append((rec["id"], tuple(names))))
        b = AR.run(self.rs, self.ts, self.ent, games=4, seed="t")
        self.assertEqual(a, b)                               # 同じ種・同じ打ち手なら同じ結果
        self.assertEqual(a["games"], 8)                      # 4 組 × 席を入れ替えて 2 回
        self.assertEqual(len(seen), 8)
        self.assertEqual(seen[0][1], ("simple", "tsumogiri"))
        self.assertEqual(seen[1][1], ("tsumogiri", "simple"))
        t = {r["name"]: r for r in a["table"]}
        self.assertEqual(a["table"][0]["name"], "simple")    # 和了を狙う打ち手が、何もしない打ち手より上
        self.assertLess(t["simple"]["avg_rank"], t["tsumogiri"]["avg_rank"])
        self.assertGreater(t["simple"]["rating"], 1500)
        self.assertAlmostEqual(sum(r["avg_settled"] * r["games"] for r in a["table"]), 0, places=3)
        self.assertEqual(sum(sum(r["ranks"]) for r in a["table"]), 16)
        self.assertEqual(t["tsumogiri"]["win_rate"], 0)
        self.assertIn("simple", AR.format_table(a))

    def test_AR2_more_entrants_than_seats_and_too_few(self):
        ent = dict(self.ent, simple2=self.ent["simple"])
        r = AR.run(self.rs, self.ts, ent, games=3, seed="t3")
        self.assertEqual(sorted(x["games"] for x in r["table"]), [4, 4, 4])      # 3 人から 2 人ずつ、3 通りを 1 回ずつ（席替えで 2 対局）
        with self.assertRaises(ValueError):
            AR.run(self.rs, self.ts, {"only": self.ent["simple"]}, games=1)

    def test_AR3_program_entrant_and_broken_entrant(self):
        root = os.path.dirname(HERE)
        old = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = root + (os.pathsep + old if old else "")
        try:
            ent = {"prog": lambda: GW.ProcessPlayer([sys.executable, "-m", "nmahjong.bots", "simple"]),
                   "broken": lambda: GW.FunctionPlayer(lambda m: {"type": "pon"}, wants_events=False)}
            r = AR.run(self.rs, self.ts, ent, games=1, seed="p")
        finally:
            if old is None:
                del os.environ["PYTHONPATH"]
            else:
                os.environ["PYTHONPATH"] = old
        t = {x["name"]: x for x in r["table"]}
        self.assertEqual(t["prog"]["faults"], 0)
        self.assertGreater(t["broken"]["faults"], 0)         # 壊れた応答は既定の行動に置き換わり、回数が残る
        self.assertEqual(r["table"][0]["name"], "prog")


if __name__ == "__main__":
    unittest.main()
