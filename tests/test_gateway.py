"""打ち手の接続口（nmahjong/gateway.py、overview.md §0 のＡ、試験 T9-7）：状況を送り、行動を受け取って記録係に積む。"""
import copy
import os
import sys
import unittest

from nmahjong import gateway as GW, recorder as RC
from nmahjong.canon import ValidationError

from corpus import nm_games, sp_games

HERE = os.path.dirname(__file__)
BOT = os.path.join(HERE, "data", "gateway_bot.py")


def table(rec, walls, rs, ts, players):
    """対局の最初の局を、親の最初のツモまで積んだ卓。"""
    rnd = rec["rounds"][0]
    wm = {w["id"]: w for w in walls}
    r = RC.Recorder(rs, ts, players=copy.deepcopy(rec["players"]), source=copy.deepcopy(rec["source"]))
    dora = next((e["tile"] for e in rnd["events"][:3] if e["t"] == "dora"), None)
    cur = r.start_round(rnd["state"], wm[rnd["wall"]["id"]], dora=dora)
    i = len(cur["events"])
    while rnd["events"][i - 1]["t"] != "draw":
        r.push(rnd["events"][i])
        i += 1
    return r, GW.Gateway(r, players, strict=True), rnd["events"][i - 1]


class TestGateway(unittest.TestCase):
    def test_G1_nm_engine_games_through_gateway_give_same_id(self):
        n = req = 0
        for n_tiles in (4, 1):
            for rec, walls, rs, ts in nm_games(n_tiles):
                r, gw = GW.replay_through_gateway(rec, rs, ts, {w["id"]: w for w in walls})
                self.assertEqual(r.rec["id"], rec["id"])
                self.assertEqual(r.warnings, [])
                self.assertEqual(gw.faults, [])
                n += 1
                req += gw.requests
        self.assertGreaterEqual(n, 20)
        self.assertGreater(req, 100)

    def test_G2_13_tile_games_through_gateway_give_same_id(self):
        for rec, walls, rs, ts in sp_games():
            r, gw = GW.replay_through_gateway(rec, rs, ts, {w["id"]: w for w in walls})
            self.assertEqual(r.rec["id"], rec["id"], rs["name"])
            self.assertEqual(r.warnings, [])                   # 四麻の対局には槍槓が 1 回ある。それも合法手と照合して通る
            self.assertEqual(gw.faults, [])
            self.assertGreater(gw.requests, 300)

    def test_G3_situation_hides_other_seats(self):
        rec, walls, rs, ts = nm_games(4)[0]
        got = {}

        def fn(msg):
            got.setdefault("msg", msg)
            raise KeyboardInterrupt

        try:
            GW.replay_through_gateway(rec, rs, ts, {w["id"]: w for w in walls}, players={s: GW.FunctionPlayer(fn) for s in range(2)})
        except KeyboardInterrupt:
            pass
        m = got["msg"]
        seat = m["request"]["actor"]
        types = [e["type"] for e in m["events"]]
        self.assertEqual(types[:2], ["start_game", "start_kyoku"])
        sk = m["events"][1]
        for s, hand in enumerate(sk["tehais"]):
            if s == seat:
                self.assertNotIn("?", hand)
            else:
                self.assertEqual(set(hand), {"?"})
                self.assertIsNone(sk["tiles"][s])
        self.assertEqual(m["request"]["type"], "request_action")
        self.assertTrue(m["request"]["possible_actions"])
        self.assertEqual(set(m["context"]), {"round", "at", "phase"})

    def test_G4_bad_response_strict_raises_loose_falls_back(self):
        rec, walls, rs, ts = nm_games(4)[0]
        for bad in ({"type": "dahai", "pai": "9z"}, {"type": "pon", "consumed": ["1m", "1m"]}, "x", {"type": "reach"}, {}):
            pl = {s: GW.FunctionPlayer(lambda msg, bad=bad: bad, wants_events=False) for s in range(2)}
            r, gw, draw = table(rec, walls, rs, ts, pl)
            with self.assertRaises(ValidationError):
                gw.ask(draw["who"], "B")
            gw.strict = False
            a = gw.ask(draw["who"], "B")
            self.assertEqual(a, {"type": "discard", "tile": draw["tile"]})      # 既定の行動＝ツモ切り
            self.assertEqual(len(gw.faults), 1)
            evs = gw.apply(draw["who"], a)
            self.assertEqual(evs, [{"t": "discard", "who": draw["who"], "tile": draw["tile"], "tsumogiri": True}])
            self.assertEqual(r.rec["rounds"][-1]["events"][-1], evs[0])

    def test_G5_response_may_omit_actor_and_accepts_kind_only(self):
        rec, walls, rs, ts = nm_games(4)[0]
        seen = {}

        def fn(msg):
            a = next(x for x in msg["request"]["possible_actions"] if x["type"] == "dahai")
            seen["pai"] = a["pai"]
            return {"type": "dahai", "pai": a["pai"]}                            # tile（牌の番号）も actor も付けない

        r, gw, draw = table(rec, walls, rs, ts, {s: GW.FunctionPlayer(fn) for s in range(2)})
        a = gw.ask(draw["who"], "B")
        self.assertEqual(ts["tiles"][a["tile"]]["kind"], seen["pai"])
        gw.apply(draw["who"], a)
        self.assertEqual(r.rec["rounds"][-1]["events"][-1]["t"], "discard")

    def test_G6_other_program_as_player(self):
        rec, walls, rs, ts = nm_games(4)[0]
        pl = {s: GW.ProcessPlayer([sys.executable, BOT]) for s in range(2)}
        r, gw, draw = table(rec, walls, rs, ts, pl)
        try:
            a = gw.ask(draw["who"], "B")
            self.assertEqual(a, {"type": "discard", "tile": draw["tile"]})      # 相手は出来事の列から自分のツモを知り、ツモ切りを返す
            gw.apply(draw["who"], a)
            other = 1 - draw["who"]
            obs, legal, at = gw.legal(other, "C")
            if any(x["type"] != "pass" for x in legal):
                self.assertIn(gw.ask(other, "C")["type"], ("pass", "ron"))
            gw.flush()
        finally:
            gw.close()
        for p in pl.values():
            self.assertEqual(p.proc.returncode, 0)

    def test_G7_program_that_dies_is_reported(self):
        rec, walls, rs, ts = nm_games(4)[0]
        pl = {s: GW.ProcessPlayer([sys.executable, "-c", "pass"]) for s in range(2)}
        for p in pl.values():
            p.proc.wait()                                                        # 先に終わらせておく（送る時点でもう居ない）
        r, gw, draw = table(rec, walls, rs, ts, pl)
        try:
            gw.strict = False
            a = gw.ask(draw["who"], "B")
            self.assertEqual(a, {"type": "discard", "tile": draw["tile"]})
            self.assertEqual(len(gw.faults), 1)
            gw.flush()
            self.assertEqual(len(gw.faults), 2)                                  # もう片方の席にも送れない
        finally:
            gw.close()


if __name__ == "__main__":
    unittest.main()
