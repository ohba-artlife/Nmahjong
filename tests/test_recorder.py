"""記録係（nmahjong/recorder.py、試験 T9-5）：出来事を 1 つずつ積んで対局を作る。"""
import copy
import unittest

from nmahjong import recorder as RC, ruleset as R, tileset as TS, wall as W
from nmahjong.canon import ValidationError

from corpus import nm_games, sp_games


class TestRecorder(unittest.TestCase):
    def test_R1_replay_nm_engine_games_gives_same_id(self):
        n = 0
        for n_tiles in (4, 1):
            for rec, walls, rs, ts in nm_games(n_tiles):
                r = RC.replay_record(rec, rs, ts, {w["id"]: w for w in walls})
                self.assertEqual(r.rec["id"], rec["id"])
                self.assertEqual(r.warnings, [])
                n += 1
        self.assertGreaterEqual(n, 20)

    def test_R2_replay_13_tile_games_gives_same_id(self):
        for rec, walls, rs, ts in sp_games():
            r = RC.replay_record(rec, rs, ts, {w["id"]: w for w in walls})
            self.assertEqual(r.rec["id"], rec["id"], rs["name"])
            self.assertEqual(r.warnings, [])                   # 四麻の対局には槍槓が 1 回ある。それも合法手と照合して通る

    def test_R2b_robbed_kan_is_checked(self):
        """槍槓（加槓の牌へのロン）も合法手と照合する。和了形でない席のロン・カンの牌でない牌でのロンを断る。"""
        rec, walls, rs, ts = sp_games("tenhou-4p-hanchan-red")[0]
        wm = {w["id"]: w for w in walls}
        k, rnd = next((k, r) for k, r in enumerate(rec["rounds"])
                      if any(y["name"] == "chankan" for w in (r["result"].get("wins") or []) for y in w["yaku"]))
        win = rnd["events"][-1]
        self.assertEqual((rnd["events"][-2]["t"], rnd["events"][-2]["kind"], win["t"]), ("kan", "kakan", "win"))

        def feed(change):
            r = RC.Recorder(rs, ts, players=copy.deepcopy(rec["players"]), source=copy.deepcopy(rec["source"]))
            for i, src in enumerate(rec["rounds"][:k + 1]):
                evs = src["events"]
                cur = r.start_round(src["state"], wm[src["wall"]["id"]], dora=next((e["tile"] for e in evs[:3] if e["t"] == "dora"), None))
                for e in evs[len(cur["events"]):]:
                    r.push(change(e) if (i == k and e is evs[-1]) else e)
                if i < k:
                    r.end_round(src["result"])
            return r

        self.assertEqual(feed(lambda e: e).warnings, [])
        other = next(s for s in range(4) if s not in (win["who"], win["from"]))
        with self.assertRaisesRegex(ValidationError, "槍槓"):
            feed(lambda e: dict(e, who=other))                                  # 和了形でない席
        with self.assertRaisesRegex(ValidationError, "直前のカン・抜き"):
            feed(lambda e: dict(e, tile=next(t for t in range(136) if t not in rnd["events"][-2]["tiles"])))
        with self.assertRaisesRegex(ValidationError, "直前のカン・抜き"):
            feed(lambda e: dict(e, **{"from": other}))

    def _start(self, name="nm-2p-4-m", seed="recorder-test"):
        rs = R.find(name=name)
        ts = TS.find(id=rs["tileset"]["id"])
        wall = W.build(ts, seed)
        r = RC.Recorder(rs, ts)
        start = R.normalize(rs)["settlement"]["start_points"]
        r.start_round({"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [start, start]}, wall)
        return r, rs, ts, wall

    def test_R3_illegal_events_are_rejected_and_not_stored(self):
        r, rs, ts, wall = self._start()
        order = wall["order"]
        N = 4
        n0 = len(r.rec["rounds"][0]["events"])
        first = order[2 * N]
        cases = [
            ({"t": "draw", "who": 0, "tile": order[2 * N + 1]}, "牌山"),          # 山の次の牌ではない
            ({"t": "discard", "who": 0, "tile": order[0], "tsumogiri": False}, "番ではない"),   # ツモの前に打牌
        ]
        for ev, part in cases:
            with self.assertRaises(ValidationError) as cm:
                r.push(ev)
            self.assertIn(part, str(cm.exception))
            self.assertEqual(len(r.rec["rounds"][0]["events"]), n0)
        r.push({"t": "draw", "who": 0, "tile": first})
        for ev, part in (
            ({"t": "discard", "who": 1, "tile": order[N], "tsumogiri": False}, "番ではない"),      # 相手の番
            ({"t": "discard", "who": 0, "tile": order[N], "tsumogiri": False}, "合法手"),          # 持っていない牌
            ({"t": "draw", "who": 1, "tile": order[2 * N + 1]}, "ツモが 2 回"),
        ):
            with self.assertRaises(ValidationError) as cm:
                r.push(ev)
            self.assertIn(part, str(cm.exception))
            self.assertEqual(len(r.rec["rounds"][0]["events"]), n0 + 1)
        r.push({"t": "discard", "who": 0, "tile": first, "tsumogiri": True})
        with self.assertRaises(ValidationError) as cm:                                           # ポンなしのルール
            r.push({"t": "pon", "who": 1, "tiles": sorted([first, order[N], order[N + 1]]), "from": 0})
        self.assertIn("合法手", str(cm.exception))
        with self.assertRaises(ValidationError):
            r.end_round({"wins": [], "draw": None, "scores": [25000, 25000]})                   # 局を閉じる出来事が無い

    def test_R4_build_rounds_live_for_each_hand_size(self):
        # 山から 1 手ずつ：全員ツモ切りで流局まで。7・10・13 枚でも同じ手順で対局になる
        for name in ("nm-2p-1-m", "nm-2p-4-mps", "nm-2p-7-mps", "nm-2p-10-mpsz", "nm-2p-13-mpsz"):
            r, rs, ts, wall = self._start(name, "live-" + name)
            norm = R.normalize(rs)
            M, N = norm["players"], norm["hand_size"]
            order = wall["order"]
            live_end = len(order) - norm["wall_rules"]["dead_wall"]
            turn = 0
            for pos in range(N * M, live_end):
                r.push({"t": "draw", "who": turn, "tile": order[pos]})
                r.push({"t": "discard", "who": turn, "tile": order[pos], "tsumogiri": True})
                turn = (turn + 1) % M
            with self.assertRaises(ValidationError):
                r.push({"t": "draw", "who": turn, "tile": order[live_end]})                       # 王牌はツモれない
            r.push({"t": "draw_end", "reason": "exhaustive"})
            with self.assertRaises(ValidationError):
                r.push({"t": "draw", "who": turn, "tile": order[0]})                              # 局が終わっている
            start = norm["settlement"]["start_points"]
            hands = [sorted(order[s * N:(s + 1) * N]) for s in range(M)]
            r.end_round({"wins": [], "draw": {"reason": "exhaustive", "tenpai": [False] * M, "hands": hands, "deltas": [0] * M},
                         "scores": [start] * M})
            rec = r.finish()
            self.assertTrue(rec["id"].startswith("sha256:"))
            self.assertEqual(rec["final"]["scores"], [start] * M)

    def test_R6_riichi_with_any_copy_of_the_same_kind(self):
        # 同じ牌種を 3 枚持っていて、どの 1 枚で立直しても積める（legal_actions の立直の候補は牌種ごとに 1 枚だけ）
        rs = R.find(name="tenhou-4p-hanchan-red")
        ts = TS.find(id=rs["tileset"]["id"])

        def kid(k, i):
            return [t["id"] for t in ts["tiles"] if t["kind"] == k and "mark" not in t][i]
        nine = [kid("9m", 0), kid("9m", 1), kid("9m", 2)]
        hand = [kid(k, 0) for k in ("1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "2p", "3p")] + nine[:2]
        rest = [t["id"] for t in ts["tiles"] if t["id"] not in hand and t["id"] != nine[2]]
        order = hand + rest[:39] + [nine[2]] + rest[39:]            # 親の配牌 13・他家 39・親の第 1 ツモ
        wall = W.build_observed(ts, order)
        state = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [25000] * 4}
        for tile in nine:                                           # 手出し 2 通りとツモ切り
            r = RC.Recorder(rs, ts)
            r.start_round(state, wall)
            r.push({"t": "draw", "who": 0, "tile": nine[2]})
            r.push({"t": "riichi", "who": 0})
            r.push({"t": "discard", "who": 0, "tile": tile, "tsumogiri": tile == nine[2], "riichi": True})
            self.assertEqual(r.rec["rounds"][0]["events"][-1]["tile"], tile)
        r = RC.Recorder(rs, ts)
        r.start_round(state, wall)
        r.push({"t": "draw", "who": 0, "tile": nine[2]})
        r.push({"t": "riichi", "who": 0})
        with self.assertRaises(ValidationError):                    # 聴牌にならない牌では立直できない
            r.push({"t": "discard", "who": 0, "tile": kid("1m", 0), "tsumogiri": False, "riichi": True})

    def test_R5_second_kan_by_same_player_is_rejected(self):
        # 4 枚麻雀：カンは各自 1 回。1 局 2 回カンのある対局で、2 回目を同じ人のものに書き換えると積めない
        for rec, walls, rs, ts in nm_games(4):
            for rnd in rec["rounds"]:
                ks = [i for i, e in enumerate(rnd["events"]) if e["t"] == "kan"]
                if len(ks) >= 2:
                    bad = copy.deepcopy(rec)
                    b = next(x for x in bad["rounds"] if x["index"] == rnd["index"])
                    b["events"][ks[1]]["who"] = b["events"][ks[0]]["who"]
                    with self.assertRaises(ValidationError):
                        RC.replay_record(bad, rs, ts, {w["id"]: w for w in walls})
                    return
        self.fail("1 局 2 回カンの対局が試験データに無い")


if __name__ == "__main__":
    unittest.main()
