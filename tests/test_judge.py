"""和了の役と符の判定（nmahjong/judge.py、試験 T11-1〜T11-3）。"""
import copy
import unittest

from nmahjong import judge as J, ruleset as R, tileset as TS

from corpus import nm_games, sp_games


def tiles(ts, text, used=None):
    """"1m 2m 5p* E" → 牌の番号の列。同じ牌種は別の牌を順に使う。* は印の付いた牌（赤など）、無印は印の無い牌。"""
    used = used if used is not None else set()
    out = []
    for w in text.split():
        marked = w.endswith("*")
        k = w.rstrip("*")
        t = next(t["id"] for t in ts["tiles"] if t["kind"] == k and t["id"] not in used and bool(t.get("mark")) == marked)
        used.add(t)
        out.append(t)
    return out


def ctx(ts, hand, win, tsumo=False, melds=(), seat="S", rnd="E", dora="", ura="", nuki="", **kw):
    used = set()
    h = tiles(ts, hand, used)
    w = tiles(ts, win, used)[0]
    c = {"hand": h + [w], "tile": w, "tsumo": tsumo, "seat_wind": seat, "round_wind": rnd,
         "melds": [{"kind": k, "tiles": tiles(ts, t, used)} for k, t in melds],
         "dora_indicators": tiles(ts, dora, used), "ura_indicators": tiles(ts, ura, used), "nuki": tiles(ts, nuki, used)}
    c.update(kw)
    return c


def names(res):
    return {y["name"]: y.get("han", "yakuman") for y in res["yaku"]}


def variant(base_name, game_rules=None, **top):
    rs = copy.deepcopy(R.find(name=base_name))
    for k in ("id", "name"):
        rs.pop(k, None)
    rs["name"] = "test-variant"

    def merge(a, b):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                merge(a[k], v)
            else:
                a[k] = v
    merge(rs.setdefault("game_rules", {}), game_rules or {})
    rs.update(top)
    return rs


class TestJudgeAgainstRecords(unittest.TestCase):
    def check(self, rec, walls, rs, ts, merge):
        n = 0
        wm = {w["id"]: w for w in walls}
        for rnd in rec["rounds"]:
            for w in rnd["result"].get("wins") or []:
                i = next(k for k, e in enumerate(rnd["events"]) if e["t"] == "win" and e["who"] == w["who"])
                res = J.judge_win(rec, rnd["index"], i, rs, ts, wm)
                self.assertIsNone(J.same_as_recorded(res, w, merge_dora=merge), (rnd["index"], res, w["yaku"], w["fu"]))
                n += 1
        return n

    def test_J1_13_tile_wins_match(self):
        """13 枚麻雀（四麻・三麻）の対局の全和了を判定し直して、記録と同じになる。
        記録を作ったのもこのライブラリなので、ここで確かめるのは「記録からの判定し直しが進行中の判定と同じ」こと。
        役・符・点の独立した裏づけは TestJudgeHands（手で作った和了）と tests/test_tenhou_logs.py（天鳳の牌譜があるとき）。"""
        n = 0
        for rec, walls, rs, ts in sp_games():
            n += self.check(rec, walls, rs, ts, False)
        self.assertGreaterEqual(n, 10)

    def test_J2_nm_engine_wins_match(self):
        n = 0
        for n_tiles in (4, 1):
            for rec, walls, rs, ts in nm_games(n_tiles):
                n += self.check(rec, walls, rs, ts, False)
        self.assertGreater(n, 20)


class TestJudgeHands(unittest.TestCase):
    """手で作った和了（一般的な立直麻雀の数え方で期待値を置いたもの）。実牌譜に出てこない役・設定を確かめる。"""

    @classmethod
    def setUpClass(cls):
        cls.rs = R.find(name="tenhou-4p-hanchan-red")
        cls.ts = TS.find(id=cls.rs["tileset"]["id"])

    def j(self, *a, rs=None, **kw):
        return J.judge(rs or self.rs, self.ts, ctx(self.ts, *a, **kw))

    def test_J3_pinfu_and_fu(self):
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 8s 9s 9s", "7s", riichi=True)
        self.assertEqual((names(r), r["fu"], r["han"]), ({"riichi": 1}, 40, 1))                       # 嵌張 2 符＋門前ロン 10 → 32 → 40
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 9s", "5s")
        self.assertEqual((names(r), r["fu"]), ({"pinfu": 1}, 30))
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 9s", "5s", tsumo=True)
        self.assertEqual((names(r), r["fu"]), ({"menzen_tsumo": 1, "pinfu": 1}, 20))
        r = self.j("3p 4p 5p 6s 7s 9s 9s", "5s", melds=[("chi", "2m 3m 4m"), ("pon", "C C C")])
        self.assertEqual((names(r), r["fu"]), ({"yakuhai_chun": 1}, 30))                               # 明刻（字牌）4 符 → 24 → 30
        r = self.j("3p 4p 5p 6s 7s 2s 2s", "8s", melds=[("chi", "2m 3m 4m"), ("chi", "6m 7m 8m")])
        self.assertEqual((names(r), r["fu"]), ({"tanyao": 1}, 30))                                     # 喰い平和形のロンは 30 符

    def test_J4_interpretation_picks_highest(self):
        r = self.j("1m 1m 1m 2m 3m 4m 5m 6m 7m 8m 9m 9m 9m", "5m", tsumo=True)
        self.assertEqual(names(r), {"junsei_chuuren": "yakuman"})
        r = self.j("1m 1m 1m 2m 3m 4m 5m 6m 7m 8m 9m 9m 9m", "5m", tsumo=True,
                   rs=variant("tenhou-4p-hanchan-red", {"yaku": {"overrides": {"chuuren": False, "junsei_chuuren": False}}}))
        self.assertEqual(names(r), {"menzen_tsumo": 1, "chinitsu": 6})
        r = self.j("2m 2m 3m 3m 4m 4m 6p 6p 7p 7p 8p 8p 5s", "5s")
        self.assertEqual(names(r), {"tanyao": 1, "ryanpeikou": 3})                                     # 七対子（2 翻）より二盃口
        r = self.j("1m 1m 2m 2m 3m 3m 5p 5p 7p 7p 9s 9s E", "E")
        self.assertEqual((names(r), r["fu"]), ({"chiitoitsu": 2}, 25))

    def test_J5_yakuman(self):
        cases = [
            ("1m 9m 1p 9p 1s 9s E S W N P F C", "1m", {}, {"kokushi13": "yakuman"}),
            ("1m 1m 9m 1p 9p 1s 9s E S W N P F", "C", {}, {"kokushi": "yakuman"}),
            ("2m 2m 2m 4p 4p 4p 6s 6s 6s 8s 8s 8s E", "E", {}, {"suuankou_tanki": "yakuman"}),
            ("2m 2m 2m 4p 4p 4p 6s 6s 6s 8s 8s E E", "E", {"tsumo": True}, {"suuankou": "yakuman"}),
            ("P P P F F F C C 2m 3m 4m 9s 9s", "C", {}, {"daisangen": "yakuman"}),
            ("E E E S S S W W N N 2m 3m 4m", "N", {}, {"shousuushii": "yakuman"}),
            ("E E E S S S W W W N N 2m 2m", "N", {}, {"daisuushii": "yakuman"}),
            ("E E E S S S P P P F F C C", "C", {}, {"tsuuiisou": "yakuman"}),
            ("1m 1m 1m 9m 9m 9m 1p 1p 1p 9s 9s 9p 9p", "9s", {}, {"chinroutou": "yakuman"}),
            ("2s 2s 3s 3s 4s 4s 6s 6s 6s 8s 8s F F", "F", {}, {"ryuuiisou": "yakuman"}),
            ("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 9s", "5s", {"tsumo": True, "tenhou": True, "seat": "E"}, {"tenhou": "yakuman"}),
            ("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 9s", "5s", {"tsumo": True, "chiihou": True}, {"chiihou": "yakuman"}),
        ]
        for hand, win, kw, want in cases:
            r = self.j(hand, win, **kw)
            self.assertEqual(names(r), want, hand)
            self.assertEqual(r["yakuman"], 1)
        r = self.j("2m 2m 2m 4p 4p 4p 6s 6s 6s 8s 8s N N", "N")                                       # ロンで完成した刻子は明刻：三暗刻＋対々和
        self.assertEqual(names(r), {"sanankou": 2, "toitoi": 2})
        r = self.j("2m", "2m", melds=[("ankan", "1m 1m 1m 1m"), ("minkan", "9p 9p 9p 9p"), ("kakan", "P P P P"), ("ankan", "3s 3s 3s 3s")])
        self.assertEqual(names(r), {"suukantsu": "yakuman"})
        r = self.j("P P P F F F C C 2m 3m E E E", "4m", tsumo=True, seat="E")                           # 三元牌の刻子 2 つ＋雀頭＝小三元
        self.assertEqual(names(r), {"menzen_tsumo": 1, "yakuhai_seat": 1, "yakuhai_round": 1, "yakuhai_haku": 1, "yakuhai_hatsu": 1,
                                    "sanankou": 2, "shousangen": 2, "honitsu": 3})

    def test_J6_ordinary_yaku(self):
        cases = [
            ("1m 2m 3m 1p 2p 3p 1s 2s 3s 7s 8s 9s 9m", "9m", {}, {"sanshoku": 2, "junchan": 3}, 40),
            ("1m 2m 3m 4m 5m 6m 7m 8m 9m 5m 5m E E", "E", {"seat": "E"}, {"yakuhai_seat": 1, "yakuhai_round": 1, "ittsu": 2, "honitsu": 3}, 40),
            ("1m 1m 1m 9m 9m 9m 1p 1p 1p E E C C", "C", {}, {"yakuhai_chun": 1, "sanankou": 2, "toitoi": 2, "honroutou": 2}, 60),
            ("1m 1m 9m 9m 1p 1p 9p 9p E E S S C", "C", {}, {"chiitoitsu": 2, "honroutou": 2}, 25),
            ("3m 3m 3m 3p 3p 3p 3s 3s 6s 7s 8s 5m 5m", "3s", {}, {"tanyao": 1, "sanshoku_doukou": 2}, 40),
            ("2m 3m 4m 2m 3m 4m 6p 7p 8p 5s 5s 7s 8s", "6s", {"riichi": True, "ippatsu": True}, {"riichi": 1, "ippatsu": 1, "tanyao": 1, "pinfu": 1, "iipeikou": 1}, 30),
            ("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 8s 9s 9s", "7s", {"double_riichi": True, "riichi": True, "houtei": True}, {"double_riichi": 2, "houtei": 1}, 40),
            ("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 8s 9s 9s", "7s", {"tsumo": True, "haitei": True}, {"menzen_tsumo": 1, "haitei": 1}, 30),
            ("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 8s 9s 9s", "7s", {"chankan": True}, {"chankan": 1}, 40),
        ]
        for hand, win, kw, want, fu in cases:
            r = self.j(hand, win, **kw)
            self.assertEqual((names(r), r["fu"]), (want, fu), hand)
        r = self.j("3p 4p 5p 9s", "9s", tsumo=True, rinshan=True, melds=[("ankan", "1m 1m 1m 1m"), ("minkan", "2p 2p 2p 2p"), ("kakan", "C C C C")])
        self.assertEqual((names(r), r["fu"]), ({"yakuhai_chun": 1, "rinshan": 1, "sankantsu": 2}, 80))  # 20＋暗槓 32＋明槓 8＋加槓（字牌）16＋単騎 2＋ツモ 2 ＝ 80
        r = self.j("3p 4p 5p 9s", "9s", tsumo=True, rinshan=True, melds=[("ankan", "1m 1m 1m 1m"), ("minkan", "2p 2p 2p 2p"), ("kakan", "C C C C")],
                   rs=variant("tenhou-4p-hanchan-red", {"scoring": {"fu": {"rinshan_tsumo_fu": 0}}}))
        self.assertEqual(r["fu"], 80)                                                                 # 嶺上開花のツモ符なし：78 → 80

    def test_J7_dora(self):
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p* 6s 7s 9s 9s", "5s", riichi=True, dora="8s 1m", ura="8s")
        self.assertEqual(names(r), {"riichi": 1, "pinfu": 1, "dora": 3, "ura_dora": 2, "aka_dora": 1})
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 9s", "5s", dora="8s", ura="8s")                # 立直していなければ裏ドラは数えない
        self.assertEqual(names(r), {"pinfu": 1, "dora": 2})
        rs3 = R.find(name="tenhou-3p")
        ts3 = TS.find(id=rs3["tileset"]["id"])
        self.assertEqual(J.next_kind(ts3, "1m"), "9m")                                                 # 三人打ち：萬子は 1 と 9 だけ
        self.assertEqual(J.next_kind(ts3, "9m"), "1m")
        self.assertEqual([J.next_kind(self.ts, k) for k in ("9p", "N", "C", "E")], ["1p", "E", "P", "S"])
        r = J.judge(rs3, ts3, ctx(ts3, "2p 3p 4p 6p 7p 8p 3s 4s 5s 6s 7s 9s 9s", "5s", dora="W", nuki="N N"))
        self.assertEqual(names(r), {"pinfu": 1, "dora": 2, "nuki_dora": 2})                             # 抜いた北はドラ（西表示）にも数える

    def test_J8_settings(self):
        hand = ("3p 4p 5p 6s 7s 2s 2s", "8s")
        open_melds = [("chi", "2m 3m 4m"), ("chi", "6m 7m 8m")]
        r = self.j(*hand, melds=open_melds, rs=variant("tenhou-4p-hanchan-red", {"flow": {"open_tanyao": False}}))
        self.assertEqual((r["ok"], r["reason"]), (False, "役が無い"))
        r = self.j(*hand, melds=open_melds, rs=variant("tenhou-4p-hanchan-red", {"yaku": {"overrides": {"tanyao": {"closed": 10, "open": 9}}}}))
        self.assertEqual(names(r), {"tanyao": 9})
        r = self.j(*hand, melds=open_melds, rs=variant("tenhou-4p-hanchan-red", {"scoring": {"fu": {"open_pinfu_fu": 20}}}))
        self.assertEqual(r["fu"], 20)
        pin = ("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 9s", "5s")
        r = self.j(*pin, tsumo=True, rs=variant("tenhou-4p-hanchan-red", {"scoring": {"fu": {"menzen_tsumo_pinfu": False}}}))
        self.assertEqual((names(r), r["fu"]), ({"menzen_tsumo": 1}, 30))
        r = self.j(*pin, honba=5, rs=variant("tenhou-4p-hanchan-red", {"scoring": {"shibari": {"from_honba": 5, "han": 2, "exclude_dora": True}}}))
        self.assertFalse(r["ok"])                                                                      # 5 本場から二翻縛り：平和のみは和了れない
        r = self.j(*pin, honba=4, rs=variant("tenhou-4p-hanchan-red", {"scoring": {"shibari": {"from_honba": 5, "han": 2, "exclude_dora": True}}}))
        self.assertTrue(r["ok"])
        r = self.j(*pin, renhou=True)
        self.assertEqual(names(r), {"pinfu": 1})                                                       # 人和は既定で不採用
        r = self.j(*pin, renhou=True, rs=variant("tenhou-4p-hanchan-red", {"yaku": {"overrides": {"renhou": "yakuman"}}}))
        self.assertEqual(names(r), {"renhou": "yakuman"})
        r = self.j(*pin, renhou=True, rs=variant("tenhou-4p-hanchan-red", {"yaku": {"overrides": {"renhou": 5}}}))
        self.assertEqual(names(r), {"pinfu": 1, "renhou": 5})
        seven = ("1m 1m 2m 2m 3m 3m 5p 5p 7p 7p 9s 9s E", "E")
        r = self.j(*seven, rs=variant("tenhou-4p-hanchan-red", {"scoring": {"fu": {"chiitoi": "50fu_1han"}}}))
        self.assertEqual((names(r), r["fu"]), ({"chiitoitsu": 1}, 50))
        r = self.j(*seven, rs=variant("tenhou-4p-hanchan-red", {"yaku": {"overrides": {"chiitoitsu": False}}}))
        self.assertEqual(r["reason"], "役が無い")
        hand_dw = ("1m 1m 1m 6m 7m 8m 3p 4p 5p 6s 7s E E", "8s")
        for v, fu in ((2, 40), (4, 50)):
            r = self.j(*hand_dw, riichi=True, seat="E", rs=variant("tenhou-4p-hanchan-red", {"scoring": {"fu": {"double_wind_pair": v}}}))
            self.assertEqual(r["fu"], fu, v)                                                           # 20＋門前ロン 10＋么九の暗刻 8＋連風 2/4 ＝ 40／42 → 40／50

    def test_J9_marks(self):
        rs = variant("tenhou-4p-hanchan-red", {"marks": {"red": {"effects": ["yaku"], "value": 2}}})
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p* 6s 8s 9s 9s", "7s", rs=rs)
        self.assertEqual(names(r), {"mark_yaku": 2})                                                   # 印の「役」だけで和了れる（ドラとは別）
        rs = variant("tenhou-4p-hanchan-red", {"marks": {"red": {"effects": ["almighty"], "when": {"state": "riichi", "how": "tsumo"}}}})
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 5m*", "9s", riichi=True, tsumo=False, rs=rs)
        self.assertFalse(r["ok"])                                                                      # 条件（立直してツモ）を満たさないので、ただの 5m
        r = self.j("2m 3m 4m 6m 7m 8m 3p 4p 5p 6s 7s 9s 9s", "5m*", riichi=True, tsumo=True, rs=rs)
        self.assertTrue(r["ok"])                                                                       # 何にでも使える：5s か 8s として和了
        self.assertIn("pinfu", names(r))

    def test_J10_small_hands(self):
        rs7 = R.find(name="nm-2p-7-mpsz")
        ts7 = TS.find(id=rs7["tileset"]["id"])
        r = J.judge(rs7, ts7, ctx(ts7, "2m 3m 4m 6p 7p 5s 5s", "8p", tsumo=True, seat="W"))
        self.assertEqual((names(r), r["fu"]), ({"menzen_tsumo": 1, "tanyao": 1, "pinfu": 1}, 20))
        r = J.judge(rs7, ts7, ctx(ts7, "2m 2m 3m 3m 4m 5s 5s", "4m", seat="W"))
        self.assertEqual(names(r), {"tanyao": 1, "pinfu": 1, "iipeikou": 1})
        rs10 = R.find(name="nm-2p-10-mpsz")
        ts10 = TS.find(id=rs10["tileset"]["id"])
        r = J.judge(rs10, ts10, ctx(ts10, "2m 2m 2m 4p 4p 4p 6s 6s 6s E", "E", seat="W"))
        self.assertEqual(names(r), {"sanankou": 2, "toitoi": 2})
        rs13 = R.find(name="nm-2p-13-mpsz")
        ts13 = TS.find(id=rs13["tileset"]["id"])
        r = J.judge(rs13, ts13, ctx(ts13, "1m 1m 2m 2m 3m 3m 5p 5p 7p 7p 9s 9s E", "E", seat="W"))
        self.assertFalse(r["ok"])                                                                      # 7・10・13 枚の既定は七対子なし


if __name__ == "__main__":
    unittest.main()
