"""試験用の 13 枚麻雀の対局 tests/data/corpus/selfplay-13.jsonl を作る。

ライブラリ自身の進行役（dealer）で、鳴く打ち手同士に打たせた対局。山は種から作り（fy-sha256-v1）、打ち手の判断も種から決まるので、
何度作っても同じ対局（同じ id）になる。四麻（tenhou-4p-hanchan-red）と三麻（tenhou-3p、抜きドラあり）を 1 つずつ。
チー・ポン・暗槓・加槓／大明槓・立直・ツモ・ロン・流局を含むように種を選んである（下の GAMES）。

使い道：対局の検証・局面と合法手・評価・記録係・接続口・進行役の試験の材料（tests/corpus.py の sp_games）。
このライブラリが作った対局なので、役や点数の正しさの独立した裏づけにはならない（それは tests/data/corpus/nm-engine.jsonl と、
利用者が置く天鳳の牌譜で確かめる。tests/data/tenhou/README.md）。

使い方: python3 tools/gen_test_games.py            GAMES の種で作り直す
        python3 tools/gen_test_games.py --search N  条件に合う種を 0〜N−1 から探して表示する（種を選び直すとき）
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from nmahjong import bots as B, dealer as D, gateway as GW, record as REC, ruleset as R, tileset as TS, wall as W  # noqa: E402

OUT = os.path.join(ROOT, "tests", "data", "corpus", "selfplay-13.jsonl")
GAMES = [("tenhou-4p-hanchan-red", 49), ("tenhou-3p", 17)]        # （同梱ルールの名前、種の番号）
# 鳴く・宣言する確率（残りは見送り）。打牌は同梱の打ち手 simple と同じ（孤立した牌から）
RATES = {"reach": 0.9, "nukidora": 0.9, "ankan": 0.6, "kakan": 0.6, "daiminkan": 0.4, "pon": 0.3, "chi": 0.2, "ryukyoku": 1.0}


def caller(seed: str):
    """種で判断が決まる打ち手。和了れるなら和了。立直・抜き・カン・ポン・チー・九種九牌は RATES の確率で行う。"""
    n = [0]

    def fn(msg):
        acts = msg["request"]["possible_actions"]
        hora = next((a for a in acts if a["type"] == "hora"), None)
        if hora is not None:
            return hora
        for t in ("reach", "nukidora", "ankan", "kakan", "daiminkan", "pon", "chi", "ryukyoku"):
            a = next((a for a in acts if a["type"] == t), None)
            if a is None:
                continue
            n[0] += 1
            x = int.from_bytes(hashlib.sha256(f"{seed}|{n[0]}".encode()).digest()[:8], "big") / 2 ** 64
            if x < RATES[t]:
                return a
        return B.simple(msg)
    return fn


def play(name: str, k: int):
    rs = R.find(name=name)
    ts = TS.find(id=rs["tileset"]["id"])
    M = R.normalize(rs)["players"]
    seed = f"selfplay-13/{name}/{k}"
    d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(caller(f"{seed}/seat{s}"), wants_events=False) for s in range(M)},
                 player_info=[{"seat": s, "name": "caller", "external": []} for s in range(M)])
    try:
        rec = d.play(lambda i, st: W.build(ts, f"{seed}/round{i}"))
    finally:
        d.gw.close()
    walls = [d.walls[rd["wall"]["id"]] for rd in rec["rounds"]]
    return rec, walls, rs, ts


def features(rec, rs) -> dict:
    """試験が当てにしている出来事が入っているか。"""
    evs = [e for rd in rec["rounds"] for e in rd["events"]]
    wins = [w for rd in rec["rounds"] for w in rd["result"]["wins"]]
    start = R.normalize(rs)["settlement"]["start_points"] * R.normalize(rs)["players"]
    last = rec["rounds"][-1]["result"]["scores"]
    return {"rounds": len(rec["rounds"]),
            "first_round_win": bool(rec["rounds"][0]["result"]["wins"]),
            "chi": sum(e["t"] == "chi" for e in evs), "pon": sum(e["t"] == "pon" for e in evs),
            "ankan": sum(e["t"] == "kan" and e["kind"] == "ankan" for e in evs),
            "other_kan": sum(e["t"] == "kan" and e["kind"] != "ankan" for e in evs),
            "nuki": sum(e["t"] == "nuki" for e in evs), "riichi": sum(e["t"] == "riichi" for e in evs),
            "tsumo": sum(w["from"] == w["who"] for w in wins), "ron": sum(w["from"] != w["who"] for w in wins),
            "draws": sum(not rd["result"]["wins"] for rd in rec["rounds"]),
            "leftover_sticks": (start - sum(last)) // 1000}


def wanted(name: str, f: dict) -> bool:
    ok = (5 <= f["rounds"] <= 12 and f["first_round_win"] and f["pon"] and f["ankan"] and f["other_kan"] and f["riichi"] >= 3
          and f["tsumo"] and f["ron"] and f["draws"])
    if name == "tenhou-3p":
        return ok and f["nuki"] >= 3
    return ok and f["chi"] >= 3 and f["leftover_sticks"] > 0


def main(argv):
    if argv[:1] == ["--search"]:
        for name in sorted({g[0] for g in GAMES}):
            for k in range(int(argv[1])):
                rec, walls, rs, ts = play(name, k)
                f = features(rec, rs)
                if wanted(name, f):
                    print(name, k, f)
        return 0
    n = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for name, k in GAMES:
            rec, walls, rs, ts = play(name, k)
            f = features(rec, rs)
            assert wanted(name, f), (name, k, f)
            assert REC.validate(rec, rs, ts, {w["id"]: w for w in walls}) == []
            out.write(json.dumps({"ruleset": rs, "walls": walls, "record": rec}, ensure_ascii=False, separators=(",", ":")) + "\n")
            print(f"  {name} 種 {k}: {f}")
            n += 1
    print(f"tests/data/corpus/selfplay-13.jsonl：対局 {n}、{os.path.getsize(OUT)} バイト")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
