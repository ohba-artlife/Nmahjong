"""天鳳が公表しているルールの文（マニュアル https://tenhou.net/man/ の「段位戦 4人打ち」「3人打ち」、2026-11-18 取得）と、
同梱ルール tenhou-* ＋進行役の突き合わせ。実対局（tests/test_tenhou_logs.py）に出てこない場面を、山を組んだ局で確かめる。

各試験の docstring の「」は天鳳の文の引用。項目ごとの対応表は docs/rules/tenhou-rules.md。
"""
import unittest

from nmahjong import dealer as D, observe as O, ruleset as R, tileset as TS

from scripted import Table, kinds

T4 = "tenhou-4p-hanchan-red"
JUNK = "147m 258p 369s ESW P"          # 聴牌しない手


def next_of(name, bakaze, kyoku, scores, kind, dealer_won=False, dealer_tenpai=False):
    """局の結果から、次の局（場風, 局, 本場）か、終わる理由。"""
    rs = R.find(name=name)
    d = D.Dealer(rs, TS.find(id=rs["tileset"]["id"]), decide=lambda *a: None)
    d._sticks = []
    oya = (kyoku - 1) % d.M
    st = {"bakaze": bakaze, "kyoku": kyoku, "honba": 0, "kyotaku": 0, "oya": oya, "scores": scores}
    if kind == "win":
        info = {"kind": "win", "dealer_won": dealer_won, "winners": [oya if dealer_won else (oya + 1) % d.M]}
    else:
        info = {"kind": "draw", "reason": "exhaustive", "dealer_tenpai": dealer_tenpai, "any_tenpai": True, "nagashi": []}
    n, why = d.next_state(st, {"scores": scores}, info, 0)
    return (n["bakaze"], n["kyoku"], n["honba"]) if n else "end"


class TestTenhouEnd(unittest.TestCase):
    """対局の終わり方。"""

    def test_TR08_extension_and_sudden_death(self):
        """「東風戦の南入、東南戦の西入あり、以降サドンデスルールで終了。」
        「サドンデスルールは、30000点(供託未収)以上になった時点で終了、ただし親の連荘がある場合は連荘を優先する」
        「サドンデスの最大局は東風戦は南場まで、東南戦は西場まで」
        補足「連荘○ 親が原点以上のトップなら和了止め/聴牌止め、他は連荘」「連荘× 最大局数までに原点以上の者が存在しなければ続行」"""
        c = self.assertEqual
        # 南 4 局（東南戦のオーラス）
        c(next_of(T4, "S", 4, [29000, 29000, 29000, 13000], "win"), ("W", 1, 0))                    # 30000 以上がいない → 西入
        c(next_of(T4, "S", 4, [31000, 29000, 29000, 11000], "win"), "end")
        c(next_of(T4, "S", 4, [25000, 25000, 25000, 25000], "draw"), ("W", 1, 1))                   # 親ノーテン・30000 以上なし → 西入
        c(next_of(T4, "S", 4, [40000, 20000, 20000, 20000], "draw"), "end")                         # 「親がノーテンで原点以上が存在する」
        # 西場（サドンデス）
        c(next_of(T4, "W", 1, [31000, 29000, 29000, 11000], "win"), "end")
        c(next_of(T4, "W", 1, [29000, 29000, 29000, 13000], "win"), ("W", 2, 0))
        c(next_of(T4, "W", 1, [25000, 40000, 20000, 15000], "draw"), "end")                         # 親ノーテン・30000 以上あり
        c(next_of(T4, "W", 1, [40000, 25000, 20000, 15000], "win", dealer_won=True), "end")          # 親が連荘して原点以上のトップ → 和了止め
        c(next_of(T4, "W", 1, [25000, 40000, 20000, 15000], "win", dealer_won=True), ("W", 1, 1))    # 親が連荘、トップでない → 連荘を優先
        c(next_of(T4, "W", 1, [25000, 40000, 20000, 15000], "draw", dealer_tenpai=True), ("W", 1, 1))
        c(next_of(T4, "W", 1, [40000, 25000, 20000, 15000], "draw", dealer_tenpai=True), "end")      # 聴牌止め
        # 最大局
        c(next_of(T4, "W", 4, [29000, 29000, 29000, 13000], "win"), "end")                          # 東南戦は西場まで
        c(next_of(T4, "W", 4, [25000, 25000, 25000, 25000], "draw"), "end")
        c(next_of(T4, "W", 4, [29000, 29000, 13000, 29000], "win", dealer_won=True), ("W", 4, 1))    # 連荘は続く
        c(next_of("tenhou-4p-tonpu-red", "E", 4, [29000, 29000, 29000, 13000], "win"), ("S", 1, 0))  # 東風戦の南入
        c(next_of("tenhou-4p-tonpu-red", "S", 4, [29000, 29000, 29000, 13000], "win"), "end")        # 東風戦は南場まで
        c(next_of("tenhou-3p", "S", 3, [39000, 39000, 27000], "win"), ("W", 1, 0))                   # 三麻は 40000
        c(next_of("tenhou-3p", "W", 3, [39000, 39000, 27000], "win"), "end")

    def test_TR12_last_dealer_stops_when_top(self):
        """「ラス親トップの自動和了り止め、自動聴牌止めあり」。トップでなければ連荘。"""
        c = self.assertEqual
        c(next_of(T4, "S", 4, [20000, 20000, 20000, 40000], "win", dealer_won=True), "end")
        c(next_of(T4, "S", 4, [40000, 20000, 20000, 20000], "win", dealer_won=True), ("S", 4, 1))
        c(next_of(T4, "S", 4, [20000, 20000, 20000, 40000], "draw", dealer_tenpai=True), "end")
        c(next_of(T4, "S", 4, [40000, 20000, 20000, 20000], "draw", dealer_tenpai=True), ("S", 4, 1))

    def test_TR11_busting(self):
        """「飛び終了あり。点数がマイナスで飛び終了、マイナス点数も集計、0点は続行」"""
        self.assertEqual(next_of(T4, "E", 1, [0, 50000, 25000, 25000], "win"), ("E", 2, 0))
        self.assertEqual(next_of(T4, "E", 1, [-100, 50100, 25000, 25000], "win"), "end")


class TestTenhouPao(unittest.TestCase):
    """包（責任払い）。席 1（子）が白・發を席 2 から、中を席 3 からポン。大三元を確定させた席 3 が責任者。"""
    HANDS = {0: "123m 456m 678m 1p 1p 2s 3s", 1: "PP FF CC 22m 345p 6s 9s", 2: "P F 579m 57p 579s 1s 1s 1p", 3: "C 468m 468p 468s 9p 9p 9p"}
    COMPOUND = {**HANDS, 1: "PP FF CC EEE W 2m 2m 6s"}          # 大三元＋字一色（西の単騎）
    PONS = [("pon", "P"), ("discard", "2m"), ("pon", "F"), ("discard", "2m"), ("pon", "C"), ("discard", "6s")]

    def play(self, hands, draws, last, honba=0):
        t = Table(T4)
        w = t.wall(0, hands, draws=draws)
        r, info, rnd, d = t.play(w, {2: [("discard", "P"), ("discard", "F")], 3: [("discard", "C")], 1: self.PONS + [last]}, state={"honba": honba})
        self.assertEqual(t.left, {})
        (win,) = r["wins"]
        return win

    def test_TR24_tsumo_liable_pays_all(self):
        """「大三元/大四喜のパオあり。…ツモ＝全額…で支払う。積み棒は包。」子の役満ツモ 32000＋2 本場 600 を、責任者 1 人が払う。"""
        w = self.play(self.HANDS, "8s 8s 8s 7p 8p 8p 7m 7m 6p 9s", ("tsumo", None), honba=2)
        self.assertEqual(([y["name"] for y in w["yaku"]], w["points"], w["pao"]), (["daisangen"], 32000, 3))
        self.assertEqual(w["deltas"], [0, 32600, 0, -32600])

    def test_TR24_ron_split_and_honba_on_liable(self):
        """「…ロン＝折半で支払う。積み棒は包。」32000 を放銃者と責任者が 16000 ずつ。2 本場の 600 は責任者。"""
        w = self.play(self.HANDS, "8s 8s 8s 7p 8p 8p 7m 7m 9s", ("ron", None), honba=2)
        self.assertEqual((w["from"], w["points"], w["pao"]), (0, 32000, 3))
        self.assertEqual(w["deltas"], [-16000, 32600, 0, -16600])

    def test_TR24_compound_yakuman(self):
        """「複合役満を含む得点を、ツモ＝全額・ロン＝折半で支払う。」「※役満は複合あり」
        大三元＋字一色＝64000。ツモは責任者が 64000。ロンは 32000 ずつ、1 本場の 300 は責任者。"""
        w = self.play(self.COMPOUND, "8s 8s 8s 7p 8p 8p 7m 7m 6p W", ("tsumo", None))
        self.assertEqual((sorted(y["name"] for y in w["yaku"]), w["points"]), (["daisangen", "tsuuiisou"], 64000))
        self.assertEqual(w["deltas"], [0, 64000, 0, -64000])
        w = self.play(self.COMPOUND, "8s 8s 8s 7p 8p 8p 7m 7m W", ("ron", None), honba=1)
        self.assertEqual(w["deltas"], [-32000, 64300, 0, -32300])

    def test_TR25_no_pao_for_four_kans(self):
        """「四槓子のパオなし」"""
        g = R.normalize(R.find(name=T4))["game_rules"]
        self.assertEqual(g["pao"]["yakuman"], ["daisangen", "daisuushii"])
        self.assertEqual(R.normalize(R.find(name="tenhou-3p"))["game_rules"]["pao"]["yakuman"], ["daisangen", "daisuushii"])


class TestTenhouAbort(unittest.TestCase):
    """「途中流局(九種九牌/四家立直/三家和了/四槓散了/四風連打)あり。すべて連荘」"""

    def after(self, t, r, info, rnd, d, **state):
        st = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0}
        st.update(state)
        n, why = d.next_state(dict(st, scores=[25000] * t.M), r, info, 0)
        return (r["draw"]["reason"] if r["draw"] else None, n["oya"], n["honba"], n["kyotaku"], r["scores"])

    def test_TR18_four_riichi(self):
        t = Table(T4)
        w = t.wall(0, {0: "123m 456m 789m 11p 23p", 1: "123p 456p 789p 11s 23s", 2: "123s 456s 789s EE 45m", 3: "SSS WWW NNN PP 56p"}, draws="F F C C")
        out = t.play(w, {0: [("riichi", "F")], 1: [("riichi", "F")], 2: [("riichi", "C")], 3: [("riichi", "C")]})
        self.assertEqual(self.after(t, *out), ("four_riichi", 0, 1, 4, [24000] * 4))          # 親はそのまま、1 本場、立直棒 4 本は供託
        self.assertEqual(out[0]["draw"]["tenpai"], [True] * 4)

    def test_TR18_four_winds(self):
        t = Table(T4)
        w = t.wall(0, {0: "E 123m 456m 789m 11p 9s", 1: "E 123p 456p 789p 11s 9m", 2: "E 123s 456s 789s PP 1m", 3: "E SSS WWW NN FF CC"}, draws="2p 3p 4p 5p")
        out = t.play(w, {s: [("discard", "E")] for s in range(4)})
        self.assertEqual(self.after(t, *out), ("four_winds", 0, 1, 0, [25000] * 4))

    def test_TR18_three_ron(self):
        t = Table(T4)
        w = t.wall(0, {0: "123m 456m 678m 11s 5p 9s", 1: "46p 123p 789p 22s 999m", 2: "46p 123s 456s 77s PPP", 3: "46p 789s 234m 88m FFF"}, draws="C")
        out = t.play(w, {0: [("discard", "5p")], 1: [("ron", None)], 2: [("ron", None)], 3: [("ron", None)]})
        self.assertEqual(self.after(t, *out), ("three_ron", 0, 1, 0, [25000] * 4))
        self.assertEqual(out[0]["wins"], [])

    def test_TR18_nine_terminals(self):
        """「九種九牌はポン/カン/チー/暗槓のない第1ツモで幺九牌が9種以上」"""
        t = Table(T4)
        w = t.wall(0, {0: JUNK, 1: "19m 19p 19s ESW 234m 5p"}, draws="2p N")
        out = t.play(w, {1: [("draw_declare", None)]})
        self.assertEqual(self.after(t, *out), ("nine_terminals", 0, 1, 0, [25000] * 4))
        # ポンが入ったあとの第 1 ツモでは宣言できない：席 0 の第 1 打（P）を席 3 がポン → 席 0 がツモ切り → 席 1 の第 1 ツモ
        w = t.wall(0, {0: "P 147m 258p 369s ESW", 1: "19m 19p 19s ESW 234m 5p", 3: "PP 147m 258p 369s EC"}, draws="2p 8s N")
        r, info, rnd, d = t.play(w, {0: [("discard", "P")], 3: [("pon", "P"), ("discard", "C")], 1: [("draw_declare", None)]})
        self.assertEqual(t.left, {1: [("draw_declare", None)]})
        self.assertNotEqual((r["draw"] or {}).get("reason"), "nine_terminals")

    def test_TR18_four_kans(self):
        """四槓散了：2 人以上で 4 つめのカンが入り、その打牌が通ったら流局。1 人で 4 つなら続く（四槓子の聴牌）。"""
        t = Table(T4)
        # 席 0 が 1m・2m・3m を暗槓（最初から 4 枚ずつ）、席 1 が 9s を暗槓
        hands = {0: "1111m 2222m 3333m 5p", 1: "9999s 47m 258p 36s ES", 2: "47m 258p 36s ESW PFC", 3: "58m 369p 147s NN PP F"}
        w = t.wall(0, hands, draws="6p 7p", rinshan="7s 7s 8s 8s")
        script = {0: [("ankan", "1m"), ("ankan", "2m"), ("ankan", "3m")], 1: [("ankan", "9s")]}
        out = t.play(w, script)
        self.assertEqual(t.left, {})
        self.assertEqual(self.after(t, *out), ("four_kans", 0, 1, 0, [25000] * 4))
        self.assertEqual(sum(1 for e in out[2]["events"] if e["t"] == "kan"), 4)
        # 1 人で 4 つ：流局にならない
        hands = {0: "1111m 2222m 3333m 4p", 1: "47m 258p 369s ESW PF", 2: "47m 258p 36s ESW PFC", 3: "58m 369p 147s NN PP F"}
        w = t.wall(0, hands, draws="4p", rinshan="4p 4p 9s 9s")
        r, info, rnd, d = t.play(w, {0: [("ankan", "1m"), ("ankan", "2m"), ("ankan", "3m"), ("ankan", "4p")]})
        self.assertEqual(t.left, {})
        self.assertNotEqual((r["draw"] or {}).get("reason"), "four_kans")


class TestTenhouDoubleRon(unittest.TestCase):
    def test_TR22_honba_and_sticks_to_the_nearer_winner(self):
        """「ダブロンあり。積み棒/供託は上家取り。」「ダブロンは親が含まれれば連荘」
        席 0（親）の 5p に席 2・席 3 がロン。2 本場の 600 と供託 1000 は、放銃者から近い席 2 だけが取る。親は入っていないので流れる。"""
        t = Table(T4)
        w = t.wall(0, {0: "123m 456m 678m 11s 5p 9s", 1: JUNK, 2: "46p 123s 456s 77s PPP", 3: "46p 789s 234m 88m FFF"}, draws="C")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 2: [("ron", None)], 3: [("ron", None)]}, state={"honba": 2, "kyotaku": 1})
        a, b = r["wins"]
        self.assertEqual((a["who"], b["who"]), (2, 3))
        self.assertEqual((a["points"], b["points"]), (1300, 1300))                 # 役牌 1 翻 40 符
        self.assertEqual(a["deltas"], [-1900, 0, 2900, 0])
        self.assertEqual(b["deltas"], [-1300, 0, 0, 1300])
        n, _ = d.next_state({"bakaze": "E", "kyoku": 1, "honba": 2, "kyotaku": 1, "oya": 0, "scores": [25000] * 4}, r, info, 0)
        self.assertEqual((n["oya"], n["honba"], n["kyotaku"]), (1, 0, 0))
        # 親が入るダブロン：席 1 の 5p に席 0（親）と席 2 → 連荘
        w = t.wall(0, {1: "123m 456m 678m 11s 5p 9s", 0: "46p 123s 456s 77s PPP", 2: "46p 789s 234m 88m FFF", 3: JUNK}, draws="C 9p")
        r, info, rnd, d = t.play(w, {1: [("discard", "5p")], 0: [("ron", None)], 2: [("ron", None)]})
        self.assertEqual([x["who"] for x in r["wins"]], [2, 0])                     # 放銃者（席 1）から近い順
        n, _ = d.next_state({"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [25000] * 4}, r, info, 0)
        self.assertEqual((n["oya"], n["honba"]), (0, 1))


class TestTenhouNagashi(unittest.TestCase):
    """「流し満貫あり。聴牌清算を満貫清算に代替。親の聴牌で連荘。」
    「流し満貫は、自分の河が鳴かれていない場合に成立。自分が鳴いた場合でも成立。」"""

    def play(self, hands, script=None):
        """席 1・席 2 が毎巡 幺九牌を引いてツモ切りし、席 0・席 3 は中張牌を引いてツモ切りする山。"""
        t = Table(T4)
        per = {0: kinds("222m 333m 444m 666m 777m 888m"), 1: kinds("111m 999m 111p 999p 111s 999s"),
               2: kinds("EEE SSS WWW NNN PPP FF"), 3: kinds("222p 333p 444p 666p 777p 88p")}
        seq = []
        for i in range(136 - 14 - 52):
            seq.append(per[i % 4][i // 4])
        w = t.wall(0, hands, draws=" ".join(seq))
        r, info, rnd, d = t.play(w, script or {})
        return t, r, info, rnd, d

    HANDS = {0: "2s 2s 4s 4s 6s 6s 8s 8s 3s 5s 7s 5m 5p", 1: "2s 3s 4s 6s 7s 8s 3s 5s 7s 5m 5p 8p 8m",
             2: "2s 4s 6s 8s 3s 5s 7s 5m 8p 4m 2p C 9s", 3: "5p C C F F 9m 1m 1p 9p 1s E S W"}

    def test_TR20_two_players_at_once(self):
        """2 人同時：それぞれ満貫のツモの支払いを受ける。席 1・席 2（どちらも子）→ 各自 親から 4000・子から 2000。"""
        t, r, info, rnd, d = self.play(self.HANDS)
        self.assertEqual(r["draw"]["reason"], "nagashi_mangan")
        self.assertEqual(info["nagashi"], [1, 2])
        #          席 0（親）  席 1               席 2               席 3
        self.assertEqual(r["draw"]["deltas"], [-8000, 8000 - 2000, 8000 - 2000, -4000])

    def test_TR20_renchan_follows_dealer_tenpai(self):
        """「聴牌清算を満貫清算に代替。親の聴牌で連荘。」流し満貫が出ても、連荘するかどうかは親の聴牌で決まる。"""
        t, r, info, rnd, d = self.play(self.HANDS)                               # 親（席 0）はノーテン
        st = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [25000] * 4}
        self.assertEqual(r["draw"]["tenpai"][0], False)
        n, _ = d.next_state(st, r, info, 0)
        self.assertEqual((n["oya"], n["honba"]), (1, 1))
        # 親が聴牌：席 0 を 5m5m 5p5p のシャンポン（＋ 234s 678s 468s ではなく 順子 3 つ）にする
        hands = {0: "2s 3s 4s 6s 7s 8s 4s 5s 6s 5m 5m 5p 5p", 1: "2s 2s 4s 6s 8s 8s 3s 3s 7s 7s 8p 8m C",
                 2: "2s 4s 6s 8s 3s 5s 7s 5m 8p 4m 2p C 9s", 3: "5p C C F F 9m 1m 1p 9p 1s E S W"}
        t, r, info, rnd, d = self.play(hands)
        self.assertEqual((r["draw"]["reason"], r["draw"]["tenpai"][0]), ("nagashi_mangan", True))
        n, _ = d.next_state(st, r, info, 0)
        self.assertEqual((n["oya"], n["honba"]), (0, 1))

    def test_TR21_called_river_does_not_count(self):
        """「流し満貫は、自分の河が鳴かれていない場合に成立。自分が鳴いた場合でも成立。」
        席 1 の第 1 打（1m）を席 2 がポン。席 1 は河を鳴かれたので不成立。席 2 は自分が鳴いても成立。"""
        t = Table(T4)
        per = {0: kinds("222m 333m 444m 666m 777m 888m"), 1: kinds("1m 99m 111p 999p 111s 999s NNN"),
               2: kinds("EEE SSS WWW PPP FF C 9m 1m"), 3: kinds("222p 333p 444p 666p 777p 88p")}
        seq = [per[i % 4][i // 4] for i in range(136 - 14 - 52)]
        hands = {0: "2s 2s 4s 4s 6s 6s 8s 8s 3s 5s 7s 5m 5p", 1: "2s 3s 4s 6s 7s 8s 3s 5s 7s 5m 5p 8p 8m",
                 2: "1m 1m 2s 4s 6s 8s 3s 5s 7s 5m 8p C 9s", 3: "5p C C F F N 9m 1s 1p 9p E S W"}
        w = t.wall(0, hands, draws=" ".join(seq))
        r, info, rnd, d = t.play(w, {2: [("pon", "1m"), ("discard", "9s")]})
        self.assertEqual(t.left, {})
        self.assertEqual(r["draw"]["reason"], "nagashi_mangan")
        self.assertIn(2, info["nagashi"])
        self.assertNotIn(1, info["nagashi"])


class TestTenhouTenpaiAndRiichi(unittest.TestCase):
    def test_TR26_waiting_only_on_tiles_used_up_in_hand_is_not_tenpai(self):
        """「形式聴牌あり。5枚目を待つ聴牌あり(手牌＝純手牌＋副露手牌として純手牌で４枚使用していなければ成立)」"""
        t = Table(T4)
        ts = t.ts
        used = set()
        tiles = lambda text: [t._take(k, used) for k in kinds(text)]          # noqa: E731
        # 123p 456p 789p 999m 9m：待ちは 9m の単騎だけ。9m は手の中で 4 枚使っている → 聴牌ではない
        hand = tiles("123p 456p 789p 9999m")
        self.assertEqual(O.waits(ts, hand, 0, 13), {"9m"})
        self.assertEqual(O.tenpai_waits(ts, hand, 0, 13), set())
        # 13m 55p 678s ＋ 副露 2 つ（そのうち 1 つが 2m のポン）：2m は残り 1 枚しかないが、純手牌では使っていない → 聴牌
        used.clear()
        hand = tiles("13m 55p 678s")
        self.assertEqual(O.tenpai_waits(ts, hand, 2, 13), {"2m"})
        # 役が無くても聴牌（形式聴牌）：副露した手の待ち
        used.clear()
        hand = tiles("23m 99p")
        self.assertEqual(O.tenpai_waits(ts, hand, 3, 13), {"1m", "4m"})

    def test_TR27_riichi_needs_1000_points_and_a_draw_left(self):
        """「リーチ宣言は得点が1000点以上でツモ巡がある場合に可能」"""
        t = Table(T4)
        w = t.wall(0, {0: "123m 456m 789m 11p 23p"}, draws="F")
        r, info, rnd, d = t.play(w, {})
        obs = O.observe(d.rc.rec, 0, 2, 0, t.rs, t.ts, d.walls)                 # 席 0 の第 1 ツモの直後
        types = lambda o: {a["type"] for a in O.legal_actions(t.rs, t.ts, o, "A")}   # noqa: E731
        self.assertIn("riichi", types(obs))
        self.assertIn("riichi", types({**obs, "state": {**obs["state"], "scores": [1000, 33000, 33000, 33000]}}))
        self.assertNotIn("riichi", types({**obs, "state": {**obs["state"], "scores": [900, 33100, 33000, 33000]}}))
        self.assertIn("riichi", types({**obs, "remaining": 4}))                  # 次の自分のツモがある
        self.assertNotIn("riichi", types({**obs, "remaining": 3}))

    def test_TR28_no_stick_when_the_riichi_discard_is_ronned(self):
        """「リーチ宣言牌で放銃した場合は供託料は発生しない」"""
        t = Table(T4)
        w = t.wall(0, {0: "123m 456m 789m 11p 23p", 1: "46p 123s 456s 77s PPP"}, draws="5p")
        r, info, rnd, d = t.play(w, {0: [("riichi", "5p")], 1: [("ron", None)]})
        (win,) = r["wins"]
        self.assertEqual((win["who"], win["from"], win["points"]), (1, 0, 1300))
        self.assertEqual(win["deltas"], [-1300, 1300, 0, 0])
        self.assertEqual(r["scores"], [23700, 26300, 25000, 25000])

    def test_TR38_last_discard_cannot_be_called(self):
        """「海底牌は鳴けない」"""
        t = Table(T4)
        w = t.wall(0, {0: "P 147m 258p 369s ESW", 3: "PP 147m 258p 369s EC"}, draws="2p")
        r, info, rnd, d = t.play(w, {0: [("discard", "P")], 3: [("skip", None)]})
        at = next(i for i, e in enumerate(d.rc.rec["rounds"][0]["events"]) if e["t"] == "discard")
        obs = O.observe(d.rc.rec, 0, at, 3, t.rs, t.ts, d.walls)
        types = lambda o: {a["type"] for a in O.legal_actions(t.rs, t.ts, o, "C")}   # noqa: E731
        self.assertIn("pon", types(obs))
        self.assertNotIn("pon", types({**obs, "remaining": 0}))
        obs = O.observe(d.rc.rec, 0, at, 1, t.rs, t.ts, d.walls)
        self.assertFalse({"chi", "pon", "kan"} & types({**obs, "remaining": 0}))


class TestTenhouFuriten(unittest.TestCase):
    """席 2 が 5p 待ち（46p 123s 456s 77s PPP：役牌）。"""
    WAIT = "46p 123s 456s 77s PPP"

    def test_TR36_same_turn(self):
        """「同一巡内の選択ロン和了なし(加槓牌を含む)」「和了放棄(搶槓を含む)後は同巡フリテンとなり、次の自分のツモ番までロン和了できない」
        「同巡振聴の解消は打牌時」。席 0 の 5p を見送る → 同じ巡の席 1 の 5p はロンできない → 自分が打牌したあとの席 3 の 5p はロンできる。"""
        t = Table(T4)
        w = t.wall(0, {0: "5p 147m 28p 369s ESW N", 2: self.WAIT}, draws="9m 5p 9m 5p")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 2: [("skip", None), ("ron", None)]})
        (win,) = r["wins"]
        self.assertEqual((win["who"], win["from"]), (2, 3))

    def test_TR30_after_riichi_it_is_permanent(self):
        """「リーチ後の当たり牌見逃しは以降振聴」。立直したあとに 5p を見送ると、その局はもうロンできない（ツモはできる）。"""
        t = Table(T4)
        w = t.wall(0, {2: self.WAIT}, draws="9m 9m C 9m  1m 5p 1m 5p  5p")
        #                              席0 席1 席2(立直) 席3 ｜ 席0 席1(5p) 席2 席3(5p) ｜ 席0(5p)
        r, info, rnd, d = t.play(w, {2: [("riichi", "C"), ("skip", None), ("ron", None)]})
        self.assertEqual(t.left, {2: [("ron", None)]})                           # 見送ったあと、ロンは最後までできなかった
        self.assertEqual(r["wins"], [])
        evs = rnd["events"]
        fives = [i for i, e in enumerate(evs) if e["t"] == "discard" and O.kind_of(t.ts, e["tile"]) == "5p"]
        self.assertGreaterEqual(len(fives), 3)                                   # 5p は何度も出た（1 回目を見送り）
        for n, i in enumerate(fives):
            types = {a["type"] for a in O.legal_actions(t.rs, t.ts, O.observe(d.rc.rec, 0, i, 2, t.rs, t.ts, d.walls), "C")}
            self.assertEqual("ron" in types, n == 0, i)


class TestTenhouChankan(unittest.TestCase):
    def test_TR35_ippatsu_with_robbed_kan(self):
        """「※一発と槍槓（連続槓の１回目）は複合する」「純正巡消しは発声＆和了打診後（加槓のみ)、嶺上ツモの前」
        席 3 が P をポン（立直の前）。席 2 が立直。次に席 3 が 5p を引いて加槓… ではなく、5p をポンしておいて 4 枚目を加槓 → 席 2 が槍槓。"""
        t = Table(T4)
        hands = {0: "5p 147m 28p 369s EWS N", 2: "46p 123s 456s 77s 789m", 3: "55p 147m 28p 369s ES C"}
        # 席 0 が 5p を切る → 席 3 がポン（席 2 はまだ立直していないので見送り＝この時点では役なし）→ 席 3 打 C
        # → 席 0 ツモ切り → 席 1 ツモ切り → 席 2 立直（F 切り）→ 席 3 が 5p（赤でない最後の 1 枚…は無いので赤）を引いて加槓 → 席 2 がロン
        w = t.wall(0, hands, draws="9m 9p 9p F 0p")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p")], 3: [("pon", "5p"), ("discard", "C"), ("kakan", "5p")], 2: [("riichi", "F"), ("ron", None)]})
        self.assertEqual(t.left, {})
        (win,) = r["wins"]
        self.assertEqual((win["who"], win["from"]), (2, 3))
        names = [y["name"] for y in win["yaku"]]
        for y in ("riichi", "ippatsu", "chankan"):
            self.assertIn(y, names)


class TestTenhou3p(unittest.TestCase):
    T3 = "tenhou-3p"

    def test_TS08_no_nuki_right_after_pon(self):
        """「ポンの直後は抜けない」"""
        t = Table(self.T3)
        w = t.wall(0, {0: "P 19m 258p 369s ESW 1p", 1: "PP N 19m 258p 369s E S"}, draws="2p")
        r, info, rnd, d = t.play(w, {0: [("discard", "P")], 1: [("pon", "P"), ("nuki", "N")]})
        evs = rnd["events"]
        i_pon = next(i for i, e in enumerate(evs) if e["t"] == "pon")
        i_nuki = next((i for i, e in enumerate(evs) if e["t"] == "nuki" and e["who"] == 1), None)
        self.assertEqual(evs[i_pon + 1]["t"], "discard")                         # ポンの直後は打牌
        self.assertTrue(i_nuki is None or any(e["t"] == "draw" and e["who"] == 1 for e in evs[i_pon:i_nuki]))   # 抜くのは次のツモのあと

    def test_TS09_nuki_counts_as_a_call(self):
        """「抜きは鳴きと同じ扱い(一発/地和/九種/両立直は消える)」"""
        t = Table(self.T3)
        # 九種：席 0 が第 1 ツモで北を抜く → 席 1 の第 1 ツモでは九種九牌を宣言できない
        w = t.wall(0, {0: "N 19m 258p 369s ESW 1p", 1: "19m 19p 19s ESW 2p 3p 4p 5s"}, draws="2s 4s P", rinshan="6s")
        r, info, rnd, d = t.play(w, {0: [("nuki", "N")], 1: [("draw_declare", None)]})
        self.assertEqual(t.left, {1: [("draw_declare", None)]})
        # 両立直：席 0 が抜いたあと、席 1 が第 1 打で立直しても、ダブル立直ではなく立直
        w = t.wall(0, {0: "N 19m 258p 369s ESW 1p", 1: "123p 456p 789p 11s 23s"}, draws="2s F 1s", rinshan="6s")
        r, info, rnd, d = t.play(w, {0: [("nuki", "N")], 1: [("riichi", "F"), ("tsumo", None)]})
        (win,) = r["wins"]
        names = [y["name"] for y in win["yaku"]]
        self.assertIn("riichi", names)
        self.assertNotIn("double_riichi", names)

    def test_TS07_nuki_tile_is_not_in_the_river_for_furiten(self):
        """「フリテンは河に捨てられた牌でのみ判定(加槓・抜きでさらした非純手牌を除く)」「北は抜きドラ」
        北を 1 枚抜き、もう 1 枚の北の単騎で待つ。他家の北でロンできる（自分で抜いた北はフリテンにしない）。"""
        t = Table(self.T3)
        w = t.wall(0, {0: "N N 123p 456p 789p PP", 2: "N 19m 258p 369s ESW 1p"}, draws="P 3s 4s", rinshan="6s")
        r, info, rnd, d = t.play(w, {0: [("nuki", "N"), ("ron", None)], 2: [("discard", "N")]})
        self.assertEqual(t.left, {})
        (win,) = r["wins"]
        self.assertEqual((win["who"], win["from"]), (0, 2))


class TestTenhouMisc(unittest.TestCase):
    def test_TR29_riichi_while_furiten(self):
        """「振聴リーチあり」。自分で 1p を捨てていても（1p-4p 待ち）、立直できる。"""
        t = Table(T4)
        w = t.wall(0, {0: "123m 456m 789m 99s 1p 2p"}, draws="3p C C C F")
        r, info, rnd, d = t.play(w, {0: [("discard", "1p"), ("riichi", None)]})
        self.assertEqual(t.left, {})
        self.assertTrue(any(e["t"] == "riichi" and e["who"] == 0 for e in rnd["events"]))

    def test_TR37_a_call_by_others_does_not_clear_same_turn_furiten(self):
        """「同巡振聴の解消は打牌時、逆巡副露では解消しない。」
        席 2（5p 待ち）が席 0 の 5p を見送る → 席 1 の 9m を席 0 がポンして、また 5p を切る（席 2 は打牌していない）→ ロンできない。
        席 2 が打牌したあとの席 3 の 5p はロンできる。"""
        t = Table(T4)
        w = t.wall(0, {0: "5p 5p 9m 9m 14m 28p 369s E S", 2: "46p 123s 456s 77s PPP"}, draws="C 9m F N 5p")
        r, info, rnd, d = t.play(w, {0: [("discard", "5p"), ("pon", "9m"), ("discard", "5p")], 2: [("skip", None), ("ron", None)]})
        self.assertEqual(t.left, {})
        (win,) = r["wins"]
        self.assertEqual((win["who"], win["from"]), (2, 3))
        evs = rnd["events"]
        fives = [i for i, e in enumerate(evs) if e["t"] == "discard" and O.kind_of(t.ts, e["tile"]) == "5p"]
        self.assertEqual([evs[i]["who"] for i in fives], [0, 0, 3])

    def test_TR39_yaku_not_adopted(self):
        """「八連荘/人和/三連刻/一色三順/十三不塔/…なし」「※役満は複合あり、四暗刻単騎・国士無双十三面待ち等はすべてシングル役満」「※数え役満は13翻以上」"""
        g = R.normalize(R.find(name=T4))["game_rules"]
        ov = g["yaku"]["overrides"]
        for y in ("renhou", "sanrenkou", "daisharin"):
            self.assertIn(ov.get(y, False), (False, None), y)
        lim = g["scoring"]["limits"]
        self.assertEqual((lim["kazoe_from"], lim["max_multiple"]), (13, 6))
        self.assertEqual(g["flow"]["riichi"]["furiten_riichi"], True)
        self.assertEqual(g["flow"]["kuikae"], "forbidden")                        # 「喰い替えなし」


class TestScenarioGames(unittest.TestCase):
    """山を組んだ対局（tests/scripted.py の SCENARIOS）を最後まで進めたものが、対局の検証を通り、記録係・進行役で進め直しても同じになる。
    同じ対局を JavaScript 版にも進め直させる（js/test_game.js）。"""

    def test_TG1_all_scenarios_validate_and_replay(self):
        from nmahjong import record as REC, recorder as RC
        from scripted import SCENARIOS, scenario_game
        expect = {"pao-tsumo": [0, 32000, 0, -32000], "pao-ron": [-16000, 32000, 0, -16000], "pao-compound-ron": [-32000, 64000, 0, -32000],
                  "pao-ron-mleague": [-16000, 32000, 0, -16000]}
        reasons = {"four-riichi": "four_riichi", "three-ron": "three_ron", "four-kans": "four_kans"}
        for name, *_ in SCENARIOS:
            with self.subTest(scenario=name):
                rec, walls, rs, ts, left = scenario_game(name)
                wm = {w["id"]: w for w in walls}
                self.assertEqual(REC.validate(rec, rs, ts, wm), [])
                r0 = rec["rounds"][0]["result"]
                if name in expect:
                    self.assertEqual(r0["wins"][0]["deltas"], expect[name])
                if name in reasons:
                    self.assertEqual(r0["draw"]["reason"], reasons[name])
                if name == "3p-nuki-then-nine-terminals":
                    self.assertEqual(left, {1: [("draw_declare", None)]})
                else:
                    self.assertEqual(left, {})
                r = RC.replay_record(rec, rs, ts, wm)
                self.assertEqual((r.rec["id"], r.warnings), (rec["id"], []))
                d = D.replay_with_dealer(rec, rs, ts, wm, through_gateway=True)
                self.assertIsNone(D.differences(d.rc.rec, rec))


if __name__ == "__main__":
    unittest.main()
