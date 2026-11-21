"""試験用の対局の集まり（tests/data/corpus/nm-engine.jsonl、tests/corpus.py）。

このライブラリとは別に作られた対局エンジンが打った N 枚麻雀（1 枚・4 枚）の対局 50 を、Nmahjong の形式で置いたもの。
ここでは集まりそのもの（検証を通る、変種のルールが入っている、特別な局面が入っている）を確かめる。
判定・進行役・記録係・接続口・評価との突き合わせは、それぞれの試験（test_judge・test_dealer・test_recorder・test_gateway・test_layer5）が行う。
"""
import copy
import unittest

from nmahjong import dealer as D, nmrules as NR, observe as O, record as REC, ruleset as R, wall as W
from nmahjong.canon import ValidationError
from corpus import nm_games


class TestCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = nm_games()

    def test_C1_all_games_validate(self):
        # 50 対局とも、ルール・牌山・対局が形式どおりで、層またぎの検証（山との突合、点数、精算）を注意なしで通る
        self.assertEqual(len(self.games), 50)
        ids = set()
        for rec, walls, rs, ts in self.games:
            R.validate(rs, ts)
            for w in walls:
                W.validate(w, ts)
            self.assertEqual(REC.validate(rec, rs, ts, {w["id"]: w for w in walls}), [], rs["name"])
            self.assertEqual(rec["ruleset"], {"name": rs["name"], "id": rs["id"]})
            self.assertEqual(rec["source"]["kind"], "imported")
            ids.add(rec["id"])
        self.assertEqual(len(ids), 50)
        self.assertEqual(sorted({rs["hand_size"] for _, _, rs, _ in self.games}), [1, 4])

    def test_C2_rules_are_the_bundled_defaults_or_their_named_variants(self):
        # 変種でない対局のルールは nmrules.ruleset_for と同じ id。変種は名前に -stays／-ronstick が付き、該当の項目だけが違う
        plain = stays = ronstick = 0
        for rec, walls, rs, ts in self.games:
            base = NR.ruleset_for(rs["hand_size"], rs["tileset"]["name"], rs["length"])
            name = rs["name"]
            if "-stays" not in name and "-ronstick" not in name:
                self.assertEqual(rs["id"], base["id"], name)
                plain += 1
                continue
            a, b = R.normalize(rs), R.normalize(base)
            ra, rb = a["game_rules"]["flow"]["riichi"], b["game_rules"]["flow"]["riichi"]
            self.assertEqual(ra["stick_at_end"], "stays" if "-stays" in name else "to_first")
            self.assertEqual(ra["stick_if_ronned"], "-ronstick" in name)
            ra2 = dict(ra, stick_at_end=rb["stick_at_end"], stick_if_ronned=rb["stick_if_ronned"])
            self.assertEqual(ra2, rb)
            for key in ("wall_rules", "end", "settlement", "players", "hand_size", "length", "tileset"):
                self.assertEqual(a[key], b[key], (name, key))
            stays += "-stays" in name
            ronstick += "-ronstick" in name
        self.assertGreater(plain, 20)
        self.assertGreater(stays, 0)
        self.assertGreater(ronstick, 5)

    def test_C3_special_situations_are_present(self):
        yaku = set()
        draws = two_kans = takeovers = yakuman2 = 0
        for rec, walls, rs, ts in self.games:
            takeovers += rec.get("parent") is not None
            wm = {w["id"]: w for w in walls}
            for rd in rec["rounds"]:
                draws += not rd["result"]["wins"]
                for w in rd["result"]["wins"]:
                    yaku |= {y["name"] for y in w["yaku"]}
                    yakuman2 += w.get("yakuman", 0) >= 2
                rin = [e for e in rd["events"] if e["t"] == "draw" and e.get("rinshan")]
                if len(rin) == 2:       # 1 局 2 回の暗槓：最初の嶺上は王牌の 4 枚目、2 回目は 1 回目のカンで王牌に入った元の海底牌
                    order = wm[rd["wall"]["id"]]["order"]
                    self.assertEqual(rin[0]["tile"], order[-1])
                    self.assertEqual(rin[1]["tile"], order[-5])
                    two_kans += 1
        for name in ("tenhou", "chiihou", "renhou", "rinshan", "haitei", "riichi", "ippatsu", "chinitsu"):
            self.assertIn(name, yaku)
        self.assertGreater(draws, 0)
        self.assertGreater(two_kans, 0)
        self.assertGreater(yakuman2, 0)
        self.assertGreaterEqual(takeovers, 2)

    def test_C4_takeover_games_continue_from_their_parent(self):
        by_id = {rec["id"]: rec for rec, _, _, _ in self.games}
        n = 0
        for rec, walls, rs, ts in self.games:
            p = rec.get("parent")
            if not p:
                continue
            par = by_id[p["record"]]
            self.assertEqual(rec["rounds"][0]["state"]["scores"], par["rounds"][p["round"]]["state"]["scores"])
            self.assertEqual(rec["rounds"][0]["wall"], par["rounds"][p["round"]]["wall"])
            n += 1
        self.assertGreaterEqual(n, 2)

    def test_C5_every_recorded_action_is_legal_and_calls_follow_the_rules(self):
        # 記録の全判断点で、実際の行動が合法手の中にある。ポン・明槓・加槓は候補に出ず、暗槓は各自 1 回まで
        points = 0
        for rec, walls, rs, ts in self.games:
            wm = {w["id"]: w for w in walls}
            M = R.normalize(rs)["players"]
            for rd in rec["rounds"]:
                evs = rd["events"]
                for at in range(len(evs) - 1):
                    for seat in range(M):
                        ph = O.phase_of(evs, at, seat)
                        if ph is None:
                            continue
                        obs = O.observe(rec, rd["index"], at, seat, rs, ts, wm)
                        phases = [ph]
                        if ph == "A" and O.actual_action(rec, rd["index"], at, seat, "A") == {"type": "pass"}:
                            phases.append("B")
                        for p in phases:
                            acts = O.legal_actions(rs, ts, obs, p)
                            self.assertFalse(any(a["type"] in ("pon", "chi") or (a["type"] == "kan" and a["kind"] != "ankan") for a in acts))
                            if any(m["kind"] == "ankan" for m in obs["melds"][seat]):
                                self.assertFalse(any(a["type"] == "kan" for a in acts))
                            actual = O.actual_action(rec, rd["index"], at, seat, p)
                            if actual is None:
                                continue
                            self.assertIn(O.action_key(actual), {O.action_key(a) for a in acts}, (rs["name"], rd["index"], at, seat, p))
                            points += 1
        self.assertGreater(points, 1000)

    def test_C6_tampered_games_are_rejected(self):
        rec, walls, rs, ts = next(g for g in self.games if not g[0].get("parent") and any(
            sum(1 for e in r["events"] if e["t"] == "kan") >= 2 for r in g[0]["rounds"]))
        wm = {w["id"]: w for w in walls}
        bad = copy.deepcopy(rec)        # 同じ人の 2 回目の暗槓
        rd = next(r for r in bad["rounds"] if sum(1 for e in r["events"] if e["t"] == "kan") >= 2)
        ks = [e for e in rd["events"] if e["t"] == "kan"]
        ks[1]["who"] = ks[0]["who"]
        bad["id"] = REC.compute_id(bad)
        with self.assertRaises(ValidationError) as cm:
            REC.validate(bad, rs, ts, wm)
        self.assertIn("max_kans_per_player", str(cm.exception))
        rec, walls, rs, ts = next(g for g in self.games if any(r["result"]["wins"] for r in g[0]["rounds"]))
        wm = {w["id"]: w for w in walls}
        for change in ("points", "scores", "final"):
            bad = copy.deepcopy(rec)
            rd = next(r for r in bad["rounds"] if r["result"]["wins"])
            if change == "points":
                rd["result"]["wins"][0]["points"] += 100
            elif change == "scores":
                rd["result"]["scores"][0] += 100
            else:
                bad["final"]["scores"][0] += 1000
            bad["id"] = REC.compute_id(bad)
            with self.assertRaises(ValidationError, msg=change):
                REC.validate(bad, rs, ts, wm)

    def test_C7_variant_rules_reproduce_the_recorded_riichi_sticks(self):
        # -ronstick の対局：進行役で進め直すと元と同じ。同じ対局を既定のルール（棒を出さない）で進め直すと、供託が合わなくなる
        n = diff = 0
        for rec, walls, rs, ts in self.games:
            if "-ronstick" not in rs["name"] or rec.get("parent"):
                continue
            wm = {w["id"]: w for w in walls}
            d = D.replay_with_dealer(rec, rs, ts, wm)
            self.assertIsNone(D.differences(d.rc.rec, rec), rs["name"])
            base = NR.ruleset_for(rs["hand_size"], rs["tileset"]["name"], rs["length"])
            try:
                d2 = D.replay_with_dealer(rec, base, ts, wm)
                diff += D.differences(d2.rc.rec, rec) is not None
            except ValidationError:
                diff += 1
            n += 1
        self.assertGreater(n, 5)
        self.assertEqual(diff, n)


if __name__ == "__main__":
    unittest.main()
