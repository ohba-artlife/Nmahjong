"""同梱ルールを全部、同梱の簡単な打ち手同士で 2 対局ずつ進める：最後まで終わるか、できた対局が検証を通るか。
python3 tools/selfplay_all.py [ルール名 …]
まだ従えない設定があるルールは、代わりの扱い（docs/programs/dealer.md §4）で進める。代わりの扱いが無いルールは「始めない」と出す。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nmahjong import bots as B, dealer as D, gateway as GW, record as REC, ruleset as R, tileset as TS, wall as W  # noqa: E402
from nmahjong.canon import ValidationError  # noqa: E402

names = sys.argv[1:]
done = refused = bad = 0
for rs in sorted(R.bundled(), key=lambda x: x["name"]):
    if names and rs["name"] not in names:
        continue
    ts = TS.find(id=rs["tileset"]["id"])
    M = R.normalize(rs)["players"]
    out = []
    for g in range(2):
        try:
            d = D.Dealer(rs, ts, players={s: GW.FunctionPlayer(B.BOTS["simple"], wants_events=False) for s in range(M)}, allow_unsupported=True)
        except ValidationError:
            out.append("始めない")
            refused += 1
            continue
        try:
            rec = d.play(lambda k, st: W.build(ts, f"all-{rs['name']}-{g}-{k}"))
            warns = REC.validate(rec, rs, ts, d.walls)
        except ValidationError as e:
            out.append(f"止まった：{str(e)[:80]}")
            bad += 1
            continue
        out.append(f"{len(rec['rounds'])} 局（{d.log[-1]}）" + (f" 検証の注意 {len(warns)}" if warns else ""))
        done += not warns
        bad += bool(warns)
    print(f"{rs['name']:28} {' ／ '.join(out)}" + (f"  ※ {'／'.join(D.unsupported(rs))}" if D.unsupported(rs) else ""), flush=True)
print(f"終わって検証を通った対局 {done}、始めない {refused}、止まった・注意あり {bad}")
