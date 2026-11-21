"""試験 T4 対局（X4〜X8）。試験データは 13 枚麻雀の対局（tests/data/corpus/selfplay-13.jsonl、四麻・天鳳のルール）。"""
import copy
import unittest

from nmahjong import record as REC, ruleset as R, scoring as S
from nmahjong.canon import ValidationError
from nmahjong.tenhou import importer as I

from corpus import sp_game


class TestRecord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec, cls.walls, cls.rs, cls.ts = sp_game("tenhou-4p-hanchan-red")
        cls.wmap = {w["id"]: w for w in cls.walls}

    def _ok(self, rec):
        return REC.validate(rec, self.rs, self.ts, self.wmap)

    def _ng(self, rec, msg_part=None):
        rec["id"] = REC.compute_id(rec)
        with self.assertRaises(ValidationError) as cm:
            REC.validate(rec, self.rs, self.ts, self.wmap)
        if msg_part:
            self.assertIn(msg_part, str(cm.exception))

    def test_T4_1_game_passes(self):
        self.assertEqual(self._ok(self.rec), [])
        self.assertEqual(len(self.rec["rounds"]), 11)
        self.assertEqual(sum(self.rec["final"]["scores"]), 100000)        # 終局時の供託はトップへ渡っている
        self.assertAlmostEqual(sum(self.rec["final"]["settled"]), 0, places=6)
        self.assertEqual(sorted(self.rec["final"]["rank"]), [1, 2, 3, 4])

    def test_T4_2_wall_tileset_mismatch(self):
        wmap = copy.deepcopy(self.wmap)
        wid = self.rec["rounds"][0]["wall"]["id"]
        wmap[wid]["tileset"]["id"] = "sha256:" + "1" * 64
        with self.assertRaises(ValidationError):
            REC.validate(self.rec, self.rs, self.ts, wmap)

    def test_T4_3_draw_mismatch_with_wall(self):
        rec = copy.deepcopy(self.rec)
        ev = next(e for e in rec["rounds"][0]["events"] if e["t"] == "draw" and e["who"] == 1)
        ev["tile"] = (ev["tile"] + 1) % 136
        self._ng(rec, "X5")

    def test_T4_4_score_continuity(self):
        rec = copy.deepcopy(self.rec)
        rec["rounds"][1]["state"]["scores"][0] += 100
        self._ng(rec, "前局の結果")

    def test_T4_5_deltas_and_points(self):
        rec = copy.deepcopy(self.rec)
        w = rec["rounds"][0]["result"]["wins"][0]
        w["points"] += 100
        self._ng(rec, "点数表")
        rec = copy.deepcopy(self.rec)
        w = rec["rounds"][0]["result"]["wins"][0]
        w["deltas"][0] -= 100
        self._ng(rec, "増減")

    def test_T4_6_yaku_adoption_and_han(self):
        rec = copy.deepcopy(self.rec)
        w = rec["rounds"][0]["result"]["wins"][0]
        w["yaku"].append({"name": "daisharin", "han": 1})   # 不採用のローカル役
        self._ng(rec, "不採用")
        rec = copy.deepcopy(self.rec)
        w = rec["rounds"][0]["result"]["wins"][0]
        w["han"] += 1
        self._ng(rec, "翻の合計")

    def test_T4_7_flow_constraints(self):
        rec = copy.deepcopy(self.rec)
        evs = rec["rounds"][0]["events"]
        evs.insert(5, {"t": "chi", "who": 1, "from": 0, "tiles": [0, 4, 8]})
        rs = copy.deepcopy(self.rs)
        rs = R.new_from(rs, "nochi", {"game_rules.flow.chi": False})
        rec["ruleset"] = R.ref(rs)
        rec["id"] = REC.compute_id(rec)
        with self.assertRaises(ValidationError) as cm:
            REC.validate(rec, rs, self.ts, self.wmap)
        self.assertIn("chi 禁止", str(cm.exception))

    def test_T4_8_final_consistency(self):
        rec = copy.deepcopy(self.rec)
        rec["final"]["rank"] = [1, 2, 3, 4]
        self._ng(rec, "final.rank")
        rec = copy.deepcopy(self.rec)
        rec["final"]["settled"][0] += 1
        self._ng(rec, "X8")
        rec = copy.deepcopy(self.rec)
        rec["final"]["scores"][rec["final"]["rank"].index(1)] -= 1000   # 供託をトップへ渡していない
        self._ng(rec, "供託")

    def test_T4_9_events_shape(self):
        rec = copy.deepcopy(self.rec)
        rec["rounds"][0]["events"][0] = {"t": "draw", "who": 0, "tile": 1}
        self._ng(rec, "deal")
        rec = copy.deepcopy(self.rec)
        rec["rounds"][0]["events"].append({"t": "bogus"})
        self._ng(rec, "語彙外")
        rec = copy.deepcopy(self.rec)
        rec["rounds"][0]["events"][3]["tile"] = 999
        self._ng(rec)

    def test_T4_10_id_and_unknown_key(self):
        rec = copy.deepcopy(self.rec)
        rec["id"] = "sha256:" + "0" * 64
        with self.assertRaises(ValidationError):
            REC.validate(rec, self.rs, self.ts, self.wmap)
        rec = copy.deepcopy(self.rec)
        rec["extra"] = 1
        self._ng(rec, "未知")

    def test_T4_11_wall_null_requires_hands(self):
        rec = copy.deepcopy(self.rec)
        rec["rounds"][0]["wall"] = None
        self._ng(rec, "deal.hands")
        rec = copy.deepcopy(self.rec)
        rec["rounds"][0]["wall"] = None
        rec["rounds"][0]["events"][0]["hands"] = [[0] * 13] * 4
        rec["id"] = REC.compute_id(rec)
        warns = REC.validate(rec, self.rs, self.ts, self.wmap)
        self.assertTrue(any("山なし" in w for w in warns))

    def test_T4_12_scoring_table(self):
        sc = R.DEFAULT_GAME_RULES["scoring"]
        self.assertEqual(S.total_points(30, 1, 0, False, False, 4, sc)[0], 1000)
        self.assertEqual(S.total_points(40, 2, 0, False, False, 4, sc)[0], 2600)
        self.assertEqual(S.total_points(30, 4, 0, False, False, 4, sc)[0], 8000)   # 切り上げ満貫
        self.assertEqual(S.total_points(40, 4, 0, True, False, 4, sc)[0], 12000)
        self.assertEqual(S.total_points(30, 3, 0, False, True, 4, sc), (4000, [2000, 1000, 1000]))
        self.assertEqual(S.total_points(0, 13, 1, False, False, 4, sc)[0], 32000)
        sc2 = dict(sc, mangan_round_up=False)
        self.assertEqual(S.total_points(30, 4, 0, False, False, 4, sc2)[0], 7700)

    def test_T4_13_settlement(self):
        st = R.normalize(self.rs)["settlement"]
        self.assertEqual(S.settle([11600, 18600, 30200, 39600], st), [-38, -21, 10, 49])
        st2 = R.DEFAULT_SETTLEMENT
        self.assertEqual(sum(S.settle([25000, 25000, 25000, 25000], st2)), 0)
        self.assertEqual(S.ranks([30000, 30000, 20000, 20000], tie="seat_order"), [1, 2, 3, 4])
        self.assertEqual(S.ranks([30000, 30000, 20000, 20000], tie="split"), [1, 1, 3, 3])

    def test_T4_14_rounding_on_score(self):
        """天鳳の丸め：持ち点を 1000 点単位に四捨五入（28500→29→−1pt、34500→35→+5pt、−500→−1→−31pt）。公開牌譜 1002 件で確認。"""
        st = R.normalize(self.rs)["settlement"]
        # 28500/24500/34500/12500：丸め後 −1/−5/+4、トップ(34500)が残りを吸収
        self.assertEqual(S.settle([28500, 24500, 34500, 12500], st), [9, -15, 43, -37])
        self.assertEqual(S.settle([36500, 24400, 39600, -500], st), [17, -16, 50, -51])
        self.assertEqual(S.settle([24400, 25600, 35000, 15000], st), [-16, 6, 45, -35])
        self.assertEqual(S.settle([30000, 30000, 20000, 20000], st), [40, 10, -20, -30])   # 同点は起家側が上位

    def test_T4_15_tenhou_ruleset_by_go_type(self):
        self.assertEqual(I.ruleset_name_for_type(0xa9), "tenhou-4p-hanchan-red")
        self.assertEqual(I.ruleset_name_for_type(0xe1), "tenhou-4p-tonpu-red")
        self.assertEqual(I.ruleset_name_for_type(0xb9), "tenhou-3p")
        with self.assertRaises(ValidationError):
            I.ruleset_name_for_type(0xab)
        self.assertEqual(R.find(name="tenhou-4p-tonpu-red")["length"], "east")
        self.assertFalse(R.normalize(self.rs)["game_rules"]["scoring"]["mangan_round_up"])


class TestTenhouJson(unittest.TestCase):
    """T6-8：天鳳 JSON（山なし）の取り込み。対局を JSON に書き出して読み戻し、同じ進行・同じ結果になる。"""

    def test_T6_8_roundtrip(self):
        from nmahjong.tenhou import json6 as J
        rec, walls, rs, ts = sp_game("tenhou-4p-hanchan-red")
        wm = {w["id"]: w for w in walls}
        j = J.export_json(rec, rs, ts, wm)
        rec2 = J.import_json(j, source_ref="rt")
        kind = lambda t: ts["tiles"][t]["kind"]  # noqa: E731

        def sig(r):
            out = []
            for e in r["events"]:
                if e["t"] == "abort":
                    continue
                d = {k: v for k, v in e.items() if k not in ("tile", "tiles", "hands")}
                if "tile" in e:
                    d["kind"] = kind(e["tile"])
                if "tiles" in e:
                    d["kinds"] = sorted(kind(t) for t in e["tiles"])
                out.append(d)
            return out
        for a, b in zip(rec["rounds"], rec2["rounds"]):
            self.assertEqual(sig(a), sig(b), a["index"])
            self.assertEqual(a["result"]["scores"], b["result"]["scores"])
            self.assertIsNone(b["wall"])
            self.assertIn("hands", b["events"][0])
            for wa, wb in zip(a["result"]["wins"], b["result"]["wins"]):
                for k in ("who", "from", "han", "points", "deltas"):
                    self.assertEqual(wa[k], wb[k], (a["index"], k))
                # 満貫以上は天鳳 JSON に符が書かれない（「満貫8000点」）ので、符は満貫未満のときだけ比べる
                if S.base_points(wa["fu"], wa["han"], 0, R.normalize(rs)["game_rules"]["scoring"]) < 2000 and not wa.get("yakuman"):
                    self.assertEqual(wa["fu"], wb["fu"], a["index"])
                self.assertEqual(sorted(y["name"] for y in wa["yaku"]), sorted(y["name"] for y in wb["yaku"]))
                self.assertEqual(sorted(map(kind, wa["hand"])), sorted(map(kind, wb["hand"])))
        self.assertEqual(rec2["final"]["scores"], rec["final"]["scores"])
        self.assertEqual(rec2["final"]["settled"], rec["final"]["settled"])
        warns = REC.validate(rec2, rs, ts, {})
        self.assertTrue(any("山なし" in w for w in warns))
        # JSON の記法
        self.assertEqual(J.code_to_kind(51), ("5m", True))
        self.assertEqual(J.kind_to_code("C", False), 47)
        self.assertEqual(J._parse_call("c121314", 1, 4)[:2], ("chi", 0))
        self.assertEqual(J._parse_call("4141p41", 0, 4)[:2], ("pon", 1))
        self.assertEqual(J._parse_call("41p4141", 0, 4)[:2], ("pon", 2))
        # 点の書き方（天鳳・downloadlogs.js 共通）：ロン／子のツモ「子-親」／親のツモ「∀」
        self.assertEqual(J._points_from_info("30符2飜2000点"), 2000)
        self.assertEqual(J._points_from_info("30符3飜1000-2000点"), 4000)
        self.assertEqual(J._points_from_info("満貫4000点∀"), 12000)
        self.assertEqual(J._points_from_info("30符3飜1000-2000点", 3), 3000)     # 三麻（ツモ損）
        # 役名の揺れ（雀魂の表記）
        self.assertEqual(J._yaku_name("役牌 白"), "yakuhai_haku")
        self.assertEqual(J._yaku_name("役牌:白"), "yakuhai_haku")
        self.assertEqual(J._yaku_name("ダブル立直"), "double_riichi")
        self.assertIsNone(J._yaku_name("存在しない役"))
        # 雀魂由来の判定とルール選択
        jt = {"ref": "231101-aaaa", "rule": {"disp": "金の間南喰赤", "aka51": 1}, "dan": ["雀傑★1", "雀傑★2", "雀豪★1", "雀傑★3"]}
        self.assertTrue(J.is_jantama(jt))
        self.assertEqual(J._rule_from_disp(jt["rule"], True)[0], "jantama-4p")
        self.assertFalse(J.is_jantama({"ref": "2019051522gm-00a9-0000-8c64c236", "rule": {"disp": "鳳南喰赤"}}))


class TestTenhouSettlement(unittest.TestCase):
    def test_exact_settlement(self):
        """精算を丸めない版：2026-11 の一般卓の実結果（owari）と一致。"""
        st = R.normalize(R.find(name="tenhou-4p-tonpu-red-exact"))["settlement"]
        self.assertEqual(S.settle([29300, 15800, 30500, 24400], st), [9.3, -34.2, 40.5, -15.6])
        self.assertEqual(S.settle([30400, 13000, 34000, 22600], st), [10.4, -37.0, 44.0, -17.4])
        self.assertEqual(I.ruleset_name_for_type(0x01, True), "tenhou-4p-tonpu-red-exact")
        self.assertTrue(I.owari_has_fraction([304, 10.4, 130, -37.0]))
        self.assertFalse(I.owari_has_fraction([304, 10.0, 130, -37.0]))


if __name__ == "__main__":
    unittest.main()
