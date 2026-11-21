"""ルールで選べる払い方・終わり方の確かめ（山を組んだ局と、点数表）。

出どころ（2026-11-18 取得）：
- 三人打ちのツモの払い：りゅ～く.net「三麻の点数表と点数計算」https://ryu-ku.net/07/9069 の点数表（ツモ損・千点加符・通常-丸取り・北家折半-丸取り）、
  Wikipedia「三人麻雀」https://ja.wikipedia.org/wiki/三人麻雀 の定義。
- 飛びの罰符・帰り東：Wikipedia「THEわれめDEポン」。
- 時間制限：健康マージャン公式競技規定 https://tojankyo.com/kenma-rule/ 「時間となった局が終わった時点でその半荘を終了する。」
- 和了止めの選択：マーチャオのルール https://mj-king.net/tempos/rule/8362 「オーラスの親があがってトップの場合、終了となります。」「2着・3着の場合は続行選択自由です。」
"""
import json
import unittest

from nmahjong import bots as B, dealer as D, gateway as GW, judge as J, record as REC, ruleset as R, scoring as S, tileset as TS, wall as W

from scripted import Table, kinds

T4 = "tenhou-4p-hanchan-red"
JUNK = "147m 258p 369s ESW P"
ST = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0}


def rule(base, **sets):
    return R.new_from(R.find(name=base), "t", {k.replace("__", "."): v for k, v in sets.items()})


def sc3(mode, **more):
    sc = dict(R.normalize(R.find(name="tenhou-3p"))["game_rules"]["scoring"], tsumo_loss=mode)
    sc.update(more)
    return sc


class TestThreePlayerTsumo(unittest.TestCase):
    """三人打ちのツモの払い（scoring.tsumo_loss）。表の値は「子の払い・親の払い」、親のツモは「オール」。"""

    # (符, 翻): (子の払い, 親の払い)
    CHILD = {
        "loss": {(30, 1): (300, 500), (30, 5): (2000, 4000)},
        "add_1000": {(30, 1): (1300, 1500), (30, 5): (3000, 5000)},
        "marudori": {(20, 2): (400, 900), (20, 3): (800, 1800), (20, 4): (1700, 3500), (25, 3): (1000, 2200), (25, 4): (2100, 4300),
                     (30, 1): (300, 700), (30, 2): (600, 1400), (30, 3): (1300, 2600), (30, 4): (2500, 5200),
                     (40, 1): (400, 900), (40, 2): (800, 1800), (40, 3): (1700, 3500), (50, 1): (500, 1100), (50, 2): (1000, 2200), (50, 3): (2100, 4300),
                     (60, 1): (600, 1400), (60, 2): (1300, 2600), (60, 3): (2500, 5200), (70, 1): (700, 1600), (70, 2): (1500, 3000),
                     (80, 1): (800, 1800), (80, 2): (1700, 3500), (90, 2): (1900, 3900), (100, 1): (1000, 2200), (100, 2): (2100, 4300),
                     (110, 1): (1200, 2400), (110, 2): (2300, 4800),
                     (30, 6): (4000, 8000), (30, 8): (5300, 10700), (30, 11): (8000, 16000), (30, 13): (10600, 21400)},
        "north_split": {(20, 2): (600, 900), (20, 3): (1000, 1700), (20, 4): (1900, 3300), (25, 3): (1200, 2000), (25, 4): (2400, 4000),
                        (30, 1): (400, 700), (30, 2): (700, 1300), (30, 3): (1500, 2500), (30, 4): (3000, 4900),
                        (40, 1): (600, 900), (40, 2): (1000, 1700), (40, 3): (1900, 3300), (50, 1): (600, 1000), (50, 2): (1200, 2000), (50, 3): (2400, 4000),
                        (60, 1): (700, 1300), (60, 2): (1500, 2500), (60, 3): (3000, 4900), (70, 1): (900, 1500), (70, 2): (1800, 2900),
                        (80, 1): (1000, 1700), (80, 2): (1900, 3300), (90, 1): (1200, 1900), (90, 2): (2200, 3700), (100, 1): (1200, 2000), (100, 2): (2400, 4000),
                        (110, 1): (1300, 2300), (110, 2): (2700, 4500),
                        (30, 5): (3000, 5000), (30, 6): (4500, 7500), (30, 8): (6000, 10000), (30, 11): (9000, 15000), (30, 13): (12000, 20000)},
    }
    # 親のツモ（丸取り・北家折半は同じ表）
    DEALER = {(20, 2): 1000, (20, 3): 2000, (20, 4): 3900, (25, 3): 2400, (25, 4): 4800, (30, 1): 800, (30, 2): 1500, (30, 3): 2900, (30, 4): 5800,
              (40, 1): 1000, (40, 2): 2000, (40, 3): 3900, (50, 1): 1200, (50, 2): 2400, (50, 3): 4800, (60, 1): 1500, (60, 2): 2900, (60, 3): 5800,
              (70, 1): 1700, (70, 2): 3400, (80, 1): 2000, (90, 1): 2200, (90, 2): 4400, (100, 1): 2400, (100, 2): 4800, (110, 1): 2700, (110, 2): 5300,
              (30, 5): 6000, (30, 6): 9000, (30, 8): 12000, (30, 11): 18000, (30, 13): 24000}

    def test_O1_child_tsumo_tables(self):
        """子のツモ：4 つの方式の点数表どおり。
        表のうち 3 か所（通常-丸取りの 90 符 1 翻「1000・2000」と満貫「2600・6400」、親の 80 符 2 翻「3800 オール」）は、
        合計がロンの点（2900・8000）を超える／同じ 7700 点の 40 符 3 翻「3900 オール」と合わないので、表の誤記とみて式の値（900・2000、2600・5400、3900）を採る。"""
        n = 0
        for mode, table in self.CHILD.items():
            for (fu, han), (child, dealer) in table.items():
                total, parts = S.total_points(fu, han, 0, False, True, 3, sc3(mode))
                self.assertEqual((parts[1], parts[0]), (child, dealer), (mode, fu, han))
                n += 1
        self.assertGreaterEqual(n, 60)
        self.assertEqual(S.total_points(90, 1, 0, False, True, 3, sc3("marudori"))[1], [2000, 900])
        self.assertEqual(S.total_points(30, 5, 0, False, True, 3, sc3("marudori"))[1], [5400, 2600])

    def test_O2_dealer_tsumo_tables(self):
        for mode in ("marudori", "north_split"):
            for (fu, han), each in self.DEALER.items():
                self.assertEqual(S.total_points(fu, han, 0, True, True, 3, sc3(mode))[1], [each, each], (mode, fu, han))
        self.assertEqual(S.total_points(80, 2, 0, True, True, 3, sc3("marudori"))[1], [3900, 3900])
        self.assertEqual(S.total_points(30, 1, 0, True, True, 3, sc3("loss"))[1], [500, 500])
        self.assertEqual(S.total_points(30, 1, 0, True, True, 3, sc3("add_1000"))[1], [1500, 1500])
        self.assertEqual(S.total_points(30, 5, 0, True, True, 3, sc3("add_1000"))[1], [5000, 5000])

    def test_O3_marudori_total_equals_ron(self):
        """丸取り：ツモの合計はロンの点と同じ（親のツモは 2 人で割って 100 点単位に切り上げる分だけ増えることがある）。
        none（ツモ損なし。方式の指定なし）は丸取りで払う。四人打ちには関係しない。"""
        for fu in (20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 110):
            for han in range(1, 14):
                ron = S.total_points(fu, han, 0, False, False, 3, sc3("marudori"))[0]
                self.assertEqual(S.total_points(fu, han, 0, False, True, 3, sc3("marudori"))[0], ron)
                dron = S.total_points(fu, han, 0, True, False, 3, sc3("marudori"))[0]
                self.assertIn(S.total_points(fu, han, 0, True, True, 3, sc3("marudori"))[0] - dron, (0, 100))
                for dealer in (False, True):
                    self.assertEqual(S.total_points(fu, han, 0, dealer, True, 3, sc3("none")), S.total_points(fu, han, 0, dealer, True, 3, sc3("marudori")))
        sc4 = R.normalize(R.find(name=T4))["game_rules"]["scoring"]
        self.assertEqual(sc4["tsumo_loss"], "none")
        self.assertEqual(S.total_points(30, 1, 0, False, True, 4, sc4)[1], [500, 300, 300])

    def test_O4_round_to_1000(self):
        """1000 点単位（scoring.round_to＝1000）：各自の払いを 1000 点に切り上げる。"""
        sc = sc3("loss", round_to=1000)
        self.assertEqual(S.total_points(30, 1, 0, False, False, 3, sc), (1000, [1000]))
        self.assertEqual(S.total_points(30, 3, 0, False, False, 3, sc), (4000, [4000]))          # 3900 → 4000
        self.assertEqual(S.total_points(30, 3, 0, True, False, 3, sc), (6000, [6000]))           # 5800 → 6000
        self.assertEqual(S.total_points(30, 3, 0, False, True, 3, sc), (3000, [2000, 1000]))     # 2000・1000
        self.assertEqual(S.total_points(30, 1, 0, False, True, 3, sc), (2000, [1000, 1000]))     # 500・300 → 1000・1000
        self.assertEqual(S.total_points(30, 5, 0, False, True, 3, sc), (6000, [4000, 2000]))


class TestMultipleWinners(unittest.TestCase):
    """複数和了のときの本場と供託（flow.kyotaku_to）。席 0（親）の 5p に席 2・席 3 がロン（どちらも 1300 点）。"""

    def play(self, rs, kyotaku):
        t = Table(rs)
        w = t.wall(0, {0: "123m 456m 678m 11s 5p 9s", 1: JUNK, 2: "46p 123s 456s 77s PPP", 3: "46p 789s 234m 88m FFF"}, draws="C")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 2: [("ron", None)], 3: [("ron", None)]}, state={"honba": 2, "kyotaku": kyotaku})
        return [x["deltas"] for x in r["wins"]]

    def test_O5_split(self):
        """split：本場は和了者それぞれが取り、供託は等分（割り切れない分は放銃者から近い和了者）。"""
        rs = rule(T4, game_rules__flow__kyotaku_to="split")
        self.assertEqual(D.unsupported(rs), [])
        self.assertEqual(self.play(rs, 2), [[-1900, 0, 2900, 0], [-1900, 0, 0, 2900]])
        self.assertEqual(self.play(rs, 3), [[-1900, 0, 3900, 0], [-1900, 0, 0, 2900]])
        self.assertEqual(self.play(rs, 0), [[-1900, 0, 1900, 0], [-1900, 0, 0, 1900]])

    def test_O6_kamicha(self):
        """kamicha（上家取り）：本場も供託も、放銃者から近い和了者だけ。"""
        self.assertEqual(self.play(R.find(name=T4), 2), [[-1900, 0, 3900, 0], [-1300, 0, 0, 1300]])


class TestTobiPenalty(unittest.TestCase):
    """飛びの罰符（end.tobi.penalty_points・penalty_to）。
    「持ち点が0未満になった時点で終了」「飛ばした人に対して10000点の罰符を支払う」「ノーテン罰符で飛んだ場合は、聴牌者に支払う（複数いる場合は頭跳ね）」"""

    def rs(self, to="tenpai_players", **more):
        return rule(T4, **{"end__tobi": {"enabled": True, "at": 0, "exact_zero_is_tobi": False, "penalty_points": 10000, "penalty_to": to}, **more})

    def test_O7_bust_by_ron(self):
        """席 0（持ち点 1000）が席 2 に 1300 点を放銃して飛ぶ → 席 2 にさらに 10000 点。対局はここで終わる。"""
        t = Table(self.rs())
        w = t.wall(0, {0: "123m 456m 678m 11s 5p 9s", 1: JUNK, 2: "46p 123s 456s 77s PPP", 3: JUNK.replace("P", "F")}, draws="C")
        st = dict(ST, scores=[1000, 33000, 33000, 33000])
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 2: [("ron", None)]}, state=st)
        self.assertEqual(r["wins"][0]["points"], 1300)
        self.assertEqual(r["wins"][0]["deltas"], [-11300, 0, 11300, 0])
        self.assertEqual(r["tobi_penalty"], [{"from": 0, "to": 2, "points": 10000}])
        self.assertEqual(r["scores"], [-10300, 33000, 44300, 33000])
        self.assertEqual(d.next_state(st, r, info, 0), (None, "飛び"))

    def test_O8_no_bust_no_penalty(self):
        """飛ばなければ罰符は無い（持ち点 1300 でちょうど 0 点。0 点は飛びではない）。"""
        t = Table(self.rs())
        w = t.wall(0, {0: "123m 456m 678m 11s 5p 9s", 1: JUNK, 2: "46p 123s 456s 77s PPP", 3: JUNK.replace("P", "F")}, draws="C")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 2: [("ron", None)]}, state=dict(ST, scores=[1300, 33000, 33000, 32700]))
        self.assertEqual(r["wins"][0]["deltas"], [-1300, 0, 1300, 0])
        self.assertNotIn("tobi_penalty", r)

    def test_O9_double_ron_goes_to_the_nearer_winner(self):
        """2 人に放銃して飛んだときは、放銃者から近い和了者（上家取り）へ。"""
        t = Table(self.rs())
        w = t.wall(0, {0: "123m 456m 678m 11s 5p 9s", 1: JUNK, 2: "46p 123s 456s 77s PPP", 3: "46p 789s 234m 88m FFF"}, draws="C")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 2: [("ron", None)], 3: [("ron", None)]}, state=dict(ST, scores=[2000, 33000, 33000, 32000]))
        self.assertEqual([x["deltas"] for x in r["wins"]], [[-11300, 0, 11300, 0], [-1300, 0, 0, 1300]])
        self.assertEqual(r["tobi_penalty"], [{"from": 0, "to": 2, "points": 10000}])

    def test_O10_bust_by_tsumo(self):
        """ツモで飛ばしたら、ツモった人へ。席 1 の 2 巡目のツモ（門前清自摸和＋役牌 40 符 2 翻：親 1300・子 700）で、持ち点 400 の席 3 が飛ぶ。"""
        t = Table(self.rs())
        w = t.wall(0, {0: JUNK, 1: "46p 123s 456s 77s PPP", 2: JUNK.replace("P", "F"), 3: "147m 268p 369s ESW C"}, draws="N 9m 9m 9m N 5p", dora="1m")
        r, info, rnd, d = t.play(w, {1: [("tsumo", None)]}, state=dict(ST, scores=[33000, 33000, 33600, 400]))
        self.assertEqual((r["wins"][0]["fu"], r["wins"][0]["han"]), (40, 2))
        self.assertEqual(r["wins"][0]["deltas"], [-1300, 12700, -700, -10700])
        self.assertEqual(r["tobi_penalty"], [{"from": 3, "to": 1, "points": 10000}])

    def draw(self, rs, scores):
        """荒牌流局。席 0（親）だけ聴牌：ほかの 3 人が 1000 点ずつ払う。"""
        t = Table(rs)
        per = {0: kinds("222m 333m 444m 666m 777m 888m"), 1: kinds("111m 999m 111p 999p 111s 999s"),
               2: kinds("EEE SSS WWW NNN PPP FF"), 3: kinds("222p 333p 444p 666p 777p 88p")}
        seq = [per[i % 4][i // 4] for i in range(136 - 14 - 52)]
        hands = {0: "2s 3s 4s 6s 7s 8s 4s 5s 6s 5m 5m 5p 5p", 1: "2s 2s 4s 6s 8s 8s 3s 3s 7s 7s 8p 8m C",
                 2: "2s 4s 6s 8s 3s 5s 7s 5m 8p 4m 2p C 9s", 3: "5p C C F F 9m 1m 1p 9p 1s E S W"}
        st = dict(ST, scores=scores)
        r, info, rnd, d = t.play(t.wall(0, hands, draws=" ".join(seq)), {}, state=st)
        return r, info, d, st

    def test_O11_bust_by_noten_penalty(self):
        """ノーテン罰符で飛んだら聴牌者へ（tenpai_players）。winner のルールでは、和了で飛ばしたときだけなので払わない。"""
        r, info, d, st = self.draw(self.rs(game_rules__nagashi_mangan={"enabled": False}), [33000, 33000, 500, 33500])
        self.assertEqual((r["draw"]["reason"], r["draw"]["tenpai"]), ("exhaustive", [True, False, False, False]))
        self.assertEqual(r["draw"]["deltas"], [13000, -1000, -11000, -1000])
        self.assertEqual(r["tobi_penalty"], [{"from": 2, "to": 0, "points": 10000}])
        self.assertEqual(d.next_state(st, r, info, 0), (None, "飛び"))
        r, info, d, st = self.draw(self.rs("winner", game_rules__nagashi_mangan={"enabled": False}), [33000, 33000, 500, 33500])
        self.assertEqual(r["draw"]["deltas"], [3000, -1000, -1000, -1000])
        self.assertNotIn("tobi_penalty", r)

    def test_O12_noten_penalty_does_not_bust(self):
        """on_noten_penalty＝false：ノーテン罰符の払いでは飛ばない（対局は続き、罰符も無い）。和了で 0 点を下回れば飛ぶ。"""
        rs = rule(T4, **{"end__tobi": {"enabled": True, "at": 0, "on_noten_penalty": False, "penalty_points": 10000, "penalty_to": "tenpai_players"},
                         "game_rules__nagashi_mangan": {"enabled": False}})
        r, info, d, st = self.draw(rs, [33000, 33000, 500, 33500])
        self.assertEqual(r["draw"]["deltas"], [3000, -1000, -1000, -1000])
        n, why = d.next_state(st, r, info, 0)
        self.assertEqual((n["oya"], n["honba"], n["scores"][2]), (0, 1, -500))


class TestNagashiVariants(unittest.TestCase):
    """流し満貫の扱い（nagashi_mangan.as）。席 1・席 2（どちらも子）が流し満貫。"""
    HANDS = {0: "2s 2s 4s 4s 6s 6s 8s 8s 3s 5s 7s 5m 5p", 1: "2s 3s 4s 6s 7s 8s 3s 5s 7s 5m 5p 8p 8m",
             2: "2s 4s 6s 8s 3s 5s 7s 5m 8p 4m 2p C 9s", 3: "5p C C F F 9m 1m 1p 9p 1s E S W"}
    TENPAI0 = {0: "2s 3s 4s 6s 7s 8s 4s 5s 6s 5m 5m 5p 5p", 1: "2s 2s 4s 6s 8s 8s 3s 3s 7s 7s 8p 8m C",
               2: "2s 4s 6s 8s 3s 5s 7s 5m 8p 4m 2p C 9s", 3: "5p C C F F 9m 1m 1p 9p 1s E S W"}

    def play(self, nm, hands=None, state=None, swap=False):
        t = Table(rule(T4, game_rules__nagashi_mangan=nm))
        per = {0: kinds("222m 333m 444m 666m 777m 888m"), 1: kinds("111m 999m 111p 999p 111s 999s"),
               2: kinds("EEE SSS WWW NNN PPP FF"), 3: kinds("222p 333p 444p 666p 777p 88p")}
        if swap:
            per[0], per[1] = per[1], per[0]                     # 席 0（親）と席 2 が流し満貫になる山
        seq = [per[i % 4][i // 4] for i in range(136 - 14 - 52)]
        st = dict(ST, scores=[25000] * 4, **(state or {}))
        r, info, rnd, d = t.play(t.wall(0, hands or self.HANDS, draws=" ".join(seq)), {}, state=st)
        self.assertEqual(r["draw"]["reason"], "nagashi_mangan")
        return r, info, d, st

    def test_O50_nagashi_with_additive_points(self):
        """足し算の点数のルール（東天紅は流し満貫が役満）：流し満貫の人は、役満の点（50）＋バンバン（2）を、残りの全員からそれぞれ受け取る。"""
        t = Table(rule(T4, game_rules__nagashi_mangan={"enabled": True, "as": "yakuman"}, game_rules__scoring__table="additive"))
        per = {0: kinds("222m 333m 444m 666m 777m 888m"), 1: kinds("111m 999m 111p 999p 111s 999s"),
               2: kinds("EEE SSS WWW NNN PPP FF"), 3: kinds("222p 333p 444p 666p 777p 88p")}
        seq = [per[i % 4][i // 4] for i in range(136 - 14 - 52)]
        r, info, rnd, d = t.play(t.wall(0, self.HANDS, draws=" ".join(seq)), {}, state=dict(ST, scores=[25000] * 4))
        self.assertEqual((r["draw"]["reason"], info["nagashi"]), ("nagashi_mangan", [1, 2]))
        self.assertEqual(r["draw"]["deltas"], [-104, 104, 104, -104])               # 席 1・席 2 が 52 点ずつを 3 人から（互いにも払う）

    def test_O13_draw_mangan(self):
        """draw_mangan：流局の扱いで、満貫のツモの額を払う（tenpai_settlement と同じ額）。本場と供託は動かない。"""
        for as_ in ("draw_mangan", "tenpai_settlement"):
            r, info, d, st = self.play({"enabled": True, "as": as_}, state={"honba": 2, "kyotaku": 1})
            self.assertEqual(r["draw"]["deltas"], [-8000, 6000, 6000, -4000])
            n, _ = d.next_state(st, r, info, 0)
            self.assertEqual((n["oya"], n["honba"], n["kyotaku"]), (1, 3, 1))

    def test_O14_with_noten_penalty(self):
        """noten_penalty＝true：満貫の払いに加えて、ノーテン罰符も払う。席 0（親）だけ聴牌 → 3 人から 1000 点ずつ。"""
        r, info, d, st = self.play({"enabled": True, "as": "draw_mangan", "noten_penalty": True}, hands=self.TENPAI0)
        self.assertEqual(r["draw"]["tenpai"], [True, False, False, False])
        self.assertEqual(r["draw"]["deltas"], [-8000 + 3000, 6000 - 1000, 6000 - 1000, -4000 - 1000])
        r, info, d, st = self.play({"enabled": True, "as": "draw_mangan", "noten_penalty": False}, hands=self.TENPAI0)
        self.assertEqual(r["draw"]["deltas"], [-8000, 6000, 6000, -4000])

    def test_O15_as_win(self):
        """win：和了の扱い。本場（2 本場 600）と供託（1 本）は、親から数えて最初の流し満貫の人（席 1）が取る。親が流し満貫でなければ親は流れ、本場は 0 に戻る。"""
        r, info, d, st = self.play({"enabled": True, "as": "win"}, state={"honba": 2, "kyotaku": 1})
        self.assertEqual(r["draw"]["deltas"], [-8000 - 200, 6000 + 600 + 1000, 6000 - 200, -4000 - 200])
        n, _ = d.next_state(st, r, info, 0)
        self.assertEqual((n["oya"], n["honba"], n["kyotaku"]), (1, 0, 0))
        # 親（席 0）が流し満貫：連荘
        r, info, d, st = self.play({"enabled": True, "as": "win"}, state={"honba": 2, "kyotaku": 1}, swap=True)
        self.assertEqual(info["nagashi"], [0, 2])
        self.assertEqual(r["draw"]["deltas"], [12000 + 600 + 1000 - 4000, -4000 - 200 - 2000, 8000 - 4000 - 200, -4000 - 200 - 2000])
        n, _ = d.next_state(st, r, info, 0)
        self.assertEqual((n["oya"], n["honba"], n["kyotaku"]), (0, 3, 0))

    def test_O16_as_yakuman(self):
        """yakuman：「流しは満貫ではなく、役満」（関西の三人打ち）。役満のツモの額を払う。"""
        r, info, d, st = self.play({"enabled": True, "as": "yakuman"})
        self.assertEqual(r["draw"]["deltas"], [-32000, 24000, 24000, -16000])

    def test_O17_dealer_does_not_stay(self):
        """renchan_if_dealer_tenpai＝false：流し満貫の局は、親が聴牌していても流れる。"""
        r, info, d, st = self.play({"enabled": True, "as": "draw_mangan", "renchan_if_dealer_tenpai": False}, hands=self.TENPAI0)
        n, _ = d.next_state(st, r, info, 0)
        self.assertEqual((n["oya"], n["honba"]), (1, 1))
        r, info, d, st = self.play({"enabled": True, "as": "draw_mangan"}, hands=self.TENPAI0)
        n, _ = d.next_state(st, r, info, 0)
        self.assertEqual((n["oya"], n["honba"]), (0, 1))


def last_round(rs, scores, kind, choose=None, dealer_tenpai=True, bakaze="S"):
    """最終局（南 4 局、親＝席 3）で親が和了（か聴牌で流局）したあと、終わるか続くか。"""
    d = D.Dealer(rs, TS.find(id=rs["tileset"]["id"]), decide=lambda *a: None, choose=choose)
    d._sticks = []
    st = {"bakaze": bakaze, "kyoku": 4, "honba": 0, "kyotaku": 0, "oya": 3, "scores": scores}
    info = {"kind": "win", "dealer_won": True, "winners": [3]} if kind == "win" else \
        {"kind": "draw", "reason": "exhaustive", "dealer_tenpai": dealer_tenpai, "any_tenpai": True, "nagashi": []}
    n, why = d.next_state(st, {"scores": scores}, info, 0)
    return why if n is None else "続く"


class TestStopOrContinue(unittest.TestCase):
    """和了止め・聴牌止めの選択（end.agari_yame・tenpai_yame の forced と others_may_continue）。"""
    TOP = [20000, 20000, 20000, 40000]
    SECOND = [40000, 15000, 15000, 30000]
    LAST = [40000, 25000, 25000, 10000]

    def test_O18_forced(self):
        """forced＝true：「オーラスの親があがってトップの場合、終了となります。」選択は聞かない。"""
        rs = R.find(name="marchao-4p")
        asked = []
        ch = lambda kind, seat, scores: asked.append(kind) or False       # noqa: E731
        self.assertEqual(last_round(rs, self.TOP, "win", ch), "和了止め")
        self.assertEqual(asked, [])

    def test_O19_choice_when_top(self):
        """forced＝false：トップの親が、止めるか続けるかを選ぶ。聞く相手がいなければ止める。"""
        rs = R.find(name="jantama-4p")
        self.assertEqual(D.unsupported(rs), [])
        seen = []
        self.assertEqual(last_round(rs, self.TOP, "win"), "和了止め")
        self.assertEqual(last_round(rs, self.TOP, "win", lambda k, s, sc: seen.append((k, s, sc)) or True), "和了止め")
        self.assertEqual(seen, [("agari_yame", 3, self.TOP)])
        self.assertEqual(last_round(rs, self.TOP, "win", lambda k, s, sc: False), "続く")
        self.assertEqual(last_round(rs, self.TOP, "draw"), "聴牌止め")
        self.assertEqual(last_round(rs, self.TOP, "draw", lambda k, s, sc: k != "tenpai_yame"), "続く")
        self.assertEqual(last_round(rs, self.SECOND, "win", lambda k, s, sc: True), "続く")      # トップでなければ聞かずに続く

    def test_O20_second_or_third_may_stop(self):
        """others_may_continue：「2着・3着の場合は続行選択自由です。」聞く相手がいなければ続く。ラスの親は続く。"""
        rs = R.find(name="marchao-4p")
        self.assertEqual(D.unsupported(rs), [])
        seen = []
        self.assertEqual(last_round(rs, self.SECOND, "win"), "続く")
        self.assertEqual(last_round(rs, self.SECOND, "win", lambda k, s, sc: seen.append(k) or True), "和了止め")
        self.assertEqual(seen, ["agari_yame_not_top"])
        self.assertEqual(last_round(rs, self.SECOND, "win", lambda k, s, sc: False), "続く")
        self.assertEqual(last_round(rs, self.LAST, "win", lambda k, s, sc: True), "続く")


class TestTimeLimit(unittest.TestCase):
    """時間制限（end.time_limit_sec）。「競技時間 団体戦60分…時間となった局が終わった時点でその半荘を終了する。」"""

    def test_O21_ends_after_the_round_in_progress(self):
        rs = R.find(name="kenko")
        self.assertEqual(D.unsupported(rs), [])
        ts = TS.find(id=rs["tileset"]["id"])
        now = [0.0]
        d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.BOTS["tsumogiri"], wants_events=False) for s in range(4)}, clock=lambda: now[0])
        played = []

        def walls(k, st):
            played.append(k)
            if k == 2:
                now[0] = 3600.0                                 # 3 局目の途中で 60 分になった
            return W.build(ts, f"time-{k}")
        rec = d.play(walls)
        self.assertEqual(played, [0, 1, 2])                     # その局は最後まで打ち、次の局は始めない
        self.assertEqual(len(rec["rounds"]), 3)
        self.assertEqual(rec["end"], "time_limit")
        self.assertEqual(d.log[-1], "終了：時間制限")

    def test_O22_not_reached(self):
        rs = R.find(name="kenko")
        ts = TS.find(id=rs["tileset"]["id"])
        d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.BOTS["tsumogiri"], wants_events=False) for s in range(4)}, clock=lambda: 0.0)
        rec = d.play(lambda k, st: W.build(ts, f"time-{k}"))
        self.assertEqual(rec["end"], "finished")
        self.assertGreaterEqual(len(rec["rounds"]), 8)


class TestWareme(unittest.TestCase):
    """われめ（flow.wareme）。「開門場所となったプレイヤーの和了に関する点棒授与は常に倍」「ノーテン罰符および積み棒は倍にならない」（THEわれめDEポン）。
    開門の家：最高位戦日本プロ麻雀協会 競技規定「「2,6,10」下家 「3,7,11」対家 「4,8,12」上家 「5,9」自家」。"""
    RS = None

    def rs(self):
        return rule(T4, game_rules__flow__wareme=True)

    def test_O23_seat_from_dice(self):
        rs = self.rs()
        self.assertEqual(D.unsupported(rs), [])
        d = D.Dealer(rs, TS.find(id=rs["tileset"]["id"]), decide=lambda *a: None)
        seat = lambda dice, oya=0: d.wareme_seat({"oya": oya, "dice": dice})      # noqa: E731
        self.assertEqual([seat([1, 4]), seat([4, 5])], [0, 0])                    # 5・9＝親
        self.assertEqual([seat([1, 1]), seat([3, 3]), seat([5, 5])], [1, 1, 1])   # 2・6・10＝下家
        self.assertEqual([seat([1, 2]), seat([3, 4]), seat([5, 6])], [2, 2, 2])   # 3・7・11＝対面
        self.assertEqual([seat([2, 2]), seat([4, 4]), seat([6, 6])], [3, 3, 3])   # 4・8・12＝上家
        self.assertEqual(seat([1, 1], oya=3), 0)

    def ron(self, wareme, **st):
        t = Table(self.rs())
        w = t.wall(0, {0: "123m 456m 678m 11s 5p 9s", 1: JUNK, 2: "46p 123s 456s 77s PPP", 3: JUNK.replace("P", "F")}, draws="C")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 2: [("ron", None)]}, state=dict(wareme=wareme, **st))
        self.assertEqual(r["wins"][0]["points"], 1300)
        return r["wins"][0]["deltas"]

    def test_O24_ron(self):
        """席 0 が席 2 に 1300 点を放銃。和了者が割れ目：2 倍。放銃者が割れ目：2 倍。どちらでもない：そのまま。本場と供託は倍にしない。"""
        self.assertEqual(self.ron(2), [-2600, 0, 2600, 0])
        self.assertEqual(self.ron(0), [-2600, 0, 2600, 0])
        self.assertEqual(self.ron(1), [-1300, 0, 1300, 0])
        self.assertEqual(self.ron(2, honba=2, kyotaku=1), [-2600 - 600, 0, 2600 + 600 + 1000, 0])

    def tsumo(self, wareme):
        t = Table(self.rs())
        w = t.wall(0, {0: JUNK, 1: "46p 123s 456s 77s PPP", 2: JUNK.replace("P", "F"), 3: "147m 268p 369s ESW C"}, draws="N 9m 9m 9m N 5p", dora="1m")
        r, info, rnd, d = t.play(w, {1: [("tsumo", None)]}, state={"wareme": wareme})
        self.assertEqual((r["wins"][0]["fu"], r["wins"][0]["han"]), (40, 2))
        return r["wins"][0]["deltas"]

    def test_O25_tsumo(self):
        """席 1 のツモ（親 1300・子 700）。和了者が割れ目：全員が 2 倍。払う人が割れ目：その人だけ 2 倍。"""
        self.assertEqual(self.tsumo(1), [-2600, 5400, -1400, -1400])
        self.assertEqual(self.tsumo(0), [-2600, 4000, -700, -700])
        self.assertEqual(self.tsumo(3), [-1300, 3400, -700, -1400])

    def test_O26_recorded_every_round(self):
        """対局の各局に、出目と割れ目の席が残る。できた対局は検証を通る。"""
        from nmahjong import record as REC
        rs = R.find(name="wareme-de-pon")
        self.assertEqual(D.unsupported(rs), [])
        ts = TS.find(id=rs["tileset"]["id"])
        d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.BOTS["simple"], wants_events=False) for s in range(4)})
        rec = d.play(lambda k, st: W.build(ts, f"wareme-{k}"))
        seen = set()
        for rnd in rec["rounds"]:
            st = rnd["state"]
            self.assertEqual(st["wareme"], (st["oya"] + sum(st["dice"]) - 1) % 4)
            seen.add((st["wareme"] - st["oya"]) % 4)
        self.assertGreaterEqual(len(seen), 2)
        self.assertEqual(REC.validate(rec, rs, ts, d.walls), [])


class TestOpenRiichiDealIn(unittest.TestCase):
    """オープン立直への放銃（flow.open_riichi の deal_in・exempt_prior_riichi・chaser_pays）。
    「オープンリーチに振り込んだ場合は役満払いとなる」「先制リーチ者は放銃しても役満払いにならない」（雀ナビ「オープンリーチ」）。"""
    WIN = "46p 123s 456s 77s PPP"                              # 5p 待ち
    TEN = "123m 456m 789m 11p 23p"                             # 聴牌（1p・4p 待ち）

    def test_O27_deal_in_is_yakuman(self):
        """席 1 がオープン立直。立直していない席 2 が放銃 → 役満の点（子 32000）。"""
        rs = R.find(name="open-riichi-house")
        self.assertEqual(D.unsupported(rs), [])
        t = Table(rs)
        w = t.wall(0, {0: JUNK, 1: self.WIN, 2: "147m 28p 369s ESW FF"}, draws="N C 5p", dora="1m", ura="1m")
        r, info, rnd, d = t.play(w, {1: [("open_riichi", "C"), ("ron", None)], 2: [("discard", "5p")]})
        win = r["wins"][0]
        self.assertEqual((win["who"], win["from"], win["yakuman"], win["points"]), (1, 2, 1, 32000))
        self.assertEqual(win["yaku"], [{"name": "open_riichi_deal_in", "yakuman": 1}])
        self.assertEqual(win["deltas"], [0, 32000, -32000, 0])

    def test_O28_prior_riichi_is_exempt(self):
        """先に立直していた席 0 が放銃 → 役満払いにならない（オープン立直 2 翻＋一発＋役牌＝40 符 4 翻の満貫 8000）。"""
        t = Table(R.find(name="open-riichi-house"))
        w = t.wall(0, {0: self.TEN, 1: self.WIN}, draws="N C 9s 9s 5p", dora="1m", ura="1m")
        r, info, rnd, d = t.play(w, {0: [("riichi", "N")], 1: [("open_riichi", "C"), ("ron", None)]})
        win = r["wins"][0]
        self.assertEqual((win["who"], win["from"], win.get("yakuman"), win["points"]), (1, 0, None, 8000))
        self.assertEqual([y["name"] for y in win["yaku"]], ["open_riichi", "ippatsu", "yakuhai_haku"])
        self.assertEqual(win["deltas"], [-9000, 9000, 0, 0])

    def chaser(self, rs):
        t = Table(rs)
        w = t.wall(0, {0: JUNK, 1: self.WIN, 2: self.TEN}, draws="N C 5p", dora="1m", ura="1m")
        r, info, rnd, d = t.play(w, {1: [("open_riichi", "C"), ("ron", None)], 2: [("riichi", "5p")]})
        return r["wins"][0]

    def test_O29_chaser(self):
        """あとから立直した席 2（追っかけ）の宣言牌：chaser_pays＝true なら役満払い、false なら普通の点。"""
        win = self.chaser(R.find(name="open-riichi-house"))
        self.assertEqual((win["from"], win["yakuman"], win["points"]), (2, 1, 32000))
        base = R.normalize(R.find(name="open-riichi-house"))["game_rules"]["flow"]["open_riichi"]
        win = self.chaser(rule("open-riichi-house", game_rules__flow__open_riichi=dict(base, chaser_pays=False)))
        self.assertEqual((win["from"], win.get("yakuman"), win["points"]), (2, None, 8000))

    def test_O30_tsumo_is_not_yakuman(self):
        """オープン立直のツモは普通の点。deal_in＝normal のルールでは放銃も普通の点。"""
        base = R.normalize(R.find(name="open-riichi-house"))["game_rules"]["flow"]["open_riichi"]
        t = Table(rule("open-riichi-house", game_rules__flow__open_riichi=dict(base, deal_in="normal")))
        w = t.wall(0, {0: JUNK, 1: self.WIN, 2: "147m 28p 369s ESW FF"}, draws="N C 5p", dora="1m", ura="1m")
        r, info, rnd, d = t.play(w, {1: [("open_riichi", "C"), ("ron", None)], 2: [("discard", "5p")]})
        self.assertEqual((r["wins"][0].get("yakuman"), r["wins"][0]["points"]), (None, 8000))
        t = Table(R.find(name="open-riichi-house"))
        w = t.wall(0, {0: JUNK, 1: self.WIN, 2: "147m 28p 369s ESW FF", 3: "258m 28p 369s ESW CC"}, draws="N C 9m 9m N 5p", dora="1m", ura="1m")
        r, info, rnd, d = t.play(w, {1: [("open_riichi", "C"), ("tsumo", None)]})
        self.assertEqual((r["wins"][0]["from"], r["wins"][0].get("yakuman")), (1, None))


TT = "toutenkou-3p"
J3 = "258p 147s 369s ESW P"


class TestAdditive(unittest.TestCase):
    """足し算の点数（scoring.table＝additive）と、東天紅の進め方（和了した人が次の親）。
    出どころ（2026-11-19 取得）：
    - LAG「東天紅麻雀のルールや始め方」https://lag.jp/toutenko-rule/ ：1 翻 1 点、バンバン 2 点、親 1 点、本場 1 点（親のみ）、役満 50 点、カラス 20 点・鳴きカラス 10 点、
      ノーテン罰符は場に 20 点（「場に 3,000 点」と同じ言い方で、ノーテンの人が合計を払い聴牌の人が受け取る）、和了した人が次の親、場は常に東。計算例（親・2 本場・立直・一通・平和・赤 1・ドラ 2・抜きドラ 3）：ツモ 16 点オール、ロン 15 点。
    - 麻雀グッズ研究所「東天紅とは」https://mahjong-item.jp/toutenko/ ：50 点持ち、ノーテン罰符は場に 10 点（2 人ノーテンなら 5 点ずつ）、カラス 30 点・鳴きカラス 20 点。
    - 麻雀プレス「三人麻雀 東天紅」https://www.mahjong-press.com/mahjong-else/three-player-mahjong-toutenkou/ ：計算例の合計 36 点（親・2 本場）をツモで 2 人から 36 点ずつ。
    - 麻雀ぽんと。「東天紅ルール解説」https://nagoya-mahjong-ponto.com/rule/ ：（基礎点（子 1・親 2）＋翻数＋ガリ＋本場）×4、10 点単位に切り上げ。
      例①子・ロン・5 翻・ガリ 3・0 本場＝40 点、例②親・ツモ・3 翻・ガリ 2・2 本場＝40 点×2 人。"""

    def sc(self, **ad):
        sc = dict(R.normalize(R.find(name=TT))["game_rules"]["scoring"])
        sc["additive"] = dict(sc["additive"], **ad)
        return sc

    def test_O31_formula(self):
        sc = self.sc()
        self.assertEqual(S.additive_points(11, 0, True, 2, None, sc)[0], 16)       # LAG の例：ツモ（立直 1・ツモ 1・平和 1・一通 2・赤 1・ドラ 2・抜き 3）
        self.assertEqual(S.additive_points(10, 0, True, 2, None, sc)[0], 15)       # 同じ手のロン（ツモの 1 点が無い）
        self.assertEqual(S.additive_points(31, 0, True, 2, None, sc)[0], 36)       # 麻雀プレスの例：役とドラ・ガリで 31、親 1、本場 2、バンバン 2
        self.assertEqual(S.additive_points(3, 0, False, 2, None, sc)[0], 5)        # 子の和了は本場を数えない（親のみ）
        self.assertEqual(S.additive_points(3, 0, False, 2, None, self.sc(honba_dealer_only=False))[0], 7)
        self.assertEqual(S.additive_points(0, 1, False, 0, None, sc)[0], 52)       # 役満 50 点＋バンバン
        self.assertEqual(S.additive_points(2, 0, False, 0, "menzen", sc)[0], 24)   # カラス 20 点
        self.assertEqual(S.additive_points(2, 0, False, 0, "open", sc)[0], 14)     # 鳴きカラス 10 点
        ponto = self.sc(base=1, dealer=1, multiplier=4, round_to=10, honba_dealer_only=False)
        self.assertEqual(S.additive_points(8, 0, False, 0, None, ponto)[0], 40)    # ぽんと。の例①：(1＋5＋3＋0)×4＝36 → 40
        self.assertEqual(S.additive_points(5, 0, True, 2, None, ponto)[0], 40)     # 例②：(2＋3＋2＋2)×4＝36 → 40（2 人から）
        with self.assertRaises(Exception):
            S.total_points(30, 1, 0, False, False, 3, sc)                          # 足し算のルールでは点数表を使わない

    def lag(self, script, draws):
        rs = rule(TT, game_rules__flow__ippatsu=False)
        t = Table(rs)
        w = t.wall(0, {0: "12340s6789s 22p 78p", 1: J3, 2: "369p 258s 147s WSE F"}, draws=draws, rinshan="1m 9m C", dora="1p", ura="P")
        r, info, rnd, d = t.play(w, script, state={"honba": 2})
        return r, info, rnd, d

    def test_O32_published_example(self):
        """LAG の計算例を山を組んで進める：親・2 本場、北・一萬・九萬を抜いて立直。ツモは 16 点オール、ロンは放銃者が 15 点。"""
        me = [("nuki", "N"), ("nuki", "1m"), ("nuki", "9m"), ("riichi", "C")]
        r, info, rnd, d = self.lag({0: me + [("tsumo", None)]}, "N 3p 3p 9p")
        win = r["wins"][0]
        self.assertEqual({y["name"]: y["han"] for y in win["yaku"]}, {"riichi": 1, "menzen_tsumo": 1, "pinfu": 1, "ittsu": 2, "dora": 2, "aka_dora": 1, "nuki_dora": 3})
        self.assertEqual(win["additive"], {"han": 11, "yakuman": 0, "base": 2, "dealer": 1, "honba": 2, "karasu": 0, "each": 16})
        self.assertEqual((win["points"], win["deltas"]), (32, [32, -16, -16]))                 # 自分の立直棒 1 点は出して戻る
        r, info, rnd, d = self.lag({0: me + [("ron", None)], 1: [("discard", "9p")]}, "N 9p")
        win = r["wins"][0]
        self.assertEqual((win["additive"]["each"], win["points"], win["deltas"]), (15, 15, [15, -15, 0]))

    def test_O33_karasu(self):
        """カラス：抜く牌を 1 枚も持たずに和了。門前 20 点、鳴くと 10 点。抜いていれば付かない。手の中に持っていても付かない。"""
        t = Table(R.find(name=TT))
        w = t.wall(0, {0: J3, 1: "234p 567p 234s 66s 78s", 2: "369p 258s 147s WSE F"}, draws="C 3p 3p C 6s", dora="E")
        r, info, rnd, d = t.play(w, {1: [("tsumo", None)]})
        self.assertEqual(r["wins"][0]["additive"], {"han": 3, "yakuman": 0, "base": 2, "dealer": 0, "honba": 0, "karasu": 20, "each": 25})   # ツモ・平和・断么九
        self.assertEqual(r["wins"][0]["deltas"], [-25, 50, -25])
        w = t.wall(0, {0: "258p 147s 369s ESW 5p", 1: "234p 567p 66s 78s FF 4p", 2: "369p 258s 147s WSE C"}, draws="F 9s", dora="E")
        r, info, rnd, d = t.play(w, {0: [("discard", "F")], 1: [("pon", "F"), ("discard", "4p"), ("ron", None)], 2: [("discard", "9s")]})
        self.assertEqual((r["wins"][0]["additive"]["karasu"], r["wins"][0]["additive"]["each"]), (10, 1 + 2 + 10))      # 發のみ、鳴きカラス
        w = t.wall(0, {0: J3, 1: "234p 567p 234s 66s 78s", 2: "369p 258s 147s WSE F"}, draws="C N 3p 3p 6s", rinshan="C", dora="E")
        r, info, rnd, d = t.play(w, {1: [("nuki", "N"), ("tsumo", None)]})
        self.assertEqual(r["wins"][0]["additive"]["karasu"], 0)

    def test_O34_noten_penalty(self):
        """ノーテン罰符は「場に 20 点」：ノーテンの人が合計 20 点を払い、聴牌の人が受け取る。全員聴牌・全員ノーテンは動かない。流局では本場は増えない。"""
        t = Table(R.find(name=TT))
        ten = "234p 567p 234s 66s 78s"
        w = t.wall(0, {0: ten, 1: J3, 2: "369p 258s 147s WSE F"}, dora="E")
        r, info, rnd, d = t.play(w, {})
        self.assertEqual((r["draw"]["tenpai"], r["draw"]["deltas"]), ([True, False, False], [20, -10, -10]))      # 聴牌 1 人：10 点ずつもらう
        nxt, _ = d.next_state(rnd["state"], r, info, 0)
        self.assertEqual((nxt["kyotaku"], nxt["oya"], nxt["honba"]), (0, 0, 0))                 # 親が聴牌なので親は続く。本場は増えない（親の和了の回数）
        w = t.wall(0, {0: ten, 1: "345p 678p 345s 77s 89s", 2: "369p 258s 147s WSE F"}, dora="E")
        r, info, rnd, d = t.play(w, {})
        self.assertEqual((r["draw"]["tenpai"], r["draw"]["deltas"]), ([True, True, False], [10, 10, -20]))        # ノーテン 1 人：20 点払う
        w = t.wall(0, {0: J3, 1: "369p 258s 147s WSE F", 2: "258p 147s 369s WSE C"}, dora="E")
        r, info, rnd, d = t.play(w, {})
        self.assertEqual(r["draw"]["deltas"], [0, 0, 0])

    def test_O35_winner_becomes_dealer(self):
        """和了した人が次の親。場と局は進まない。親が和了すれば本場が 1 つ増え、子が和了すれば 0 に戻る。"""
        t = Table(R.find(name=TT))
        w = t.wall(0, {0: J3, 1: "234p 567p 234s 66s 78s", 2: "369p 258s 147s WSE F"}, draws="C 3p 3p C 6s", dora="E")
        r, info, rnd, d = t.play(w, {1: [("tsumo", None)]}, state={"honba": 3})
        self.assertEqual(r["wins"][0]["additive"]["honba"], 0)                                  # 子の和了：本場は数えない
        nxt, _ = d.next_state(rnd["state"], r, info, 0)
        self.assertEqual((nxt["oya"], nxt["honba"], nxt["bakaze"], nxt["kyoku"]), (1, 0, "E", 1))
        w = t.wall(1, {1: "234p 567p 234s 66s 78s", 0: J3, 2: "369p 258s 147s WSE F"}, draws="C 3p 3p 6s", dora="E")
        r, info, rnd, d = t.play(w, {1: [("tsumo", None)]}, state={"oya": 1, "honba": 1})
        self.assertEqual((r["wins"][0]["additive"]["dealer"], r["wins"][0]["additive"]["honba"]), (1, 1))
        nxt, _ = d.next_state(rnd["state"], r, info, 0)
        self.assertEqual((nxt["oya"], nxt["honba"]), (1, 2))

    def test_O36_settings(self):
        """設定の決まり：足した項目は、書かなければこれまでの id のまま。既定と同じ値を書いても id は変わらない。"""
        base = R.find(name=T4)
        self.assertEqual(R.new_from(base, "t", {"game_rules.flow.next_dealer": "rotate"})["id"], base["id"])
        self.assertNotEqual(R.new_from(base, "t", {"game_rules.flow.next_dealer": "winner"})["id"], base["id"])
        a = R.normalize(R.new_from(R.find(name="tenhou-3p"), "t", {"game_rules.scoring.table": "additive"}))["game_rules"]["scoring"]["additive"]
        self.assertEqual(a, R.ADDITIVE_DEFAULTS)                                                # 書かなければ既定で埋まる
        for sets in ({"game_rules.scoring.additive": {"per_han": 1}},                           # table が additive でないのに additive がある
                     {"game_rules.scoring.table": "additive", "game_rules.scoring.additive": {"multiplier": 0}},
                     {"game_rules.scoring.table": "additive", "game_rules.scoring.additive": {"nazo": 1}},
                     {"game_rules.flow.next_dealer": "loser"},
                     {"length": "endless"}):                                                    # 区切りなしなのに終わり方が無い
            with self.assertRaises(Exception, msg=str(sets)):
                rs = R.new_from(R.find(name="jpml-official"), "t", sets)
                _, errs = R.validate(rs)
                if any(not e.startswith("欠落") for e in errs):
                    raise ValueError(errs)

    def test_O37_bundled_rule_plays_to_the_end(self):
        """同梱の東天紅を、同梱の打ち手同士で最後（誰かが飛ぶ）まで進め、できた対局が検証を通る。"""
        rs = R.find(name=TT)
        ts = TS.find(id=rs["tileset"]["id"])
        for g in range(3):
            d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.BOTS["simple"], wants_events=False) for s in range(3)})
            rec = d.play(lambda k, st: W.build(ts, f"o37-{g}-{k}"))
            self.assertEqual(REC.validate(rec, rs, ts, d.walls), [])
            self.assertEqual(d.log[-1], "終了：飛び")
            self.assertTrue(all(r["state"]["bakaze"] == "E" for r in rec["rounds"]))


SK, PH = "sakae-shibuya", "pocchi-house"
O4 = {1: "147m 258p 369s ESW F", 2: "258m 369p 147s WSE C", 3: "369m 147p 258s NNN C"}


class TestChips(unittest.TestCase):
    """祝儀（settlement.chips）と、白ポッチ・逆ポッチ。
    払い方の決まり（payer＝loser）：ロンは放銃者が、ツモは残りの全員が、それぞれ同じ枚数を払う。
    出どころ（2026-11-20 取得）：
    - さかえ：doramahjong https://doramahjong.org/freejyannsou/08/0040.html 「鳴き祝儀で赤一発裏」「トビぺナ1枚」、赤 5p は役扱い。
    - 白ポッチの店：note https://note.com/daisen/n/n66fdb6489afb 「金は祝儀2倍でドラ扱い」、白ポッチでの和了は祝儀 1 枚、逆ポッチは立直後のツモで
      オールマイティだが「打点と祝儀が支払い」。麻雀プレス https://www.mahjong-press.com/mahjong-strategy/white-tile-almighty/ 立直後に白ポッチをツモると和了、高め取り。"""

    def sakae(self, script, draws, hands0="234m 40m6m 234p 66s 78s", state=None, oya=0):
        t = Table(SK)
        w = t.wall(oya, {0: hands0, **O4}, draws=draws, dora="E", ura="5s")
        return t.play(w, script, state=state)

    def test_O38_win_chips(self):
        """赤 1 枚・一発・裏 3 枚で 5 枚。ロンは放銃者が 5 枚、ツモは 3 人が 5 枚ずつ。"""
        r, info, rnd, d = self.sakae({0: [("riichi", "F"), ("ron", None)], 1: [("discard", "6s")]}, "F 6s")
        win = r["wins"][0]
        self.assertEqual({y["name"]: y["han"] for y in win["yaku"] if y["name"] in ("ippatsu", "ura_dora", "aka_dora")}, {"ippatsu": 1, "ura_dora": 3, "aka_dora": 1})
        self.assertEqual(win["chips"], [5, -5, 0, 0])
        r, info, rnd, d = self.sakae({0: [("riichi", "F"), ("tsumo", None)]}, "F 1s 1s 1s 6s")
        self.assertEqual(r["wins"][0]["chips"], [15, -5, -5, -5])

    def test_O39_open_hand_keeps_chips(self):
        """鳴き祝儀：鳴いた手でも赤の祝儀が付く。赤 5p は 1 翻の役（鳴いていても和了できる）。"""
        t = Table(SK)
        w = t.wall(1, {0: "40p6p 234m 66s 78s FF 9m", 1: "147m 258p 369s ESW 1p", 2: "258m 369p 147s WSE C", 3: "369m 147p 258s NNN C"}, draws="F 9s", dora="E")
        r, info, rnd, d = t.play(w, {1: [("discard", "F"), ("discard", "9s")], 0: [("pon", "F"), ("discard", "9m"), ("ron", None)]}, state={"oya": 1})
        win = r["wins"][0]
        self.assertIn({"name": "mark_yaku", "han": 1}, win["yaku"])
        self.assertEqual(win["chips"], [1, -1, 0, 0])

    def test_O40_tobi_chip_and_total(self):
        """飛びの祝儀：飛んだ人が、飛ばした人に 1 枚。対局の最後の祝儀は、各和了の祝儀の合計。"""
        rs = rule(SK, end__tobi={"enabled": True, "at": 2000})
        t = Table(rs)
        w = t.wall(0, {0: "234m 40m6m 234p 66s 78s", **O4}, draws="F 6s", dora="E", ura="5s")
        r, info, rnd, d = t.play(w, {0: [("riichi", "F"), ("ron", None)], 1: [("discard", "6s")]}, state={"dice": [1, 2]})
        self.assertEqual(r["tobi_chips"], [{"from": 1, "to": 0, "chips": 1}])
        self.assertEqual(r["wins"][0]["chips"], [6, -6, 0, 0])
        rec = d.rc.finish(end="tobi")
        self.assertEqual(rec["final"]["chips"], [6, -6, 0, 0])
        bad = json.loads(json.dumps(rec))
        bad["rounds"][0]["result"]["wins"][0]["chips"] = [5, -5, 0, 0]              # 枚数を書き換えた対局は検証が断る
        bad["id"] = REC.compute_id(bad)
        with self.assertRaises(Exception):
            REC.validate(bad, rs, t.ts, d.walls)

    def pocchi(self, draw):
        t = Table(PH)
        w = t.wall(0, {0: "234m 4m Gm 6m 234p 66s 78s", **O4}, draws="F 1s 1s 1s 1p 2s 2s 2s " + draw, dora="E", ura="S")
        r, info, rnd, d = t.play(w, {0: [("riichi", "F"), ("discard", "1p"), ("tsumo", None)]})
        return r, rnd, t

    def test_O41_pocchi(self):
        """白ポッチ：立直のあとにツモると、何の牌としても和了できる（高い方：6s として断么九が付く）。金は祝儀 2 枚、白ポッチの和了は 1 枚。"""
        r, rnd, t = self.pocchi("Q")
        win = r["wins"][0]
        self.assertEqual(t.ts["tiles"][win["tile"]].get("mark"), "pocchi")
        self.assertIn({"name": "tanyao", "han": 1}, win["yaku"])
        self.assertEqual((win["points"], win["deltas"], win["chips"]), (18000, [18000, -6000, -6000, -6000], [9, -3, -3, -3]))
        self.assertEqual(len(rnd["events"]), 21)                                    # 白ポッチを引いた 3 巡目で和了している

    def test_O42_reverse_pocchi(self):
        """逆ポッチ：和了は成立するが、点と祝儀は和了者が払う。"""
        r, rnd, t = self.pocchi("R")
        win = r["wins"][0]
        self.assertTrue(win["reverse"])
        self.assertEqual((win["points"], win["deltas"], win["chips"]), (18000, [-18000, 6000, 6000, 6000], [-6, 2, 2, 2]))
        self.assertEqual(r["scores"], [7000, 31000, 31000, 31000])

    def test_O43_pocchi_is_plain_tile_otherwise(self):
        """白ポッチは、手の内に持っているだけなら普通の白。印のない白を引いても和了にならない（立直していなければ引いても和了にならない）。"""
        r, rnd, t = self.pocchi("P")
        self.assertEqual(t.ts["tiles"][r["wins"][0]["tile"]]["kind"], "9s")       # 3 巡目の白では和了にならず、あとで 9s をツモった
        t = Table(PH)
        w = t.wall(0, {0: "234m 456m 234p 66s Q P", **O4}, draws="F 1s 1s 1s P", dora="E", ura="S")
        r, info, rnd, d = t.play(w, {0: [("riichi", "F"), ("tsumo", None)]})
        win = r["wins"][0]
        self.assertIn({"name": "yakuhai_haku", "han": 1}, win["yaku"])               # 白の暗刻として数える
        self.assertEqual(win["chips"], [0, 0, 0, 0])                                  # 白ポッチで和了していないので、白ポッチの祝儀は付かない
        w = t.wall(0, {0: "234m 4m Gm 6m 234p 66s 78s", **O4}, draws="F 1s 1s 1s Q 9s", dora="E", ura="S")
        r, info, rnd, d = t.play(w, {0: [("discard", "F"), ("tsumo", None)], 1: [("discard", "1s")]})
        self.assertEqual(t.ts["tiles"][r["wins"][0]["tile"]]["kind"], "9s") if r["wins"] else self.assertIsNotNone(r["draw"])

    def test_O44_chip_rules_not_followed_are_reported(self):
        """和了と飛び以外の祝儀（カン・抜き・鳴き・焼き鳥）は数えない。そういう規則のあるルールは、指定しないかぎり始めない。"""
        rs = rule("mleague", settlement__chips=[{"on": "kan", "per": "event", "count": 1, "payer": "all"}])
        self.assertTrue(D.unsupported(rs))
        self.assertEqual([r["name"] for r in R.bundled() if D.unsupported(r)], [])


KS = "kansai-3p"
K3 = {1: "258p 147s 369s ESW P", 2: "369p 258s 147s WSE F"}


class TestKansai(unittest.TestCase):
    """関西の三人打ちの決まり：完全先付け、小車輪・大車輪、子のツモの払いの表。裏ドラ表示牌が白ポッチのとき。
    出どころ（2026-11-20 取得）：
    - 「関西サンマのルール」https://ameblo.jp/kansai3mj/entry-12100946684.html ：
      「喰いタン、後付け、片和了なし（完全先付け）」「役牌絡みの雀頭待ちをダマでは出あがれないし、役牌バックの仕掛けも不可能」
      「仕掛けの際、役のない和了牌が存在するだけで、役なし聴牌と同じ扱いになる」。
      ツモ損なし（丸取り）：子の満貫ツモ 5000-3000、跳満 8000-4000、倍満 10000-6000、三倍満 16000-8000、役満 20000-12000、親のツモはロンの半分ずつ。
      大車輪＝清一色七対子（役満）、小車輪＝混一色七対子（6 翻が普通）、三連刻 2 翻、三風 2 翻、積み棒 1000 点、数え役満 14 翻。
    - Wikipedia「三人麻雀」https://ja.wikipedia.org/wiki/三人麻雀 ：小車輪は 6 翻、混一色と七対子の複合形、色の制約なし。大車輪は役満、清一色と七対子の複合形、色の制約なし。
    - 麻雀プレス「白ポッチ」https://www.mahjong-press.com/mahjong-strategy/white-tile-almighty/ ：裏ドラ表示牌が白ポッチのときは、好きな牌を裏ドラにできる。"""

    def test_O45_wheels(self):
        """小車輪（混一色の七対子）は 6 翻で、七対子・混一色とは重ねない。大車輪は、関西では清一色の七対子ならどの並びでも役満。"""
        t = Table(KS)
        w = t.wall(0, {0: "1133557799p EE S", **K3}, draws="C 2s 2s S", dora="1s")
        r, info, rnd, d = t.play(w, {0: [("discard", "C"), ("tsumo", None)]})
        self.assertEqual(r["wins"][0]["yaku"], [{"name": "menzen_tsumo", "han": 1}, {"name": "shousharin", "han": 6}, {"name": "aka_dora", "han": 2}])   # 五筒は全部赤
        w = t.wall(0, {0: "1122334466779p", 1: "258p 147s 369s ESW P", 2: "58p 258s 147s WSE F C"}, draws="C 2s 2s 9p", dora="1s")
        r, info, rnd, d = t.play(w, {0: [("discard", "C"), ("tsumo", None)]})
        self.assertEqual(r["wins"][0]["yaku"], [{"name": "daisharin", "yakuman": 1}])
        ts = TS.find(name="mpsz")
        rs = rule("tenhou-4p-hanchan-red", game_rules__yaku__overrides={"daisharin": "yakuman", "shousharin": 6})   # 既定の大車輪は 2〜8 の並びだけ
        hand = lambda text: [next(i for i, x in enumerate(ts["tiles"]) if x["kind"] == k and x.get("mark") is None and i not in used and not used.add(i)) for k in kinds(text)]   # noqa: E731
        used = set()
        h = hand("11223344667799p")
        ctx = {"hand": h, "tile": h[-1], "melds": [], "tsumo": False, "seat_wind": "S", "round_wind": "E", "riichi": False, "dora_indicators": [], "ura_indicators": []}
        self.assertEqual([y["name"] for y in J.judge(rs, ts, ctx)["yaku"]], ["chiitoitsu", "chinitsu"])
        used = set()
        h = hand("22334455667788p")
        ctx = dict(ctx, hand=h, tile=h[-1])
        self.assertEqual(J.judge(rs, ts, ctx)["yaku"], [{"name": "daisharin", "yakuman": 1}])

    def test_O46_kanzen_sakizuke(self):
        """完全先付け：役の付かない待ちが 1 つでもあれば、役の付く牌でも和了できない。待ちがその牌だけなら和了できる。立直すればどの待ちにも役がある。門前のツモは和了できる。"""
        t = Table(KS)
        # 鳴いた手：444p5p ＋ 777p。5p は対々和になるが、3p・6p の待ちには役が無い → 5p でもロンできない
        hands = {0: "444p 5p 777p 99m 99s E W", 1: "258p 147s 369s S P 9m N", 2: "369p 258s 147s WS F C"}
        script = {1: [("discard", "9m"), ("discard", "9s"), ("discard", "5p")], 0: [("pon", "9m"), ("discard", "E"), ("pon", "9s"), ("discard", "W"), ("ron", None)]}
        w = t.wall(1, hands, draws="C 2s 5p 5p", dora="3s")
        r, info, rnd, d = t.play(w, script, state={"oya": 1})
        self.assertEqual(r["wins"], [])
        loose = rule(KS, game_rules__flow__atozuke="allowed")                # 後付けありなら、同じ局で 5p をロンできる（対々和）
        t2 = Table(loose)
        r, info, rnd, d = t2.play(t2.wall(1, hands, draws="C 2s 5p 5p", dora="3s"), script, state={"oya": 1})
        self.assertEqual([y["name"] for y in r["wins"][0]["yaku"]], ["toitoi", "aka_dora"])   # 五筒・五索は全部赤
        # 待ちが 5p の単騎だけ（222p ＋ 888s ＋ 5p）なら、完全先付けでも和了できる
        hands2 = {**hands, 0: "222p 5p 888s 99m 99s E W"}
        r, info, rnd, d = t.play(t.wall(1, hands2, draws="C 2s 5p 5p", dora="3s"), script, state={"oya": 1})
        self.assertEqual([y["name"] for y in r["wins"][0]["yaku"]], ["toitoi", "aka_dora"])   # 五筒・五索は全部赤
        # 門前：白と 9s のシャンポン。白は役になるが 9s には役が無い → ダマではロンできない。立直していればロンできる。ツモは和了できる
        hands3 = {0: "234p 456p 789p 99s PP", 1: "258p 147s 36s ESW P 1s", 2: "369p 258s 147s WSE F"}
        w = t.wall(0, hands3, draws="C P 2s 2s", dora="3s")
        r, info, rnd, d = t.play(w, {0: [("discard", "C"), ("ron", None)], 1: [("discard", "P")]})
        self.assertEqual(r["wins"], [])
        r, info, rnd, d = t.play(t.wall(0, hands3, draws="C P 2s 2s", dora="3s", ura="3s"), {0: [("riichi", "C"), ("ron", None)], 1: [("discard", "P")]})
        self.assertIn("yakuhai_haku", [y["name"] for y in r["wins"][0]["yaku"]])
        r, info, rnd, d = t.play(t.wall(0, hands3, draws="C 2s 2s 9s", dora="3s"), {0: [("discard", "C"), ("tsumo", None)]})
        self.assertIn("menzen_tsumo", [y["name"] for y in r["wins"][0]["yaku"]])

    def test_O47_tsumo_table(self):
        """関西の丸取り：子のツモの払いは出典の表、親のツモはロンの半分ずつ。ロンは 1000 点単位に切り上げ。"""
        sc = R.normalize(R.find(name=KS))["game_rules"]["scoring"]
        for name, fu, han, ym, ron, pay in (("満貫", 30, 5, 0, 8000, [5000, 3000]), ("跳満", 30, 6, 0, 12000, [8000, 4000]), ("倍満", 30, 8, 0, 16000, [10000, 6000]),
                                             ("三倍満", 30, 11, 0, 24000, [16000, 8000]), ("役満", 0, 0, 1, 32000, [20000, 12000])):
            self.assertEqual(S.total_points(fu, han, ym, False, False, 3, sc)[0], ron, name)
            self.assertEqual(S.total_points(fu, han, ym, False, True, 3, sc), (ron, pay), name)        # 子のツモ：[親の払い, 子の払い]。合計はロンと同じ
            half = S.total_points(fu, han, ym, True, False, 3, sc)[0] // 2
            self.assertEqual(S.total_points(fu, han, ym, True, True, 3, sc)[1], [half, half], name)   # 親のツモ：ロンの半分ずつ
        self.assertEqual(S.total_points(40, 1, 0, False, False, 3, sc)[0], 2000)                       # 立直のみ 1300 は 2000
        self.assertEqual(sc["honba_points"], 1000)

    def test_O48_ura_indicator_pocchi(self):
        """裏ドラ表示牌が白ポッチ（as_ura_indicator＝choose_any）なら、好きな牌を裏ドラにできる＝手の中でいちばん多い牌種の枚数が裏ドラ。"""
        rs = rule(PH, game_rules__marks={"red": {"effects": ["dora"]}, "gold": {"effects": ["dora"]},
                                         "pocchi": {"effects": ["almighty"], "when": {"state": "riichi", "how": "tsumo"}, "as_ura_indicator": "choose_any"},
                                         "reverse_pocchi": {"effects": ["almighty", "reverse"], "when": {"state": "riichi", "how": "tsumo"}}})
        t = Table(rs)
        w = t.wall(0, {0: "234m 456m 234p 666s 7s", **O4}, draws="F 7s", dora="E", ura="Q")
        r, info, rnd, d = t.play(w, {0: [("riichi", "F"), ("ron", None)], 1: [("discard", "7s")]})
        self.assertIn({"name": "ura_dora", "han": 3}, r["wins"][0]["yaku"])                           # 6s が 3 枚
        t = Table(PH)                                                                                # 設定が無ければ、白ポッチの次の牌（發）が裏ドラ
        w = t.wall(0, {0: "234m 456m 234p 666s 7s", **O4}, draws="F 7s", dora="E", ura="Q")
        r, info, rnd, d = t.play(w, {0: [("riichi", "F"), ("ron", None)], 1: [("discard", "7s")]})
        self.assertNotIn("ura_dora", [y["name"] for y in r["wins"][0]["yaku"]])

    def test_O49_settings(self):
        """足した項目（子のツモの表、大車輪の形）は、書かなければこれまでの id のまま。先付け（forbidden）は決め方の出典が無いので、進行役は従えない設定として知らせる。"""
        b = R.find(name="tenhou-3p")
        self.assertEqual(R.new_from(b, "t", {"game_rules.yaku.wheel": "2to8"})["id"], b["id"])
        self.assertNotEqual(R.new_from(b, "t", {"game_rules.scoring.tsumo_table": {"8000": [5000, 3000]}})["id"], b["id"])
        for sets in ({"game_rules.yaku.wheel": "nazo"}, {"game_rules.scoring.tsumo_table": {"8000": [5000]}}):
            with self.assertRaises(Exception, msg=str(sets)):
                _, errs = R.validate(R.new_from(b, "t", sets))
                if any(not e.startswith("欠落") for e in errs):
                    raise ValueError(errs)
        self.assertTrue(D.unsupported(rule("mleague", game_rules__flow__atozuke="forbidden")))
        self.assertEqual([r["name"] for r in R.bundled() if D.unsupported(r)], [])

    TRIPLE = {0: "123m 456m 678m 11s 5p 9s", 1: "46p 123p 789p 22s 999m", 2: "46p 123s 456s 77s PPP", 3: "46p 789s 234m 88m FFF"}

    def triple(self, name):
        t = Table(name)
        r, info, rnd, d = t.play(t.wall(0, self.TRIPLE, draws="C"), {0: [("discard", "5p")], 1: [("ron", None)], 2: [("ron", None)], 3: [("ron", None)]})
        return r

    def test_O51_triple_ron(self):
        """3 人が同じ牌でロン。雀魂：「二家和・三家和(ダブロン・トリロン)あり」＝3 人とも和了、流局にしない（Wikipedia 雀魂）。
        さかえ渋谷：「途中流局は三家和(トリロン)のみあり」「ダブロン有、トリロンは三家和」＝流局（雀荘巡りの記事、雀荘紹介）。"""
        r = self.triple("jantama-4p")
        self.assertIsNone(r["draw"])
        self.assertEqual(sorted(w["who"] for w in r["wins"]), [1, 2, 3])
        self.assertEqual(sum(r["scores"]), 100000)
        self.assertLess(r["scores"][0], 25000)
        self.assertTrue(all(x > 25000 for x in r["scores"][1:]))
        r = self.triple("sakae-shibuya")
        self.assertEqual((r["draw"]["reason"], r["wins"], r["scores"]), ("three_ron", [], [25000] * 4))
        for name, want in (("jantama-4p", (False, "allow")), ("jantama-4p-tonpu", (False, "allow")), ("sakae-shibuya", (True, "draw"))):
            fl = R.normalize(R.find(name=name))["game_rules"]["flow"]
            self.assertEqual((fl["ryukyoku"]["three_ron"], fl["triple_ron"]), want, name)
        self.assertFalse(R.normalize(R.find(name="sakae-shibuya"))["game_rules"]["flow"]["ryukyoku"]["four_riichi"])   # 四人立直は続行

    def test_O52_tsumo_no_loss_shops(self):
        """マーチャオ三人：「点数はツモ損なし。（子のハネ満ツモ 4000・8000）」＝丸取り（北家の分の折半なら 4500・7500）。
        ZOO 三人：出典は「ツモ損なし」だけで額が無い。同じ書き方のマーチャオの例に合わせて丸取りにしてある。"""
        for name in ("marchao-3p", "zoo-3p"):
            sc = R.normalize(R.find(name=name))["game_rules"]["scoring"]
            self.assertEqual(sc["tsumo_loss"], "marudori", name)
            self.assertEqual(S.total_points(30, 6, 0, False, True, 3, sc), (12000, [8000, 4000]), name)   # [親の払い, 子の払い]
            self.assertNotIn("game_rules.scoring.tsumo_loss", R.find(name=name).get("unknown", []))
        self.assertEqual(S.total_points(30, 6, 0, False, True, 3, sc3("north_split"))[1], [7500, 4500])

    def test_O53_single_double_yakuman(self):
        """M リーグ：「役満1種での二倍役満は無し」「純粋な役満の複合は認められる」。連盟公式：「四暗刻単騎・大四喜・国士無双13門待ち・九蓮宝燈9門待ち はダブル役満扱いにならない」。
        雀魂：この 4 つは二倍。"""
        for name, single in (("mleague", False), ("jpml-official", False), ("jantama-4p", True)):
            g = R.normalize(R.find(name=name))["game_rules"]
            ov = g["yaku"]["overrides"]
            for y in ("suuankou_tanki", "kokushi13", "junsei_chuuren", "daisuushii"):
                self.assertEqual(ov.get(y) == "yakuman:2", single, (name, y))
            self.assertEqual(g["scoring"]["limits"]["max_multiple"], 6, name)                          # 役満どうしの複合はあり
            self.assertNotIn("game_rules.yaku.overrides", R.find(name=name).get("unknown", []))

    def test_O54_classic_and_wrc(self):
        """最高位戦 Classic（最高位戦のルールのページ）：「順位点は、1位＋12P、2位＋4P、3位△4P、4位△12P」「ドラは最初の一種類に限る（カンドラ、裏ドラなし）」
        「リーチ一発なし」「ノーテン罰符なし」、連荘は親の和了だけ、切り上げ満貫なし、喰い替え可、立直後の暗槓不可、チョンボ △16P。
        連盟 WRC：途中流局なし、国士無双は暗槓でも和了できる。"""
        n = R.normalize(R.find(name="saikouisen-classic")); g = n["game_rules"]
        self.assertEqual(n["settlement"]["uma"], [12, 4, -4, -12])
        self.assertEqual((g["dora"]["ura"], g["dora"]["kan"], g["dora"]["kan_ura"], g["flow"]["ippatsu"]), (False, False, False, False))
        self.assertEqual((g["flow"]["renchan"]["dealer_win"], g["flow"]["renchan"]["dealer_tenpai"]), (True, False))
        self.assertEqual((g["scoring"]["noten_penalty"], g["scoring"]["honba_points"], g["scoring"]["mangan_round_up"]), (0, 300, False))
        self.assertEqual((g["flow"]["kuikae"], g["flow"]["riichi"]["ankan_after"], g["penalties"]["chombo"]["value"]), ("allowed", "none", 16))
        self.assertEqual(S.total_points(30, 4, 0, False, False, 4, g["scoring"])[0], 7700)
        t = Table("saikouisen-classic")                                                              # 親がノーテンで流局：罰符なし、親は流れる
        r, info, rnd, d = t.play(t.wall(0, {0: "147m 258p 369s ESW F", 1: "123m 456m 789m 11p 23p"}), {})
        self.assertEqual((r["draw"]["reason"], r["scores"]), ("exhaustive", [30000] * 4))
        nx, why = d.next_state({"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [30000] * 4}, r, info, 0)
        self.assertEqual(nx["oya"], 1)
        for name in ("jpml-wrc", "jpml-wrc-r"):
            fl = R.normalize(R.find(name=name))["game_rules"]["flow"]
            self.assertTrue(fl["kokushi_ankan_chankan"], name)
            self.assertEqual(set(fl["ryukyoku"].values()), {False}, name)

    def test_O55_sources_reread(self):
        """雀魂：「流局によって終局となった場合、供託はトップ取り。」。関西サンマ：「七対子四枚使いあり」。
        東天紅：「ドラは9枚目をめくる(抜きドラ12枚+槓用の4枚)」＝王牌 18 枚、補充 16 枚、9 幢目がドラ表示牌。天鳳三麻：「順位ウマ +20, 0, -20」。"""
        for name in ("jantama-4p", "jantama-4p-tonpu"):
            self.assertEqual(R.normalize(R.find(name=name))["game_rules"]["flow"]["riichi"]["stick_at_end"], "to_first", name)
        self.assertTrue(R.normalize(R.find(name="kansai-3p"))["game_rules"]["yaku"]["chiitoi_four_of_kind"])
        n = R.normalize(R.find(name="toutenkou-3p")); w = n["wall_rules"]
        self.assertEqual((w["dead_wall"], w["dora_indicator"], w["ura_indicator"], len(w["rinshan"])), (18, [0], [1], 16))
        self.assertEqual((n["game_rules"]["dora"]["kan"], n["game_rules"]["dora"]["kan_ura"]), (False, False))
        t = Table("toutenkou-3p")                                                                    # 暗槓：補充は王牌の末尾から。カンドラはめくらない
        wl = t.wall(0, {0: "2222p 345p 678s 99s 4s", 1: "369p 258s 147s WSE F", 2: "147p 369s 258s PPP C"}, draws="5s", rinshan="6s", dora="1p", ura="P")
        r, info, rnd, d = t.play(wl, {0: [("ankan", "2p"), ("tsumo", None)]})
        win = r["wins"][0]
        self.assertIn("rinshan", [y["name"] for y in win["yaku"]])
        self.assertEqual([e["t"] for e in rnd["events"]].count("dora"), 1)                           # 表ドラ 1 枚だけ
        self.assertEqual(sum(y["han"] for y in win["yaku"] if y["name"] == "dora"), 4)               # 2p が 4 枚
        self.assertEqual(R.normalize(R.find(name="tenhou-3p"))["settlement"]["uma"], [20, 0, -20])
        self.assertNotIn("unknown", R.find(name="tenhou-3p"))

    def test_O56_nuki_options_not_enforced(self):
        """抜く牌を手に残すのを止める設定（forbid_keep＝true）と抜きドラの責任払い（pao＝true）は、進行役が従えない設定として知らせる。"""
        b = "tenhou-3p"
        self.assertEqual(D.unsupported(R.find(name=b)), [])
        for k, v in (("forbid_keep", True), ("pao", True)):
            self.assertTrue(any(k in u for u in D.unsupported(rule(b, **{"game_rules__nuki__" + k: v}))), k)
        self.assertEqual([r["name"] for r in R.bundled() if D.unsupported(r)], [])

    def test_O57_reserved_replacements(self):
        """東天紅（LAG）：「ドラは9枚目をめくる(抜きドラ12枚+槓用の4枚)」「ドラ表示牌の隣までツモる」＝補充は取ってある 16 枚から取り、局は短くならない。
        108 枚 − 配牌 39 枚 − 王牌 18 枚 ＝ ツモ 51 枚。抜いても抜かなくても、流局までのツモ（補充を除く）は 51 枚。"""
        H = {0: "147p 258p 369p 147s 2s", 1: "258s 369s 147p 258p 3p", 2: "369s 147s 258s EE SS"}
        for script, nuki in (({}, 0), ({0: [("nuki", "N")]}, 1)):
            t = Table("toutenkou-3p")
            r, info, rnd, d = t.play(t.wall(0, H, draws="N", rinshan="W"), script)
            ev = rnd["events"]
            self.assertEqual(r["draw"]["reason"], "exhaustive")
            self.assertEqual(sum(1 for e in ev if e["t"] == "nuki"), nuki)
            self.assertEqual(sum(1 for e in ev if e["t"] == "draw" and not e.get("rinshan")), 51, nuki)
            self.assertEqual(sum(1 for e in ev if e["t"] == "draw" and e.get("rinshan")), nuki)
        b = R.find(name="tenhou-3p")                                                                 # 書かなければ（false でも）これまでの id のまま
        self.assertEqual(R.new_from(b, "t", {"wall_rules.rinshan_reserved": False})["id"], b["id"])
        self.assertNotEqual(R.new_from(b, "t", {"wall_rules.rinshan_reserved": True})["id"], b["id"])
        t = Table("tenhou-3p")                                                                       # これまでのルール：抜いた数だけ早く終わる
        r, info, rnd, d = t.play(t.wall(0, H, draws="N", rinshan="W"), {0: [("nuki", "N")]})
        n0 = 108 - 39 - 14
        self.assertEqual(sum(1 for e in rnd["events"] if e["t"] == "draw" and not e.get("rinshan")), n0 - 1)

    def test_O58_nuki_kept_in_hand(self):
        """東天紅：「抜きドラ(ガリ)はどのタイミングで抜いても良いが手牌には使用できない」「一萬、九萬、北を使用しないと和了できない役満のみ使用可」（LAG）、
        「国士無双、清老頭、字一色、四喜和の場合、「一萬」、「九萬」、「北」は手牌で使える。」（麻雀プレス）。"""
        O = {1: "147p 258p 369p 147s 2s", 2: "258s 369s 147p 258p 3p"}
        script = {0: [("riichi", "C"), ("ron", None)], 1: [("discard", "N")]}

        def go(name, hand, draws):
            t = Table(name)
            r, info, rnd, d = t.play(t.wall(0, {**O, 0: hand}, draws=draws), script)
            return r, t.left
        r, left = go("toutenkou-3p", "234p 567p 345s 678s N", "C N")                                # 北を雀頭に残したまま：ロンできない
        self.assertEqual((r["wins"], left.get(0)), ([], [("ron", None)]))
        script[1] = [("discard", "E")]
        r, left = go("toutenkou-3p", "234p 567p 345s 678s E", "C E")                                # 雀頭が抜く牌でなければ和了できる
        self.assertEqual((len(r["wins"]), r["wins"][0]["who"]), (1, 0))
        t = Table("toutenkou-3p")                                                                    # 記録した和了を判定し直すと同じ（足し算の点数は符を比べない）
        r, info, rnd, d = t.play(t.wall(0, {**O, 0: "234p 567p 345s 678s E"}, draws="C E"), script)
        i = next(k for k, e in enumerate(rnd["events"]) if e["t"] == "win")
        rec = d.rc.rec
        self.assertIsNone(J.same_as_recorded(J.judge_win(rec, rnd["index"], i, t.rs, t.ts, d.walls), r["wins"][0]))
        script[1] = [("discard", "N")]
        r, left = go("tenhou-3p", "234p 567p 345s 678s N", "C N")                                   # 天鳳三麻：抜かずに手に残したままでも和了できる
        self.assertEqual(len(r["wins"]), 1)
        t = Table("toutenkou-3p")                                                                    # 国士無双：一萬・九萬・北を使って和了できる
        r, info, rnd, d = t.play(t.wall(0, {**O, 0: "19m 19p 19s ESWN PFC"}, draws="2s C"),
                                 {0: [("discard", "2s"), ("ron", None)], 1: [("discard", "C")]})
        self.assertIn(r["wins"][0]["yaku"][0]["name"], ("kokushi", "kokushi13"))

    def test_O59_kansai_reds_and_nuki(self):
        """関西サンマ（出典）：「五筒、五索がすべてドラである。」「赤8枚、抜きドラ4枚、オモドラ4枚、裏ドラ4枚」、
        「抜きドラ用の四枚、四槓のための四枚、計八枚を嶺上牌とし、その隣をドラ表示牌として開ける」、
        北抜きの店では「北絡みや字牌絡みの役満（四喜和、字一色など）以外で北を手の内に使うことはできない」。"""
        rs = R.find(name="kansai-3p"); ts = TS.find(id=rs["tileset"]["id"]); n = R.normalize(rs)
        reds = [t for t in ts["tiles"] if "red" in (t.get("mark") or [])]
        self.assertEqual(sorted(t["kind"] for t in reds), ["5p"] * 4 + ["5s"] * 4)
        self.assertEqual(len(ts["tiles"]), 108)
        nk = n["game_rules"]["nuki"]; w = n["wall_rules"]
        self.assertEqual((nk["enabled"], nk["tiles"], nk["value"], nk["win_with_nuki_in_hand"]), (True, ["N"], 1, False))
        self.assertEqual((len(w["rinshan"]), w["dora_indicator"]), (8, [4]))
        H = {0: "234p 55p 678p 345s 78s", 1: "147p 258s 369s EE SS", 2: "369p 147s 258s WW PP"}
        t = Table("kansai-3p")                                                                       # 北を抜いて立直、ロン：赤 3 枚（五筒 2・五索 1）と抜きドラ 1 枚
        r, info, rnd, d = t.play(t.wall(0, H, draws="N C 9s", rinshan="F", dora="1s", ura="1s"),
                                 {0: [("nuki", "N"), ("riichi", "F"), ("ron", None)], 1: [("discard", "C")], 2: [("discard", "9s")]})
        self.assertEqual([(y["name"], y["han"]) for y in r["wins"][0]["yaku"]],
                         [("riichi", 1), ("ippatsu", 1), ("pinfu", 1), ("aka_dora", 3), ("nuki_dora", 1)])
        self.assertEqual(r["scores"], [43000, 25000, 7000])                                          # 親の跳満 18000
        t = Table("kansai-3p")                                                                       # 北を雀頭に残したまま：ロンできない
        r, info, rnd, d = t.play(t.wall(0, {**H, 0: "234p 678p 345s 78s NN"}, draws="C C 9s"),
                                 {0: [("riichi", "C"), ("ron", None)], 1: [("discard", "C")], 2: [("discard", "9s")]})
        self.assertEqual((r["wins"], t.left.get(0)), ([], [("ron", None)]))


if __name__ == "__main__":
    unittest.main()
