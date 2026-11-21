"""N 枚麻雀の既定ルール（nmahjong/nmrules.py、同梱の nm-*、nm-defaults.md）。"""
import unittest

from nmahjong import nmrules as NR, ruleset as R, scoring as S, tileset as TS
from nmahjong.canon import ValidationError


class TestNmRules(unittest.TestCase):
    def test_N1_bundled_ids_match(self):
        # 同梱の nm-*（東南戦、m／mps／mpsz）は ruleset_for が作るものと同じ id
        for n in NR.HAND_SIZES:
            for suits in ("m", "mps", "mpsz"):
                rs = NR.ruleset_for(n, suits, "east_south")
                self.assertEqual(R.find(name=f"nm-2p-{n}-{suits}")["id"], rs["id"])
                R.validate(rs, TS.find(id=rs["tileset"]["id"]))

    def test_N2_other_colors_and_lengths(self):
        # 色と長さを変えた組み合わせ。名前は nm-2p-{枚数}-{色}[-east|-one]、同じ指定なら同じ id、長さが違えば別の id
        a = NR.ruleset_for(4, ["z"], "east")
        self.assertEqual(a["name"], "nm-2p-4-z-east")
        self.assertEqual(a["id"], NR.ruleset_for(4, "z", "east")["id"])
        self.assertNotEqual(a["id"], NR.ruleset_for(4, "z", "one")["id"])
        self.assertEqual(NR.ruleset_for(1, "sm", "one")["name"], "nm-2p-1-ms-one")      # 色は m p s z の順に並べる
        ts = NR.tileset_for("pz")
        self.assertEqual((ts["name"], len(ts["tiles"])), ("pz", 64))
        for bad in (lambda: NR.ruleset_for(5, "m"), lambda: NR.ruleset_for(4, "x"), lambda: NR.ruleset_for(4, ""),
                    lambda: NR.ruleset_for(4, "m", "full")):
            with self.assertRaises(ValidationError):
                bad()

    def test_N3_payment_modes(self):
        sc4 = R.normalize(R.find(name="nm-2p-4-m"))["game_rules"]["scoring"]
        # 20 符 2 翻（基本点 320）：ロン子 1300・親 2000、ツモは基本点×2 を切り上げ＝700
        self.assertEqual(S.total_points(20, 2, 0, False, False, 2, sc4)[0], 1300)
        self.assertEqual(S.total_points(20, 2, 0, True, False, 2, sc4)[0], 2000)
        self.assertEqual(S.total_points(20, 2, 0, False, True, 2, sc4)[0], 700)
        self.assertEqual(S.total_points(20, 2, 0, True, True, 2, sc4)[0], 700)
        self.assertEqual(S.total_points(30, 6, 0, True, True, 2, sc4)[0], 6000)      # 跳満ツモ
        self.assertEqual(S.total_points(0, 0, 2, False, False, 2, sc4)[0], 64000)    # 二倍役満ロン（子）
        sc1 = R.normalize(R.find(name="nm-2p-1-m"))["game_rules"]["scoring"]
        self.assertEqual(S.total_points(20, 7, 0, False, False, 2, sc1)[0], 12000)   # 最低が跳満
        self.assertEqual(S.total_points(20, 7, 0, True, True, 2, sc1)[0], 6000)
        self.assertEqual(S.total_points(20, 0, 2, True, False, 2, sc1)[0], 96000)

    def test_N4_calls_kans_and_riichi_sticks(self):
        for n in NR.HAND_SIZES:
            fl = R.normalize(R.find(name=f"nm-2p-{n}-mps"))["game_rules"]["flow"]
            self.assertFalse(fl["chi"])
            self.assertFalse(fl["pon"])
            self.assertEqual(fl["riichi"]["stick_at_end"], "to_first")        # 終局時に残った供託はトップへ
            self.assertFalse(fl["riichi"]["stick_if_ronned"])                 # 宣言牌でロンされたら立直は成立せず、棒は出さない
            if n == 1:
                self.assertEqual((fl["kan_kinds"], fl["max_kans"]), ([], 0))
            else:
                self.assertEqual((fl["kan_kinds"], fl["max_kans"], fl["max_kans_per_player"]), (["ankan"], 2, 1))

    def test_N5_larger_hands_extend_the_four_tile_rules(self):
        # 7・10・13 枚は 4 枚の延長：王牌・点数・支払い・終了・精算は 4 枚と同じ。役は標準の役（七対子・国士無双なし、人和は役満）
        base = R.normalize(R.find(name="nm-2p-4-mps"))
        for n in (7, 10, 13):
            x = R.normalize(R.find(name=f"nm-2p-{n}-mps"))
            self.assertEqual(x["hand_size"], n)
            for key in ("wall_rules", "end", "settlement"):
                self.assertEqual(x[key], base[key], (n, key))
            self.assertEqual(x["game_rules"]["scoring"], base["game_rules"]["scoring"])
            y = x["game_rules"]["yaku"]
            self.assertEqual(y["base"], "riichi-standard")
            self.assertEqual((y["overrides"]["chiitoitsu"], y["overrides"]["kokushi"], y["overrides"]["renhou"]), (False, False, "yakuman"))


if __name__ == "__main__":
    unittest.main()
