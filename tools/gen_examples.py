"""examples/ の見本一式（牌表・ルール・牌山・対局・評価の 5 層 1 組）を作る。

ライブラリ自身で 1 対局を進めて作る：同梱ルール nm-2p-4-mps（4 枚麻雀、萬子・筒子・索子 108 枚、2 人、東南戦）を、
同梱の打ち手 simple 同士で打つ。山は種から作る（fy-sha256-v1）。種と打ち手が決まっているので、何度作っても同じ id になる。

使い方: python3 tools/gen_examples.py  → examples/ に 牌表 1・ルール 1・牌山（局の数）・対局 1・評価 1 と README.md（英語。日本語の文書があるときは日本語の README も）
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from nmahjong import annotation as A, bots as B, dealer as D, evaluate as E, files, gateway as GW, record as REC, ruleset as R, tileset as TS, wall as W  # noqa: E402

OUT = os.path.join(ROOT, "examples")
RULESET = "nm-2p-4-mps"
BOT = "simple"
STARTED = "2026-11-18T10:00:00+09:00"
ENDED = "2026-11-18T10:30:00+09:00"


def seed_of(k: int) -> str:
    """k 局目の山の種。秒まで入れた日時（時差付き ISO 8601）。"""
    return f"2026-11-18T10:{k // 60:02d}:{k % 60:02d}+09:00"


def main():
    rs = R.find(name=RULESET)
    ts = TS.find(id=rs["tileset"]["id"])
    M = R.normalize(rs)["players"]
    d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.BOTS[BOT], wants_events=False) for s in range(M)},
                 player_info=[{"seat": s, "name": BOT, "external": []} for s in range(M)])
    live = E.LiveAnnotator(rs, ts, run_at=ENDED).attach(d.rc)        # 打牌が届くたびに評価を付ける
    try:
        rec = d.play(lambda k, st: W.build(ts, seed_of(k)), started_at=STARTED, ended_at=ENDED)
    finally:
        d.gw.close()
    ann = live.finish(rec)
    walls = [d.walls[rd["wall"]["id"]] for rd in rec["rounds"]]
    wmap = {w["id"]: w for w in walls}
    warns = REC.validate(rec, rs, ts, wmap)
    A.validate(ann, rec, rs, ts, wmap)
    assert E.annotate(rec, rs, ts, wmap, run_at=ENDED)["id"] == ann["id"]      # まとめて付けた評価と同じ
    for fn in os.listdir(OUT):
        if fn.endswith(".json"):
            os.remove(os.path.join(OUT, fn))
    files.save(ts, OUT, TS.filename(ts))
    files.save(rs, OUT, R.filename(rs))
    for w in walls:
        files.save(w, OUT, W.filename(w), pretty=False)
    files.save(rec, OUT, REC.filename(rec, rs), pretty=False)
    files.save(ann, OUT, A.filename(ann), pretty=False)
    rows = "\n".join(f"| 牌山 | `{W.filename(w)}` | {i + 1} 局目の山（source generated、種 `{w['generation']['seed']}`） |" for i, w in enumerate(walls))
    wins = sum(len(rd["result"]["wins"]) for rd in rec["rounds"])
    rows_en = "\n".join(f"| wall | `{W.filename(w)}` | The wall of round {i + 1} (source generated, seed `{w['generation']['seed']}`) |" for i, w in enumerate(walls))
    # 日本語の文書があるとき（docs/ に日本語の一覧があるとき）だけ、日本語版への行と日本語の README を作る
    HAS_JA = os.path.exists(os.path.join(ROOT, "docs", "README_JA.md"))
    JA_LINK = "\n日本語版：[README_JA.md](README_JA.md)\n" if HAS_JA else ""
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"""# examples — a full set of samples (five layers)
{JA_LINK}
One game run by the library itself: the bundled ruleset `{RULESET}` (4-tile mahjong; 108 tiles of characters, dots and bamboo; two players; east-south), played between the bundled players `{BOT}`.
{len(rec['rounds'])} rounds ({wins} wins, {len(rec['rounds']) - wins} draws), final points {rec['final']['scores']}.

| Layer | File | Content |
|---|---|---|
| tileset | `{TS.filename(ts)}` | 108 tiles of characters, dots and bamboo, no red tiles |
| ruleset | `{R.filename(rs)}` | {rs['name']} (bundled; docs/rules/nm-defaults.md §2) |
{rows_en}
| record | `{REC.filename(rec, rs)}` | The record made by the game runner (dealer), which dealt the walls and added the players' actions one by one |
| annotation | `{A.filename(ann)}` | The bundled evaluator nm-waits (the number of kinds of waiting tiles for each discard), made each time a discard arrived |

- How it is made: `python3 tools/gen_examples.py` (the seeds and the players are fixed, so the ids are the same however many times it is made)
- Verification: `python3 -m nmahjong validate examples/*.json` (references are looked up in the same folder, and the cross-layer checks pass)
- An example of running a game with the command: `python3 -m nmahjong play {RULESET} --seed demo --annotate --out /tmp/out` (the seed differs, so it is a different game)
""")
    if HAS_JA:
      with open(os.path.join(OUT, "README_JA.md"), "w", encoding="utf-8") as f:
        f.write(f"""# examples — 見本一式（5 層）

English: [README.md](README.md)

ライブラリ自身で進めた 1 対局：同梱ルール `{RULESET}`（4 枚麻雀、萬子・筒子・索子 108 枚、2 人、東南戦）を、同梱の打ち手 `{BOT}` 同士で打ったもの。
{len(rec['rounds'])} 局（和了 {wins}・流局 {len(rec['rounds']) - wins}）、最終の持ち点 {rec['final']['scores']}。

| 層 | ファイル | 中身 |
|---|---|---|
| 牌表 | `{TS.filename(ts)}` | 萬子・筒子・索子 108 枚、赤なし |
| ルール | `{R.filename(rs)}` | {rs['name']}（同梱。docs/rules/nm-defaults_JA.md §2） |
{rows}
| 対局 | `{REC.filename(rec, rs)}` | 進行役（dealer）が山を配り、打ち手の行動を 1 つずつ積んで作った対局 |
| 評価 | `{A.filename(ann)}` | 同梱評価器 nm-waits（打牌ごとの待ちの種類数）。打牌が届くたびに付けたもの |

- 作り方：`python3 tools/gen_examples.py`（種と打ち手が決まっているので、何度作っても同じ id）
- 検証：`python3 -m nmahjong validate examples/*.json`（同じフォルダの参照先を探して層またぎまで通る）
- 同じ対局をコマンドで進める例：`python3 -m nmahjong play {RULESET} --seed demo --annotate --out /tmp/out`（種が違うので別の対局になる）
""")
    print("examples/", sorted(fn for fn in os.listdir(OUT) if fn.endswith(".json")), "warnings:", warns)


if __name__ == "__main__":
    main()
