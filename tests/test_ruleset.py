"""試験 T3 ルール。"""
import copy
import unittest

from nmahjong import ruleset as R, tileset as TS
from nmahjong.canon import ValidationError

WALL4 = {"deal": "N_each_then_1_to_dealer", "dead_wall": 14, "dora_indicator": [8], "ura_indicator": [9],
         "kan_dora": [6, 4, 2, 0], "kan_ura": [7, 5, 3, 1], "rinshan": [12, 13, 10, 11], "break": {"by": "dice"}}


def minimal(ts, **extra):
    rs = {"format": R.FORMAT, "version": R.VERSION, "name": "t", "tileset": TS.ref(ts), "players": 4, "hand_size": 13,
          "length": "east_south", "winds": ["E", "S", "W", "N"], "wall_rules": copy.deepcopy(WALL4)}
    rs.update(extra)
    return rs


class TestRuleset(unittest.TestCase):
    def setUp(self):
        self.defs = TS.bundled_definitions()
        self.ts = TS.build(**self.defs["mpsz"])

    def test_T3_1_bundled_all_validate(self):
        rss = R.bundled()
        self.assertGreaterEqual(len(rss), 25)
        for rs in rss:
            ts = TS.find(id=rs["tileset"]["id"])
            norm, warns = R.validate(rs, ts)
            self.assertEqual(norm["id"], rs["id"])
            if rs.get("unknown"):
                self.assertTrue(any(w.startswith("欠落") for w in warns), rs["name"])

    def test_T3_2_defaults_and_id(self):
        a = R.finalize(minimal(self.ts))
        b = R.finalize(minimal(self.ts, game_rules=copy.deepcopy(R.DEFAULT_GAME_RULES), end=copy.deepcopy(R.DEFAULT_END),
                               settlement=copy.deepcopy(R.DEFAULT_SETTLEMENT)))
        self.assertEqual(a["id"], b["id"], "省略と明示は同じ id")
        c = R.finalize(minimal(self.ts, name="other-name"))
        self.assertEqual(a["id"], c["id"], "name は id に入らない")
        d = R.finalize(minimal(self.ts, meta={"note": "x"}))
        self.assertEqual(a["id"], d["id"], "meta は id に入らない")
        e = R.finalize(minimal(self.ts, unknown=["end.tobi"]))
        self.assertNotEqual(a["id"], e["id"], "unknown は id に入る")

    def test_T3_3_required_and_ranges(self):
        for mutate in (
            lambda r: r.pop("wall_rules"),
            lambda r: r.__setitem__("players", 0),
            lambda r: r.__setitem__("hand_size", 12),                      # standard で mod 3 ≠ 1
            lambda r: r.__setitem__("winds", ["E", "S"]),
            lambda r: r["wall_rules"].__setitem__("dead_wall", 200),       # N×M+1+dead > K
            lambda r: r["wall_rules"].__setitem__("kan_ura", [7, 5]),      # 長さ不一致
            lambda r: r["wall_rules"].__setitem__("rinshan", [8, 13]),     # 重複位置
            lambda r: r.__setitem__("length", "custom"),                   # rounds_total 無し
        ):
            rs = minimal(self.ts); mutate(rs)
            with self.assertRaises(ValidationError):
                R.validate(R.finalize(rs), self.ts)

    def test_T3_4_unknown_keys_and_vocab_rejected(self):
        for extra in (
            {"game_rules": {"flow": {"foo": 1}}},
            {"game_rules": {"yaku": {"overrides": {"not_a_yaku": 1}}}},
            {"game_rules": {"flow": {"kuikae": "sometimes"}}},
            {"settlement": {"chips": [{"on": "lucky", "per": "tile", "count": 1, "payer": "all"}]}},
            {"bogus": 1},
        ):
            rs = minimal(self.ts, **extra)
            with self.assertRaises(ValidationError):
                R.validate(R.finalize(rs), self.ts)

    def test_T3_7_id_mismatch(self):
        rs = R.finalize(minimal(self.ts))
        rs["id"] = "sha256:" + "0" * 64
        with self.assertRaises(ValidationError):
            R.validate(rs, self.ts)

    def test_T3_8_yaku_han_values(self):
        rs = minimal(self.ts, game_rules={"yaku": {"overrides": {"tanyao": 10, "riichi": {"closed": 10, "open": None},
                                                                  "renhou": "yakuman:2", "ippatsu": False}}})
        R.validate(R.finalize(rs), self.ts)
        for bad in ({"tanyao": 0}, {"tanyao": True}, {"tanyao": "yakuman:0"}, {"tanyao": {"closed": 0}}):
            rs = minimal(self.ts, game_rules={"yaku": {"overrides": bad}})
            with self.assertRaises(ValidationError):
                R.validate(R.finalize(rs), self.ts)

    def test_T3_9_settlement_forms(self):
        rs = minimal(self.ts, settlement={
            "uma": {"by_floating": {"1": [12, -1, -3, -8], "2": [8, 4, -4, -8], "3": [8, 3, 1, -12]}, "threshold": "start"},
            "external_points": [{"system": "x", "kind": "rank_plus_raw", "raw_base": 25000, "raw_divisor": 1000,
                                 "rank_points": {"by_player_rank": {"a": [1, 2, 3, -6]}}}],
            "chips": [{"on": "win_kind", "kind": "ippatsu", "per": "event", "count": 1, "payer": "loser"}],
            "payout": {"unit": {"code": "COIN"}, "per_pt": 10, "chip_value": 5, "fees": {"by_rank": [7, 5, 5, 5]}}})
        R.validate(R.finalize(rs), self.ts)
        rs = minimal(self.ts, settlement={"uma": {"by_floating": {"1": [1, 0, 0, -1]}}})   # キー不足
        with self.assertRaises(ValidationError):
            R.validate(R.finalize(rs), self.ts)
        rs = minimal(self.ts, settlement={"chips": [{"on": "tobi", "per": "event", "count": 1, "payer": "loser"}],
                                          "payout": {"unit": {"code": "JPY"}, "per_pt": 100}})   # chip_value 無し
        with self.assertRaises(ValidationError):
            R.validate(R.finalize(rs), self.ts)

    def test_T3_10_marks_and_ankan_after(self):
        tsp = TS.build(**self.defs["mpsz-pocchi"])
        rs = minimal(tsp, game_rules={"marks": {"red": {"effects": ["dora"]}, "pocchi": {"effects": ["dora", "almighty"], "when": {"state": "riichi", "how": "tsumo"}},
                                                "reverse_pocchi": {"effects": ["almighty", "reverse"]}},
                                      "flow": {"riichi": {"ankan_after": "any"}}})
        R.validate(R.finalize(rs), tsp)
        for bad in ({"red": {"effects": ["none", "dora"]}}, {"red": {"effects": ["reverse"]}}, {"red": {"effects": ["gold"]}}):
            rs = minimal(tsp, game_rules={"marks": bad})
            with self.assertRaises(ValidationError):
                R.validate(R.finalize(rs), tsp)
        # 赤なし牌表に既定の marks.red → 警告のみ
        nored = TS.build(**self.defs["mpsz-nored"])
        _, warns = R.validate(R.finalize(minimal(nored)), nored)
        self.assertTrue(any("marks.red" in w for w in warns))

    def test_T3_11_generator(self):
        base = R.find(name="mleague")
        a = R.new_from(base, "x", {"settlement.uma": [20, 10, -10, -20]})
        b = R.new_from(base, "y", {"settlement.uma": [20, 10, -10, -20]})
        self.assertEqual(a["id"], b["id"])
        rows = R.diff(R.find(name="rmu-a"), R.find(name="rmu-b"))
        keys = {k for k, _, _ in rows}
        self.assertEqual(keys, {"game_rules.dora.ura", "game_rules.dora.kan", "game_rules.dora.kan_ura", "game_rules.flow.ippatsu"})

    def test_T3_12_nm_defaults(self):
        rs = R.find(name="nm-2p-4-room")
        self.assertEqual(rs["players"], 2)
        self.assertEqual(rs["game_rules"]["scoring"]["payment"], "4p_total_from_opponent")
        self.assertEqual(rs["wall_rules"]["rinshan"], "live")
        fl = R.normalize(rs)["game_rules"]["flow"]
        self.assertEqual((fl["pon"], fl["chi"], fl["kan_kinds"], fl["max_kans"]), (False, False, ["ankan"], 1))     # 鳴きは暗槓だけ
        rs4 = R.find(name="nm-2p-4-m")
        self.assertEqual(rs4["game_rules"]["scoring"]["payment"], "4p_dealer_share_from_opponent")
        self.assertEqual(rs4["wall_rules"]["rinshan"], [3, -1])
        rs1 = R.find(name="nm-2p-1-m")
        self.assertEqual(rs1["end"]["max_honba"], 50)
        self.assertEqual(rs1["settlement"]["tie"], "seat_order")
        # payment が standard 以外で 4 人はエラー
        bad = minimal(self.ts, game_rules={"scoring": {"payment": "4p_total_from_opponent"}})
        with self.assertRaises(ValidationError):
            R.validate(R.finalize(bad), self.ts)


if __name__ == "__main__":
    unittest.main()


class TestJsParity(unittest.TestCase):
    """T8：JS 実装が読む data/defaults.json が Python の既定値と同じ（tools/gen_js_bundle.py で生成）。"""

    def test_T8_7_defaults_json_matches(self):
        import json, os
        from nmahjong import ruleset as R
        p = os.path.join(os.path.dirname(R.__file__), "data", "defaults.json")
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertEqual(d["game_rules"], R.DEFAULT_GAME_RULES)
        self.assertEqual(d["end"], R.DEFAULT_END)
        self.assertEqual(d["settlement"], R.DEFAULT_SETTLEMENT)
        self.assertEqual(d["enabled_defaults"], R.ENABLED_DEFAULTS)
        self.assertEqual(set(d["passthrough"]), R._PASSTHROUGH)
        self.assertEqual(set(d["free_key_objects"]), R._FREE_KEY_OBJECTS)
        self.assertEqual(d["enum"], R.ENUM)
