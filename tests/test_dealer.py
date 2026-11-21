"""進行役（nmahjong/dealer.py、試験 T12-1〜T12-5）：山を配り、局を進め、結果・次の局・終了・精算を決める。"""
import os
import sys
import unittest

from nmahjong import bots as B, dealer as D, gateway as GW, observe as O, record as REC, recorder as RC, ruleset as R, tileset as TS, wall as W
from nmahjong.canon import ValidationError

from corpus import nm_games, rob_ankan_game, sp_games

HERE = os.path.dirname(__file__)


def selfplay(name, seed, bot="simple", **kw):
    rs = R.find(name=name)
    ts = TS.find(id=rs["tileset"]["id"])
    M = R.normalize(rs)["players"]
    d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.BOTS[bot], wants_events=False) for s in range(M)}, **kw)
    rec = d.play(lambda k, st: W.build(ts, f"{seed}-{k}"))
    return d, rec, rs, ts


class TestDealerAgainstRecords(unittest.TestCase):
    def test_D1_nm_engine_games_same_progress_and_result(self):
        n = 0
        for n_tiles in (4, 1):
            for rec, walls, rs, ts in nm_games(n_tiles):
                if rec.get("parent"):
                    continue                                   # 代打ちの対局は途中から始まるので対象外
                d = D.replay_with_dealer(rec, rs, ts, {w["id"]: w for w in walls})
                self.assertIsNone(D.differences(d.rc.rec, rec), rec["source"]["ref"])
                n += 1
        self.assertGreaterEqual(n, 18)

    def test_D2_13_tile_games_same_progress_and_result(self):
        games = sp_games()
        self.assertEqual(len(games), 2)                        # 四麻と三麻
        for rec, walls, rs, ts in games:
            d = D.replay_with_dealer(rec, rs, ts, {w["id"]: w for w in walls})
            self.assertIsNone(D.differences(d.rc.rec, rec), rs["name"])
            self.assertEqual(d.rc.rec["id"], rec["id"], rs["name"])

    def test_D3_same_through_gateway_with_legal_check(self):
        """判断を接続口ごしに求める（打てる手の一覧を作り、応答がその中にあることを確かめる）形でも同じ対局になる。"""
        for rec, walls, rs, ts in sp_games():
            d = D.replay_with_dealer(rec, rs, ts, {w["id"]: w for w in walls}, through_gateway=True)
            self.assertIsNone(D.differences(d.rc.rec, rec), rs["name"])
            self.assertGreater(d.gw.requests, 200)
        rec, walls, rs, ts = nm_games(4)[0]
        d = D.replay_with_dealer(rec, rs, ts, {w["id"]: w for w in walls}, through_gateway=True)
        self.assertIsNone(D.differences(d.rc.rec, rec))


class TestDealerRobbedKan(unittest.TestCase):
    """槍槓のうち、暗槓の牌へのロン。ルールが認めていて（flow.kokushi_ankan_chankan）、国士無双のときだけできる。"""

    def first_round(self, name, kokushi):
        rec, walls, rs, ts = rob_ankan_game(name, kokushi)
        wm = {w["id"]: w for w in walls}
        self.assertEqual(REC.validate(rec, rs, ts, wm), [], name)
        rnd = rec["rounds"][0]
        self.assertEqual([e["t"] for e in rnd["events"][:4]], ["deal", "dora", "draw", "kan"])
        self.assertEqual(rnd["events"][3]["kind"], "ankan")
        return rec, wm, rs, ts, rnd

    def test_D6_kokushi_may_rob_a_closed_kan_when_the_rule_allows(self):
        rec, wm, rs, ts, rnd = self.first_round("jantama-4p", True)
        self.assertTrue(R.normalize(rs)["game_rules"]["flow"]["kokushi_ankan_chankan"])
        self.assertEqual(rnd["events"][4]["t"], "win")
        (w,) = rnd["result"]["wins"]
        self.assertEqual((w["who"], w["from"], [y["name"] for y in w["yaku"]], w["points"]), (1, 0, ["kokushi"], 32000))
        # 記録係に積み直しても、接続口ごしに進め直しても通る（槍槓も合法手と照合する）
        r = RC.replay_record(rec, rs, ts, wm)
        self.assertEqual((r.rec["id"], r.warnings), (rec["id"], []))
        d = D.replay_with_dealer(rec, rs, ts, wm, through_gateway=True)
        self.assertIsNone(D.differences(d.rc.rec, rec))

    def test_D7_closed_kan_is_not_robbed_otherwise(self):
        # 認めないルール（天鳳）：国士無双でも暗槓の牌はロンできず、局が続く
        rec, wm, rs, ts, rnd = self.first_round("tenhou-4p-hanchan-red", True)
        self.assertFalse(R.normalize(rs)["game_rules"]["flow"]["kokushi_ankan_chankan"])
        self.assertNotEqual(rnd["events"][4]["t"], "win")
        # 認めるルールでも、国士無双でない形は暗槓の牌をロンできない
        rec, wm, rs, ts, rnd = self.first_round("jantama-4p", False)
        self.assertNotEqual(rnd["events"][4]["t"], "win")
        # 記録を書き換えて暗槓の牌でロンしたことにすると、記録係が断る
        rec, walls, rs, ts = rob_ankan_game("tenhou-4p-hanchan-red", True)
        rnd = rec["rounds"][0]
        r = RC.Recorder(rs, ts)
        cur = r.start_round(rnd["state"], next(w for w in walls if w["id"] == rnd["wall"]["id"]), dora=rnd["events"][1]["tile"])
        for e in rnd["events"][len(cur["events"]):4]:
            r.push(e)
        with self.assertRaisesRegex(ValidationError, "槍槓"):
            r.push({"t": "win", "who": 1, "from": 0, "tile": rnd["events"][3]["tiles"][0]})


class TestDealerSelfPlay(unittest.TestCase):
    def test_D4_bots_finish_a_valid_game_in_every_hand_size(self):
        for name in ("nm-2p-1-mps", "nm-2p-4-mps", "nm-2p-7-mps", "nm-2p-10-mpsz", "nm-2p-13-mpsz", "tenhou-4p-tonpu-red", "tenhou-3p"):
            for bot in (("tsumogiri", "simple") if name.startswith("nm-") else ("simple",)):
                d, rec, rs, ts = selfplay(name, f"t-{name}-{bot}", bot)
                self.assertEqual(REC.validate(rec, rs, ts, d.walls), [], name)
                self.assertEqual(rec["end"], "finished")
                self.assertEqual(sum(rec["final"]["scores"]), R.normalize(rs)["settlement"]["start_points"] * R.normalize(rs)["players"], name)
                self.assertAlmostEqual(sum(rec["final"]["settled"]), 0, places=6)
                self.assertTrue(d.log[-1].startswith("終了"))

    def test_D5_same_seed_same_game(self):
        a = selfplay("nm-2p-4-mps", "same")[1]
        b = selfplay("nm-2p-4-mps", "same")[1]
        c = selfplay("nm-2p-4-mps", "other")[1]
        self.assertEqual(a["id"], b["id"])
        self.assertNotEqual(a["id"], c["id"])

    def test_D6_other_programs_as_players(self):
        rs = R.find(name="nm-2p-4-mps")
        ts = TS.find(id=rs["tileset"]["id"])
        cmd = [sys.executable, "-m", "nmahjong.bots", "simple"]
        env_root = os.path.dirname(HERE)
        old = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = env_root + (os.pathsep + old if old else "")
        try:
            players = {0: GW.ProcessPlayer(cmd), 1: GW.ProcessPlayer(cmd)}
            d = D.Dealer(rs, ts, players=players)
            try:
                rec = d.play(lambda k, st: W.build(ts, f"proc-{k}"))
            finally:
                d.gw.close()
        finally:
            if old is None:
                del os.environ["PYTHONPATH"]
            else:
                os.environ["PYTHONPATH"] = old
        self.assertEqual(REC.validate(rec, rs, ts, d.walls), [])
        self.assertEqual(d.gw.faults, [])
        same = selfplay("nm-2p-4-mps", "proc")[1]              # 関数の打ち手でも、別プログラムの打ち手でも同じ対局
        self.assertIsNone(D.differences(rec, same))

    def test_D7_broken_player_does_not_stop_the_game(self):
        rs = R.find(name="nm-2p-4-mps")
        ts = TS.find(id=rs["tileset"]["id"])
        players = {0: GW.FunctionPlayer(lambda m: {"type": "dahai", "pai": "9z"}, wants_events=False), 1: GW.FunctionPlayer(B.simple, wants_events=False)}
        with self.assertRaises(ValidationError):
            D.Dealer(rs, ts, players=players).play(lambda k, st: W.build(ts, f"bad-{k}"))
        d = D.Dealer(rs, ts, players=players, strict=False)
        rec = d.play(lambda k, st: W.build(ts, f"bad-{k}"))
        self.assertEqual(REC.validate(rec, rs, ts, d.walls), [])
        self.assertTrue(d.gw.faults)


class TestDealerRules(unittest.TestCase):
    def setUp(self):
        self.rs = R.find(name="tenhou-4p-hanchan-red")
        self.ts = TS.find(id=self.rs["tileset"]["id"])
        self.d = D.Dealer(self.rs, self.ts, decide=lambda *a: None)
        self.d._sticks = []

    def st(self, bakaze="E", kyoku=1, honba=0, kyotaku=0, oya=0, scores=(25000, 25000, 25000, 25000)):
        return {"bakaze": bakaze, "kyoku": kyoku, "honba": honba, "kyotaku": kyotaku, "oya": oya, "scores": list(scores)}

    def nx(self, state, scores, **info):
        return self.d.next_state(state, {"scores": list(scores)}, info, 0)

    def test_D8_next_round(self):
        s = self.st(honba=1, kyotaku=1)
        n, _ = self.nx(s, (33000, 22000, 22000, 23000), kind="win", dealer_won=True, winners=[0])
        self.assertEqual((n["kyoku"], n["oya"], n["honba"], n["kyotaku"]), (1, 0, 2, 0))        # 親の和了：連荘、本場＋1、供託は和了者へ
        n, _ = self.nx(s, (22000, 33000, 22000, 23000), kind="win", dealer_won=False, winners=[1])
        self.assertEqual((n["kyoku"], n["oya"], n["honba"], n["kyotaku"]), (2, 1, 0, 0))        # 子の和了：親が流れ、本場 0
        self.d._sticks = [2]
        n, _ = self.nx(s, (26500, 23500, 23500, 26500), kind="draw", reason="exhaustive", dealer_tenpai=True, any_tenpai=True)
        self.assertEqual((n["kyoku"], n["oya"], n["honba"], n["kyotaku"]), (1, 0, 2, 2))        # 親聴牌の流局：連荘、供託は持ち越し＋この局の立直棒
        n, _ = self.nx(s, (23500, 26500, 23500, 26500), kind="draw", reason="exhaustive", dealer_tenpai=False, any_tenpai=True)
        self.assertEqual((n["kyoku"], n["oya"], n["honba"], n["kyotaku"]), (2, 1, 2, 2))        # 親ノーテン：親が流れ、本場＋1
        self.d._sticks = []
        n, _ = self.nx(self.st(kyoku=4, oya=3), (25000, 25000, 25000, 25000), kind="draw", reason="exhaustive", dealer_tenpai=False, any_tenpai=False)
        self.assertEqual((n["bakaze"], n["kyoku"], n["oya"]), ("S", 1, 0))
        n, _ = self.nx(s, (25000, 25000, 25000, 25000), kind="abort", reason="four_winds")
        self.assertEqual((n["kyoku"], n["oya"], n["honba"]), (1, 0, 2))                          # 途中流局：連荘（天鳳）

    def test_D9_end_of_game(self):
        last = self.st(bakaze="S", kyoku=4, oya=3)
        self.assertEqual(self.nx(last, (40000, 20000, 20000, 20000), kind="win", dealer_won=False, winners=[0])[1], "規定の局数")
        n, why = self.nx(last, (28000, 26000, 24000, 22000), kind="win", dealer_won=False, winners=[0])
        self.assertEqual((n["bakaze"], n["kyoku"], why), ("W", 1, None))                          # 誰も 30000 に届かない：西入
        self.assertEqual(self.nx(last, (20000, 20000, 20000, 40000), kind="win", dealer_won=True, winners=[3])[1], "和了止め")
        n, why = self.nx(last, (40000, 20000, 20000, 20000), kind="win", dealer_won=True, winners=[3])
        self.assertEqual((n["kyoku"], n["honba"], why), (4, 1, None))                             # 親が和了ったがトップでない：続く
        self.assertEqual(self.nx(last, (20000, 20000, 20000, 40000), kind="draw", reason="exhaustive", dealer_tenpai=True, any_tenpai=True)[1], "聴牌止め")
        self.assertEqual(self.nx(self.st(), (-100, 30100, 35000, 35000), kind="win", dealer_won=False, winners=[1])[1], "飛び")
        n, why = self.nx(self.st(), (0, 30000, 35000, 35000), kind="win", dealer_won=False, winners=[1])
        self.assertIsNone(why)                                                                    # ちょうど 0 点は飛びではない（天鳳）
        west = self.st(bakaze="W", kyoku=1)
        self.assertEqual(self.nx(west, (31000, 23000, 23000, 23000), kind="win", dealer_won=True, winners=[0])[1], "和了止め")   # 親が連荘してトップ
        self.assertEqual(self.nx(west, (23000, 31000, 23000, 23000), kind="win", dealer_won=False, winners=[1])[1], "延長：規定の点に届いた")
        n, why = self.nx(west, (23000, 31000, 23000, 23000), kind="win", dealer_won=True, winners=[0])
        self.assertEqual((n["bakaze"], n["kyoku"], n["honba"], why), ("W", 1, 1, None))            # 親が連荘、トップでない：連荘を優先（天鳳）
        d = D.Dealer(R.find(name="zoo-4p"), TS.find(id=R.find(name="zoo-4p")["tileset"]["id"]), decide=lambda *a: None)
        d._sticks = []
        self.assertEqual(d.next_state(self.st(), {"scores": [55000, 15000, 15000, 15000]}, {"kind": "win", "dealer_won": True, "winners": [0]}, 0)[1], "コールド")

    def test_D10_unsupported_settings_are_refused(self):
        """従えない設定があるルールは、指定しないかぎり始めない。同梱ルールには、もう無い。"""
        self.assertEqual([r["name"] for r in R.bundled() if D.unsupported(r)], [])
        rs = R.new_from(R.find(name="tenhou-3p"), "t", {"game_rules.flow.wareme": True})          # 三人打ちのわれめ：開門の家の決め方が無い
        ts = TS.find(id=rs["tileset"]["id"])
        self.assertTrue(any("wareme" in u for u in D.unsupported(rs)))
        with self.assertRaises(ValidationError):
            D.Dealer(rs, ts, decide=lambda *a: None)
        D.Dealer(rs, ts, decide=lambda *a: None, allow_unsupported=True)

    def test_D11_pao_payment(self):
        """包の支払いの 3 つの設定。山を組んだ局での確認は tests/test_tenhou_rules.py。"""
        d = self.d                                               # 天鳳：ロンは複合役満を含む全部を折半（split_all）、本場は責任者（liable）
        d.M = 4
        self.assertEqual((d.g["pao"]["ron"], d.g["pao"]["honba_kyotaku"]), ("split_all", "liable"))
        # 役満 32000（子）。席 0 が和了、席 2 が責任者。ツモ：責任者が全部。ロン（席 1 から）：半分ずつ、本場は責任者
        self.assertEqual(d._pao_deltas(None, None, 1, 0, 0, 2, 1.0, 32000, 1, True), [32300, 0, -32300, 0])
        self.assertEqual(d._pao_deltas(None, None, 1, 0, 1, 2, 1.0, 32000, 1, False), [32300, -16000, -16300, 0])
        self.assertEqual(d._pao_deltas(None, None, 1, 0, 1, 2, 0.5, 64000, 0, False), [64000, -32000, -32000, 0])   # 複合：全部を折半
        # M リーグ：ロンは包にあたる役満の分だけを折半（split）、本場は放銃者（discarder）
        m = R.find(name="mleague")
        dm = D.Dealer(m, TS.find(id=m["tileset"]["id"]), decide=lambda *a: None)
        dm._sticks = []
        self.assertEqual((dm.g["pao"]["ron"], dm.g["pao"]["honba_kyotaku"]), ("split", "discarder"))
        self.assertEqual(dm._pao_deltas(None, None, 1, 0, 1, 2, 1.0, 32000, 1, False), [32300, -16300, -16000, 0])
        self.assertEqual(dm._pao_deltas(None, None, 1, 0, 1, 2, 0.5, 64000, 0, False), [64000, -48000, -16000, 0])  # 複合：包は半分の役満だけ
        # full：包にあたる分を責任者が全部
        dm.g["pao"]["ron"] = "full"
        self.assertEqual(dm._pao_deltas(None, None, 1, 0, 1, 2, 1.0, 32000, 0, False), [32000, 0, -32000, 0])

    def test_D12_furiten_same_turn_and_after_riichi(self):
        ts = self.ts
        k = lambda name: next(t["id"] for t in ts["tiles"] if t["kind"] == name)   # noqa: E731
        obs = {"seat": 0, "discards": [[k("9m")], [], [], []], "passed": [], "passed_riichi": []}
        self.assertFalse(O._furiten(ts, obs, {"1p", "4p"}))
        self.assertTrue(O._furiten(ts, dict(obs, passed=[k("4p")]), {"1p", "4p"}))                 # 同巡に見逃した
        self.assertTrue(O._furiten(ts, dict(obs, passed_riichi=[k("1p")]), {"1p", "4p"}))          # 立直後に見逃した
        self.assertTrue(O._furiten(ts, obs, {"9m", "6m"}))                                         # 自分の河にある


if __name__ == "__main__":
    unittest.main()
