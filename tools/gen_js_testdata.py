"""JS 版（4 層・5 層）の試験データを作る：js/testdata/games.jsonl と js/testdata/selfplay.json。
Python 実装の結果（和了の状況・役と符・局面・合法手・検証の注意・評価の id・同梱の打ち手同士の対局の id）を書き出し、
js/test_game.js が JS 実装の結果と突き合わせる。tests/data/corpus の対局（N 枚麻雀の先頭 20 と、13 枚麻雀の四麻・三麻の 2）と、山を組んだ対局（国士無双の槍槓、包、途中流局 など）を使う。"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nmahjong import bots as B, dealer as D, evaluate as EV, gateway as GW, judge as J, observe as O, record as REC, ruleset as R, scoring as S, tileset as TS, wall as W  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tests"))
from corpus import nm_games, rob_ankan_game, sp_games  # noqa: E402
from scripted import SCENARIOS, scenario_game  # noqa: E402

OUT = os.path.join(ROOT, "js", "testdata")
os.makedirs(OUT, exist_ok=True)


def games():
    for g in nm_games()[:20]:          # N 枚麻雀の対局（tests/data/corpus）の先頭 20：4 枚 14・1 枚 6
        yield g
    for g in sp_games():               # 13 枚麻雀の対局（四麻・三麻。チー・ポン・カン・抜きドラ・立直・流局あり）
        yield g
    yield rob_ankan_game("jantama-4p", True)      # 暗槓の牌へのロン（国士無双の槍槓）がある対局
    for name, *_ in SCENARIOS:                       # 山を組んだ対局（包、途中流局、ダブロン、槍槓、抜きのあとの九種 など）
        yield scenario_game(name)[:4]


n = 0
with open(os.path.join(OUT, "games.jsonl"), "w", encoding="utf-8") as f:
    for rec, walls, rs, ts in games():
        wm = {w["id"]: w for w in walls}
        M = R.normalize(rs)["players"]
        judged, legal = [], []
        for rnd in rec["rounds"]:
            for i, e in enumerate(rnd["events"]):
                if e["t"] == "win":
                    ctx = J.win_context(rec, rnd["index"], i, rs, ts, wm)
                    judged.append([rnd["index"], i, ctx, J.judge(rs, ts, ctx)])
        for rnd in rec["rounds"][:1]:
            for at in range(len(rnd["events"])):
                for seat in range(M):
                    ph = O.phase_of(rnd["events"], at, seat)
                    if ph is None:
                        continue
                    obs = O.observe(rec, rnd["index"], at, seat, rs, ts, wm)
                    for p in (("A", "B") if ph == "A" else (ph,)):
                        legal.append([rnd["index"], at, seat, p, obs, O.legal_actions(rs, ts, obs, p), O.actual_action(rec, rnd["index"], at, seat, p)])
        f.write(json.dumps({"rs": rs["name"], "rso": rs, "tso": ts, "rec": rec, "walls": walls, "judged": judged, "legal": legal,
                            "warns": REC.validate(rec, rs, ts, wm), "ann": EV.annotate(rec, rs, ts, wm)["id"]},
                           ensure_ascii=False, separators=(",", ":")) + "\n")
        n += 1

# 同梱の打ち手同士の対局：Python の進行役が作った対局の id（JS の進行役が同じ種で同じ対局を作ることを確かめる）
sp = []
for name in ("nm-2p-1-mps", "nm-2p-4-mps", "nm-2p-7-mps", "nm-2p-10-mpsz", "nm-2p-13-mpsz", "tenhou-4p-tonpu-red", "tenhou-3p", "toutenkou-3p", "sakae-shibuya", "pocchi-house", "kansai-3p"):
    rs = R.find(name=name)
    ts = TS.find(id=rs["tileset"]["id"])
    M = R.normalize(rs)["players"]
    for bot in ("simple", "tsumogiri", "mix"):
        if bot == "tsumogiri" and not name.startswith("nm-"):
            continue
        pick = lambda s: B.BOTS["simple" if (bot == "simple" or (bot == "mix" and s % 2 == 0)) else "tsumogiri"]   # noqa: E731
        d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(pick(s), wants_events=False) for s in range(M)})
        rec = d.play(lambda k, st: W.build(ts, f"js-{name}-{bot}-{k}"))
        sp.append({"rs": name, "bot": bot, "seed": f"js-{name}-{bot}", "id": rec["id"], "rounds": len(rec["rounds"]), "final": rec["final"], "end": d.log[-1]})
with open(os.path.join(OUT, "selfplay.json"), "w", encoding="utf-8") as f:
    json.dump(sp, f, ensure_ascii=False, indent=1)

# 対局の終わり方・聴牌の数え方：Python の進行役の答え（JS の進行役が同じ答えを出すことを確かめる）
cases = {"next_state": [], "tenpai_waits": []}
SC4 = [[29000, 29000, 29000, 13000], [31000, 29000, 29000, 11000], [25000, 25000, 25000, 25000], [40000, 20000, 20000, 20000],
       [20000, 20000, 20000, 40000], [25000, 40000, 20000, 15000], [0, 50000, 25000, 25000], [-100, 50100, 25000, 25000]]
SC3 = [[39000, 39000, 27000], [41000, 39000, 25000], [35000, 35000, 35000], [25000, 50000, 30000]]
INFOS = [{"kind": "win", "dealer_won": False}, {"kind": "win", "dealer_won": True},
         {"kind": "draw", "reason": "exhaustive", "dealer_tenpai": False, "any_tenpai": True, "nagashi": []},
         {"kind": "draw", "reason": "exhaustive", "dealer_tenpai": True, "any_tenpai": True, "nagashi": []},
         {"kind": "abort", "reason": "four_winds"}]
for name in ("tenhou-4p-hanchan-red", "tenhou-4p-tonpu-red", "tenhou-3p", "jantama-4p", "mleague", "nm-2p-4-mps"):
    rs = R.find(name=name)
    d = D.Dealer(rs, TS.find(id=rs["tileset"]["id"]), decide=lambda *a: None, allow_unsupported=True)
    d._sticks = []
    M = d.M
    start = d.norm["settlement"]["start_points"]
    scores = SC4 if M == 4 else SC3 if M == 3 else [[start, start], [start + 12000, start - 12000], [start - 12000, start + 12000], [-100, 2 * start + 100]]
    for bakaze in ("E", "S", "W"):
        for kyoku in (1, M):
            for sc in scores:
                for info in INFOS:
                    oya = kyoku - 1
                    inf = dict(info)
                    if inf["kind"] == "win":
                        inf["winners"] = [oya if inf["dealer_won"] else (oya + 1) % M]
                    st = {"bakaze": bakaze, "kyoku": kyoku, "honba": 0, "kyotaku": 0, "oya": oya, "scores": sc}
                    nxt, why = d.next_state(st, {"scores": sc}, inf, 0)
                    cases["next_state"].append({"rs": name, "state": st, "info": inf, "next": nxt, "why": why})
ts = TS.find(name="mpsz")
by = {}
for i, t in enumerate(ts["tiles"]):
    by.setdefault(t["kind"], []).append(i)
for text, melds in (("1p2p3p4p5p6p7p8p9p9m9m9m9m", 0), ("1m3m5p5p6s7s8s", 2), ("2m3m9p9p", 3), ("1m1m1m1m2m3m4m5m6m7m8m9m9m", 0), ("1m2m3m4m5m6m7m8m9m1p1p2p3p", 0)):
    kindsl = [text[i:i + 2] for i in range(0, len(text), 2)]
    cnt = {}
    hand = []
    for k in kindsl:
        hand.append(by[k][-1 - cnt.get(k, 0)])
        cnt[k] = cnt.get(k, 0) + 1
    cases["tenpai_waits"].append({"hand": hand, "melds": melds, "waits": sorted(O.waits(ts, hand, melds, 13)), "tenpai_waits": sorted(O.tenpai_waits(ts, hand, melds, 13))})

# ルールで選べる払い方・終わり方（tests/test_rule_options.py）：その試験が進めた局を全部写し取り、JS の進行役に同じ判断で進めさせる
import unittest  # noqa: E402
import scripted  # noqa: E402
import test_rule_options as OPT  # noqa: E402

cases["rounds"] = []
_play = scripted.Table.play


def _logged(self, wall, script, state=None, **kw):
    answers = []
    inner = self._decide

    def deciding(d, todo, seat, phase, at):
        a = inner(d, todo, seat, phase, at)
        answers.append(a)
        return a
    self._decide = deciding
    try:
        r, info, rnd, d = _play(self, wall, script, state, **kw)
    finally:
        del self._decide
    st = {"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [self.norm["settlement"]["start_points"]] * self.M}
    st.update(state or {})
    nxt, why = d.next_state(st, r, info, 0)
    cases["rounds"].append({"rso": self.rs, "wall": wall, "state": st, "answers": answers, "result": r, "info": info, "next": nxt, "why": why})
    return r, info, rnd, d


scripted.Table.play = _logged
res = unittest.TextTestRunner(stream=open(os.devnull, "w")).run(unittest.defaultTestLoader.loadTestsFromModule(OPT))
scripted.Table.play = _play
assert res.wasSuccessful() and len(cases["rounds"]) >= 20, (res.failures, res.errors, len(cases["rounds"]))

# 三人打ちのツモの払い・1000 点単位：点数の計算
cases["points"] = []
for mode in ("none", "loss", "add_1000", "marudori", "north_split"):
    for unit in (100, 1000):
        sc = OPT.sc3(mode, round_to=unit)
        for fu in (20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 110):
            for han in range(1, 14):
                for dealer in (False, True):
                    for tsumo in (False, True):
                        cases["points"].append([mode, unit, fu, han, dealer, tsumo, list(S.total_points(fu, han, 0, dealer, tsumo, 3, sc))])
cases["sc3"] = OPT.sc3("loss")
# 子のツモの払いの表（関西の三人打ち）：表のある点・無い点、役満
cases["table_points"] = []
_sc_k = R.normalize(R.find(name="kansai-3p"))["game_rules"]["scoring"]
for _sc in (_sc_k, dict(_sc_k, round_to=100)):
    for fu in (20, 25, 30, 40, 50, 70):
        for han in range(1, 15):
            for ym in (0, 1):
                for dealer in (False, True):
                    for tsumo in (False, True):
                        cases["table_points"].append({"sc": _sc, "args": [fu, han, ym, dealer, tsumo], "want": list(S.total_points(fu, han, ym, dealer, tsumo, 3, _sc))})
# 足し算の点数：設定の組み合わせ × 翻・役満・親・本場・カラス
cases["additive"] = []
_sc_add = R.normalize(R.find(name="toutenkou-3p"))["game_rules"]["scoring"]
for _ad in ({}, {"honba_dealer_only": False}, {"base": 1, "dealer": 1, "multiplier": 4, "round_to": 10, "honba_dealer_only": False}, {"per_han": 2, "yakuman": 30, "karasu": {"menzen": 30, "open": 20}}):
    _sc = dict(_sc_add, additive=dict(_sc_add["additive"], **_ad))
    for han in (0, 1, 3, 8, 13):
        for ym in (0, 1, 2):
            for dealer in (False, True):
                for honba in (0, 2):
                    for karasu in (None, "menzen", "open"):
                        each, parts = S.additive_points(han, ym, dealer, honba, karasu, _sc)
                        cases["additive"].append({"sc": _sc, "args": [han, ym, dealer, honba, karasu], "want": [each, parts]})

# 和了止め・聴牌止めの選択
cases["choices"] = []
for name in ("jantama-4p", "marchao-4p", "sakae-shibuya", "tenhou-4p-hanchan-red"):
    rs = R.find(name=name)
    for sc in (OPT.TestStopOrContinue.TOP, OPT.TestStopOrContinue.SECOND, OPT.TestStopOrContinue.LAST):
        for kind in ("win", "draw"):
            for answer in (None, True, False):
                why = OPT.last_round(rs, sc, kind, None if answer is None else (lambda k, s, x, a=answer: a))
                cases["choices"].append({"rs": name, "scores": sc, "kind": kind, "answer": answer, "why": why})

with open(os.path.join(OUT, "cases.json"), "w", encoding="utf-8") as f:
    json.dump(cases, f, ensure_ascii=False, separators=(",", ":"))
print(f"cases.json（終わり方 {len(cases['next_state'])}、聴牌 {len(cases['tenpai_waits'])}）")
print(f"js/testdata/games.jsonl（対局 {n}、{os.path.getsize(os.path.join(OUT, 'games.jsonl'))} バイト）、selfplay.json（{len(sp)} 対局）")
