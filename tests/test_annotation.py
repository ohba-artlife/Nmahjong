"""試験 T5 評価（annotation.md §3）と、局面・合法手（observe.py）。試験データは 13 枚麻雀の対局（tests/data/corpus/selfplay-13.jsonl、四麻）。"""
import copy
import unittest

from nmahjong import annotation as A, evaluate as E, observe as O, ruleset as R, tileset as TS, mjai as MJ
from nmahjong.canon import ValidationError

from corpus import sp_game


class TestObserve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec, cls.walls, cls.rs, cls.ts = sp_game("tenhou-4p-hanchan-red")
        cls.wmap = {w["id"]: w for w in cls.walls}

    def test_T7_5_actual_actions_are_legal(self):
        """対局の全判断点（A・B・C）で、実際の行動が legal_actions に含まれる。"""
        n = 0
        for rnd in self.rec["rounds"]:
            evs = rnd["events"]
            for at in range(len(evs)):
                for seat in range(4):
                    ph = O.phase_of(evs, at, seat)
                    if ph is None:
                        continue
                    obs = O.observe(self.rec, rnd["index"], at, seat, self.rs, self.ts, self.wmap)
                    phases = [ph]
                    if ph == "A" and O.actual_action(self.rec, rnd["index"], at, seat, "A") == {"type": "pass"}:
                        phases.append("B")
                    for p in phases:
                        act = O.actual_action(self.rec, rnd["index"], at, seat, p)
                        if act is None:
                            continue
                        keys = {O.action_key(a) for a in O.legal_actions(self.rs, self.ts, obs, p)}
                        self.assertIn(O.action_key(act), keys, (rnd["index"], at, seat, p, act))
                        n += 1
        self.assertGreater(n, 2000)

    def test_T7_6_hand_counts(self):
        """再生中の手牌枚数：ツモ直後は 14−3×副露、打牌後は 13−3×副露（抜きは 1 枚減）。"""
        for rnd in self.rec["rounds"]:
            evs = rnd["events"]
            for at, e in enumerate(evs):
                if e["t"] in ("draw", "discard"):
                    obs = O.observe(self.rec, rnd["index"], at, e["who"], self.rs, self.ts, self.wmap)
                    m = len(obs["melds"][e["who"]])
                    self.assertEqual(len(obs["hand"]), (14 if e["t"] == "draw" else 13) - 3 * m)

    def test_T7_7_rule_dependent_actions(self):
        """チー禁止・送りカン none・喰い替え禁止で合法手が変わる。"""
        # 対局の中からチーが実際に起きた場面
        hit = None
        for rnd in self.rec["rounds"]:
            for at, e in enumerate(rnd["events"]):
                if e["t"] == "chi":
                    hit = (rnd["index"], at - 1, e["who"])
                    break
            if hit:
                break
        self.assertIsNotNone(hit)
        r, at, seat = hit
        obs = O.observe(self.rec, r, at, seat, self.rs, self.ts, self.wmap)
        self.assertTrue(any(a["type"] == "chi" for a in O.legal_actions(self.rs, self.ts, obs, "C")))
        rs2 = R.new_from(copy.deepcopy(self.rs), "nochi", {"game_rules.flow.chi": False})
        self.assertFalse(any(a["type"] == "chi" for a in O.legal_actions(rs2, self.ts, obs, "C")))
        # 喰い替え：チー直後の打牌で、鳴いた牌と同種が消える
        obs2 = O.observe(self.rec, r, at + 1, seat, self.rs, self.ts, self.wmap)
        called = obs2["just_called_tile"]
        kinds = {O.kind_of(self.ts, a["tile"]) for a in O.legal_actions(self.rs, self.ts, obs2, "B")}
        self.assertNotIn(O.kind_of(self.ts, called), kinds)
        rs3 = R.new_from(copy.deepcopy(self.rs), "kuikae", {"game_rules.flow.kuikae": "allowed"})
        kinds3 = {O.kind_of(self.ts, a["tile"]) for a in O.legal_actions(rs3, self.ts, obs2, "B")}
        self.assertGreaterEqual(len(kinds3), len(kinds))

    def test_T7_10_no_nuki_or_kan_when_no_tile_is_left(self):
        """海底（ツモれる牌が残っていない）では、抜きもカンもできない。抜くと嶺上から 1 枚補うので、カンと同じ扱い。"""
        rec, walls, rs, ts = sp_game("tenhou-3p")
        wm = {w["id"]: w for w in walls}
        n = 0
        for rnd in rec["rounds"]:
            for i, e in enumerate(rnd["events"]):
                if e["t"] != "draw":
                    continue
                obs = O.observe(rec, rnd["index"], i + 1, e["who"], rs, ts, wm)
                if not any(O.kind_of(ts, t) == "N" for t in obs["hand"]) or obs["riichi"][e["who"]]:
                    continue
                obs["remaining"] = 1
                self.assertIn("nuki", {a["type"] for a in O.legal_actions(rs, ts, obs, "A")})
                obs["remaining"] = 0
                self.assertFalse({a["type"] for a in O.legal_actions(rs, ts, obs, "A")} & {"nuki", "kan"})
                n += 1
        self.assertGreaterEqual(n, 1)

    def test_T7_11_call_that_leaves_no_discard_is_not_legal(self):
        """鳴いたあとに切れる牌が残らない鳴き（残りが喰い替えになる牌だけ）はできない。"""
        ts, rs = self.ts, self.rs
        norm = R.normalize(rs)
        self.assertEqual(norm["game_rules"]["flow"]["kuikae"], "forbidden")
        by = {}
        for i, t in enumerate(ts["tiles"]):
            by.setdefault(t["kind"], []).append(i)
        m1, m2, m3, m4, p9 = (by[k] for k in ("1m", "2m", "3m", "4m", "9p"))
        # 2m3m で 4m をチー：切れないのは 4m（現物）と 1m（筋）。残りが 1m 1m なら鳴けない、9p があれば鳴ける
        self.assertFalse(O._call_leaves_discard(ts, norm, [m1[0], m1[1], m2[0], m3[0]], "chi", m4[0], [m2[0], m3[0], m4[0]]))
        self.assertTrue(O._call_leaves_discard(ts, norm, [m1[0], p9[0], m2[0], m3[0]], "chi", m4[0], [m2[0], m3[0], m4[0]]))
        # 4m4m で 4m をポン：切れないのは 4m。残りが 4m だけなら鳴けない
        self.assertFalse(O._call_leaves_discard(ts, norm, [m4[0], m4[1], m4[2]], "pon", m4[3], [m4[0], m4[1], m4[3]]))
        self.assertTrue(O._call_leaves_discard(ts, norm, [m4[0], m4[1], m1[0]], "pon", m4[3], [m4[0], m4[1], m4[3]]))
        # 合法手の一覧でも同じ：対局の中のチーの場面を借り、手牌だけ差し替える
        for rnd in self.rec["rounds"]:
            i = next((k for k, e in enumerate(rnd["events"]) if e["t"] == "chi"), None)
            if i is not None:
                break
        seat = rnd["events"][i]["who"]
        obs = O.observe(self.rec, rnd["index"], i - 1, seat, rs, ts, self.wmap)
        obs["melds"][seat] = [{"kind": "pon", "tiles": by[k][:3], "from": (seat + 1) % 4} for k in ("E", "S", "W")]
        obs["last_discard"] = {"who": (seat - 1) % 4, "tile": m4[0]}
        obs["riichi"] = [False] * 4
        obs["hand"] = sorted([m1[0], m1[1], m2[0], m3[0]])
        self.assertNotIn("chi", {a["type"] for a in O.legal_actions(rs, ts, obs, "C")})
        obs["hand"] = sorted([m1[0], p9[0], m2[0], m3[0]])
        self.assertIn("chi", {a["type"] for a in O.legal_actions(rs, ts, obs, "C")})

    def test_T7_12_robbing_a_kan(self):
        """槍槓：加槓と抜きの牌はロンできる。暗槓の牌は、ルールが認めていて国士無双の形のときだけ。大明槓の牌はできない。フリテンならできない。"""
        ts = self.ts
        by = {}
        for i, t in enumerate(ts["tiles"]):
            by.setdefault(t["kind"], []).append(i)
        rnd = self.rec["rounds"][0]
        obs = O.observe(self.rec, rnd["index"], 2, 1, self.rs, ts, self.wmap)
        self.assertEqual((obs["melds"][1], obs["discards"][1]), ([], []))
        obs["passed"], obs["passed_riichi"] = [], []
        yao = ["1m", "9m", "1p", "9p", "1s", "9s", "E", "S", "W", "N", "P", "F", "C"]
        kokushi = [by[k][0] for k in yao]                                      # 国士無双 13 面待ち
        normal = [by[k][0] for k in ("1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "1p", "E", "E")][:10] + [by["1p"][1], by["E"][1], by["E"][2]]
        tenhou = R.normalize(self.rs)                                           # kokushi_ankan_chankan false
        jpml = R.normalize(R.find(name="jantama-4p"))                           # kokushi_ankan_chankan true
        self.assertFalse(tenhou["game_rules"]["flow"]["kokushi_ankan_chankan"])
        self.assertTrue(jpml["game_rules"]["flow"]["kokushi_ankan_chankan"])
        obs["hand"] = sorted(kokushi)
        tile = by["E"][3]
        self.assertTrue(O.can_rob(tenhou, ts, obs, "kakan", tile))
        self.assertFalse(O.can_rob(tenhou, ts, obs, "ankan", tile))              # ルールが認めていない
        self.assertTrue(O.can_rob(jpml, ts, obs, "ankan", tile))                 # 認めるルールで、国士無双
        self.assertFalse(O.can_rob(jpml, ts, obs, "minkan", tile))
        self.assertFalse(O.can_rob(jpml, ts, obs, "kakan", by["5m"][0]))         # 和了形にならない
        obs["hand"] = sorted(normal)                                            # 123456789m 11p EE：1p か E 待ち
        self.assertTrue(O.can_rob(jpml, ts, obs, "kakan", by["1p"][2]))
        self.assertFalse(O.can_rob(jpml, ts, obs, "ankan", by["1p"][2]))         # 認めるルールでも、国士無双でなければ暗槓の牌はロンできない
        obs["discards"][1] = [by["E"][3]]                                       # 待ちの牌を自分で捨てている
        self.assertFalse(O.can_rob(jpml, ts, obs, "kakan", by["1p"][2]))
        obs["discards"][1] = []
        self.assertTrue(O.can_rob(jpml, ts, obs, "nuki", by["E"][3]))            # 抜きの牌

    def test_T7_8_completion_and_waits(self):
        ts = self.ts
        ids = lambda *labels: [TS.parse_label(ts, l)[i] for i, l in enumerate(labels)]  # noqa: E731
        # 123m 456p 789s 11z(E E) 22z(S S)… → 4 面子 1 雀頭
        hand = []
        for lab in ("1m", "2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "E", "E", "S", "S"):
            hand.append(next(t for t in TS.parse_label(ts, lab) if t not in hand))
        self.assertTrue(O.is_complete(ts, hand, 0, 13))
        self.assertFalse(O.is_complete(ts, hand[:-1] + [TS.parse_label(ts, "W")[0]], 0, 13))
        # 七対子
        hand = []
        for lab in ("1m", "1m", "3p", "3p", "5s", "5s", "E", "E", "S", "S", "W", "W", "C", "C"):
            hand.append(next(t for t in TS.parse_label(ts, lab) if t not in hand))
        self.assertTrue(O.is_complete(ts, hand, 0, 13))
        # 待ち：23m 456p 789s EEE SS → 1m・4m
        hand = []
        for lab in ("2m", "3m", "4p", "5p", "6p", "7s", "8s", "9s", "E", "E", "E", "S", "S"):
            hand.append(next(t for t in TS.parse_label(ts, lab) if t not in hand))
        self.assertEqual(O.waits(ts, hand, 0, 13), {"1m", "4m"})

    def test_T7_9_mjai_roundtrip(self):
        evs = MJ.to_mjai(self.rec, self.rs, self.ts, self.wmap, seat=0)
        self.assertEqual(evs[0]["type"], "start_game")
        self.assertEqual(evs[1]["type"], "start_kyoku")
        self.assertEqual(evs[1]["tehais"][1], ["?"] * 13)
        self.assertEqual(len(evs[1]["tehais"][0]), 13)
        self.assertEqual(evs[-1]["type"], "end_game")
        # 他家のツモは伏せる
        self.assertTrue(all(e["pai"] == "?" for e in evs if e["type"] == "tsumo" and e["actor"] != 0))
        # 応答 → 行動 → 合法手に含まれる
        rnd = self.rec["rounds"][0]
        at = next(i for i, e in enumerate(rnd["events"]) if e["t"] == "draw" and e["who"] == 0)
        obs = O.observe(self.rec, 0, at, 0, self.rs, self.ts, self.wmap)
        legal = O.legal_actions(self.rs, self.ts, obs, "B")
        pai = TS.tile_label(self.ts, obs["hand"][0])
        act = MJ.from_mjai_action({"type": "dahai", "actor": 0, "pai": pai}, self.ts, obs)
        self.assertIn(O.action_key(act), {O.action_key(a) for a in legal})
        self.assertEqual(MJ.from_mjai_action({"type": "none"}, self.ts, obs), {"type": "pass"})


class TestAnnotation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec, cls.walls, cls.rs, cls.ts = sp_game("tenhou-4p-hanchan-red")
        cls.wmap = {w["id"]: w for w in cls.walls}
        cls.ann = E.annotate(cls.rec, cls.rs, cls.ts, cls.wmap)

    def _ng(self, ann, part, cross=True):
        ann["id"] = A.compute_id(ann)
        with self.assertRaises(ValidationError) as cm:
            if cross:
                A.validate(ann, self.rec, self.rs, self.ts, self.wmap)
            else:
                A.validate(ann)
        self.assertIn(part, str(cm.exception))

    def test_T5_0_generated_passes(self):
        self.assertEqual(A.validate(self.ann, self.rec, self.rs, self.ts, self.wmap), [])
        self.assertEqual(A.validate(self.ann), [])
        self.assertGreater(len(self.ann["points"]), 400)
        self.assertTrue(A.filename(self.ann).endswith("_nm-waits.annotation.json"))

    def test_T5_1_record_at_actor(self):
        ann = copy.deepcopy(self.ann)
        ann["record"]["id"] = "sha256:" + "0" * 64
        self._ng(ann, "record.id")
        ann = copy.deepcopy(self.ann)
        ann["points"][0]["at"] = 9999
        self._ng(ann, "at")
        ann = copy.deepcopy(self.ann)
        ann["points"][0]["actor"] = 7
        self._ng(ann, "")

    def test_T5_2_phase_matches_event(self):
        ann = copy.deepcopy(self.ann)
        ann["points"][0]["phase"] = "C"
        self._ng(ann, "phase")
        ann = copy.deepcopy(self.ann)
        p = ann["points"][0]
        p["actual"] = {"type": "discard", "tile": p["candidates"][1]["tile"]}   # 実際と違う打牌
        p["best"] = 0
        p["loss"] = p["candidates"][0]["values"]["waits"] - p["candidates"][1]["values"]["waits"]
        p["verdict"] = "o" if p["loss"] <= 0 else "d" if p["loss"] <= 1 else "x"
        self._ng(ann, "次の event")

    def test_T5_3_candidates_must_be_legal(self):
        ann = copy.deepcopy(self.ann)
        p = ann["points"][0]
        p["candidates"].append({"type": "chi", "tiles": [0, 4, 8], "values": {"waits": 0}})
        self._ng(ann, "X12")
        # 送りカン不可（ankan_after=none）のルールで、立直後の暗槓を候補にすると断る
        rec = self.rec
        hit = None
        for rnd in rec["rounds"]:
            for at, e in enumerate(rnd["events"]):
                if e["t"] == "kan" and e["kind"] == "ankan":
                    hit = (rnd["index"], at - 1, e["who"], e["tiles"])
                    break
            if hit:
                break
        if hit:
            r, at, seat, tiles = hit
            obs = O.observe(rec, r, at, seat, self.rs, self.ts, self.wmap)
            legal = O.legal_actions(self.rs, self.ts, obs, "A")
            self.assertTrue(any(a["type"] == "kan" for a in legal))
            # 立直中と仮定して ankan_after=none にすると消える（局面を立直状態にして確認）
            obs2 = dict(obs, riichi=[True if s == seat else x for s, x in enumerate(obs["riichi"])])
            rs2 = R.new_from(copy.deepcopy(self.rs), "nokan", {"game_rules.flow.riichi.ankan_after": "none"})
            self.assertFalse(any(a["type"] == "kan" for a in O.legal_actions(rs2, self.ts, obs2, "A")))

    def test_T5_5_metrics_and_values(self):
        ann = copy.deepcopy(self.ann)
        ann["evaluator"]["metrics"].append({"name": "waits", "scope": "candidate", "kind": "count", "higher_is_better": True})
        self._ng(ann, "重複", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["evaluator"]["metrics"][1]["primary"] = True
        self._ng(ann, "primary", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["points"][0]["candidates"][0]["values"]["bogus"] = 1
        self._ng(ann, "宣言されていない", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["evaluator"]["metrics"].append({"name": "rank_prob", "scope": "point", "kind": "prob_vector"})
        ann["points"][0]["estimates"]["rank_prob"] = [0.5, 0.5, 0.5, 0.5]
        self._ng(ann, "合計", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["points"][0]["loss"] += 1
        self._ng(ann, "loss", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["points"][0]["best"] = len(ann["points"][0]["candidates"])
        self._ng(ann, "best", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["points"][0]["verdict"] = "x"
        self._ng(ann, "verdict", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["points"].append(copy.deepcopy(ann["points"][0]))
        self._ng(ann, "2 つ", cross=False)
        ann = copy.deepcopy(self.ann)
        ann["id"] = "sha256:" + "1" * 64
        with self.assertRaises(ValidationError):
            A.validate(ann)

    def test_T5_6_multiple_evaluators(self):
        ann2 = copy.deepcopy(self.ann)
        ann2["evaluator"]["name"] = "nm-waits-b"
        ann2 = A.finalize(ann2)
        self.assertEqual(A.validate(ann2, self.rec, self.rs, self.ts, self.wmap), [])
        self.assertNotEqual(A.filename(ann2), A.filename(self.ann))


if __name__ == "__main__":
    unittest.main()
