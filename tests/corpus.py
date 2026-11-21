"""試験用の対局の集まり（tests/data/corpus/）。Nmahjong の形式（ルール・牌山・対局）で 1 行 1 対局。

nm-engine.jsonl：N 枚麻雀（1 枚・4 枚、2 人）の対局 50。このライブラリとは別に作られた対局エンジン（N 枚麻雀のアプリ）が
CPU 同士で打ったものを、Nmahjong の形式に変換して置いたもの。天和・地和・人和・二倍役満・流局・嶺上開花・海底・
1 局 2 回の暗槓・途中から打ち直した対局（parent あり）を含む。ルールは同梱の nm-* と、その変種
（-stays＝終局時の供託を卓に残す、-ronstick＝立直の宣言牌でロンされても立直棒を出す）。
別の実装が作った結果と、このライブラリの判定・進行・検証が一致することを確かめるのに使う。

selfplay-13.jsonl：13 枚麻雀の対局 2（四麻 tenhou-4p-hanchan-red、三麻 tenhou-3p）。ライブラリ自身の進行役で、鳴く打ち手同士に
打たせたもの（tools/gen_test_games.py。種が決まっているので何度作っても同じ id）。チー・ポン・カン・抜きドラ・立直・流局を含む。
対局の検証・局面と合法手・評価などの試験の材料。このライブラリが作った対局なので、役や点数の独立した裏づけにはならない。
"""
import json
import os

from nmahjong import tileset as TS

HERE = os.path.dirname(os.path.abspath(__file__))
NM_ENGINE = os.path.join(HERE, "data", "corpus", "nm-engine.jsonl")
SELFPLAY_13 = os.path.join(HERE, "data", "corpus", "selfplay-13.jsonl")
_cache = {}


def _load(path):
    if path not in _cache:
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                rs = d["ruleset"]
                ts = next((t for t in TS.bundled() if t["id"] == rs["tileset"]["id"]), None) or TS.build(rs["tileset"]["name"])
                assert ts["id"] == rs["tileset"]["id"], rs["name"]
                out.append((d["record"], d["walls"], rs, ts))
        _cache[path] = out
    return _cache[path]


def nm_games(hand_size=None):
    """N 枚麻雀の対局の一覧 [(record, walls, ruleset, tileset), …]。hand_size（1／4）を渡すとその枚数だけ。
    試験が書き換えても元が壊れないよう、呼ぶたびに写しを返す。"""
    import copy
    return [copy.deepcopy(g) for g in _load(NM_ENGINE) if hand_size is None or g[2]["hand_size"] == hand_size]


def sp_games(ruleset_name=None):
    """13 枚麻雀の対局の一覧 [(record, walls, ruleset, tileset), …]。ruleset_name を渡すとそのルールの対局だけ。"""
    import copy
    return [copy.deepcopy(g) for g in _load(SELFPLAY_13) if ruleset_name is None or g[2]["name"] == ruleset_name]


def sp_game(ruleset_name="tenhou-4p-hanchan-red"):
    """13 枚麻雀の対局 1 つ (record, walls, ruleset, tileset)。既定は四麻（チー・ポン・カン・立直・流局・終局時の供託あり）。"""
    return sp_games(ruleset_name)[0]


def rob_ankan_game(ruleset_name, kokushi=True):
    """暗槓の牌へのロン（国士無双の槍槓）を確かめるための、山を組んだ対局 (record, walls, ruleset, tileset)。
    第 1 局：親（席 0）が最初のツモで暗槓する。席 1 はその牌で和了れる形で待っている。
    kokushi=True なら席 1 は国士無双（東待ち。親は東を暗槓）、False なら普通の形（3m・6m 待ち。親は 3m を暗槓）。
    打ち手は「和了れるなら和了る、暗槓できるならする、あとはツモ切り」。第 2 局から先の山は種から作る。"""
    from nmahjong import bots as B, dealer as D, gateway as GW, ruleset as R, wall as W
    rs = R.find(name=ruleset_name)
    ts = TS.find(id=rs["tileset"]["id"])
    by = {}
    for i, t in enumerate(ts["tiles"]):
        by.setdefault(t["kind"], []).append(i)
    if kokushi:
        kan = by["E"]
        s0 = kan[:3] + [by[k][0] for k in ("2m", "5m", "8m", "2p", "5p", "8p", "2s", "5s", "8s", "3m")]
        s1 = [by["1m"][0], by["1m"][1]] + [by[k][0] for k in ("9m", "1p", "9p", "1s", "9s", "S", "W", "N", "P", "F", "C")]
    else:
        kan = by["3m"]
        s0 = kan[:3] + [by[k][0] for k in ("1s", "5s", "9s", "E", "S", "W", "N", "P", "F", "C")]
        s1 = [by[k][0] for k in ("4m", "5m", "7m", "8m", "9m", "1p", "2p", "3p", "4p", "5p", "6p")] + by["7s"][:2]
    rest = [t for t in range(len(ts["tiles"])) if t not in set(s0 + s1 + [kan[3]])]
    order = s0 + s1 + rest[:26] + [kan[3]] + rest[26:]

    def bot(msg):
        acts = msg["request"]["possible_actions"]
        for t in ("hora", "ankan"):
            a = next((a for a in acts if a["type"] == t), None)
            if a is not None:
                return a
        return B.tsumogiri(msg)

    d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(bot, wants_events=False) for s in range(4)})
    rec = d.play(lambda k, st: W.build_observed(ts, order) if k == 0 else W.build(ts, f"rob-ankan/{ruleset_name}/{k}"))
    return rec, list(d.walls.values()), rs, ts
