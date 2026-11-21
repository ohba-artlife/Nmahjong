"""対戦場（5 層）：打ち手同士を何対局も戦わせて、強さを数字にする。

    table = arena.run(rs, ts, {"A": lambda: FunctionPlayer(bots.simple), "B": lambda: ProcessPlayer(["python3", "my_ai.py"])}, games=20, seed="s1")

- 1 つの「組」＝同じ山の並びを、席を 1 つずつずらして M 回打つ（mirror=True。配牌の運を打ち手の間でならす）。games は組の数
- 出場者が M 人より多いときは、M 人の組み合わせを順に回す
- 結果：出場者ごとの対局数・平均順位・順位の内訳・平均の最終持ち点・平均の精算・和了率・放銃率・立直率・目安のレーティング
- 山は種（seed）から作るので、同じ種・同じ打ち手なら同じ結果になる

ここにあるのは「決めた数の対局を回して集計する」ところまで。常時つないで相手を探す（マッチング）・利用者の管理は、ライブラリの外（サーバー）の役目。
"""
import itertools
from typing import Callable, Dict, List, Optional

from . import dealer as D, record as REC, ruleset as R, wall as W


def _elo_update(rating: Dict[str, float], names: List[str], ranks: List[int], k: float = 16.0) -> None:
    """順位から、2 人ずつの勝ち負けに分けて Elo を動かす（目安）。"""
    M = len(names)
    delta = {n: 0.0 for n in names}
    for i in range(M):
        for j in range(i + 1, M):
            a, b = names[i], names[j]
            if a == b:
                continue
            ea = 1.0 / (1.0 + 10 ** ((rating[b] - rating[a]) / 400.0))
            sa = 1.0 if ranks[i] < ranks[j] else 0.0 if ranks[i] > ranks[j] else 0.5
            delta[a] += k / (M - 1) * (sa - ea)
            delta[b] -= k / (M - 1) * (sa - ea)
    for n in delta:
        rating[n] += delta[n]


def run(rs: dict, ts: dict, entrants: Dict[str, Callable[[], object]], games: int = 10, seed: str = "arena", mirror: bool = True,
        strict: bool = False, allow_unsupported: bool = False, on_game: Optional[Callable] = None, annotate: bool = False) -> dict:
    """entrants：名前 → 打ち手を作る関数（対局ごとに新しく作る）。戻り値：{"ruleset", "games", "rounds", "table": [...], "faults"}。
    on_game(rec, walls, names)：1 対局終わるたびに呼ぶ（保存など）。strict=False：壊れた応答は既定の行動に置き換えて続け、回数を faults に数える。"""
    norm = R.normalize(rs)
    M = norm["players"]
    names = list(entrants)
    if len(names) < M:
        raise ValueError(f"出場者が {M} 人に足りない（同じ打ち手を別の名前で並べてよい）")
    combos = list(itertools.combinations(names, M))
    stat = {n: {"name": n, "games": 0, "rank_sum": 0, "ranks": [0] * M, "score_sum": 0, "settled_sum": 0.0, "rounds": 0,
                "wins": 0, "deal_ins": 0, "riichi": 0, "faults": 0} for n in names}
    rating = {n: 1500.0 for n in names}
    total_games = total_rounds = 0
    for g in range(games):
        base = list(combos[g % len(combos)])
        for rot in range(M if mirror else 1):
            seats = base[rot:] + base[:rot] if mirror else base[g % M:] + base[:g % M]
            players = {s: entrants[seats[s]]() for s in range(M)}
            d = D.Dealer(rs, ts, players=players, strict=strict, allow_unsupported=allow_unsupported,
                         player_info=[{"seat": s, "name": seats[s], "external": []} for s in range(M)])
            try:
                rec = d.play(lambda k, st: W.build(ts, f"{seed}-{g}-{k}"))
            finally:
                d.gw.close()
            REC.validate(rec, rs, ts, d.walls)
            total_games += 1
            total_rounds += len(rec["rounds"])
            fin = rec["final"]
            for s in range(M):
                st = stat[seats[s]]
                st["games"] += 1
                st["rank_sum"] += fin["rank"][s]
                st["ranks"][fin["rank"][s] - 1] += 1
                st["score_sum"] += fin["scores"][s]
                st["settled_sum"] += fin["settled"][s]
                st["rounds"] += len(rec["rounds"])
            for rnd in rec["rounds"]:
                for w in rnd["result"]["wins"]:
                    stat[seats[w["who"]]]["wins"] += 1
                    if w["from"] != w["who"]:
                        stat[seats[w["from"]]]["deal_ins"] += 1
                for e in rnd["events"]:
                    if e["t"] == "riichi":
                        stat[seats[e["who"]]]["riichi"] += 1
            for f in d.gw.faults:
                seat = int(f.split("seat ")[1].split()[0])
                stat[seats[seat]]["faults"] += 1
            _elo_update(rating, seats, fin["rank"])
            if on_game:
                on_game(rec, d.walls, seats)
    table = []
    for n in names:
        st = stat[n]
        gm, rd = max(st["games"], 1), max(st["rounds"], 1)
        table.append({"name": n, "games": st["games"], "avg_rank": round(st["rank_sum"] / gm, 3), "ranks": st["ranks"],
                      "avg_score": round(st["score_sum"] / gm, 1), "avg_settled": round(st["settled_sum"] / gm, 2),
                      "win_rate": round(st["wins"] / rd, 4), "deal_in_rate": round(st["deal_ins"] / rd, 4), "riichi_rate": round(st["riichi"] / rd, 4),
                      "rating": round(rating[n], 1), "faults": st["faults"]})
    table.sort(key=lambda r: (r["avg_rank"], -r["avg_settled"], r["name"]))
    return {"ruleset": {"name": rs.get("name"), "id": rs.get("id")}, "seed": seed, "mirror": mirror, "games": total_games, "rounds": total_rounds, "table": table}


def format_table(result: dict) -> str:
    M = len(result["table"][0]["ranks"])
    head = f"{'名前':<14}{'対局':>5}{'平均順位':>8}  {'順位の内訳':<{3 * M + 2}}{'平均持ち点':>10}{'平均精算':>9}{'和了率':>8}{'放銃率':>8}{'立直率':>8}{'目安Rate':>9}"
    lines = [head]
    for r in result["table"]:
        lines.append(f"{r['name']:<16}{r['games']:>5}{r['avg_rank']:>10.3f}  {'-'.join(str(x) for x in r['ranks']):<{3 * M + 6}}{r['avg_score']:>12.0f}{r['avg_settled']:>12.2f}"
                     f"{r['win_rate'] * 100:>9.1f}%{r['deal_in_rate'] * 100:>9.1f}%{r['riichi_rate'] * 100:>9.1f}%{r['rating']:>10.1f}"
                     + (f"  応答の置き換え {r['faults']}" if r["faults"] else ""))
    return "\n".join(lines)
