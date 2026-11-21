"""天鳳の牌譜を使う試験の入口。牌譜はこのリポジトリに同梱しない（天鳳の規約）。

牌譜（mjlog の XML。拡張子 .xml／.mjlog）を次のどれかに置くと、tests/test_tenhou_logs.py が動く。無ければその試験は飛ばす。
  1. tests/data/tenhou/
  2. 環境変数 NMAHJONG_TENHOU_LOGS で指したフォルダ
  3. internal/tenhou/（開発用。公開版には無い）
期待値（牌譜の名前 → 取り込んだ対局の id など）は、同じフォルダの expected.json に書ける。あれば突き合わせる。
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def log_dirs():
    out = [os.path.join(HERE, "data", "tenhou")]
    if os.environ.get("NMAHJONG_TENHOU_LOGS"):
        out.append(os.environ["NMAHJONG_TENHOU_LOGS"])
    out.append(os.path.join(ROOT, "internal", "tenhou"))
    return [d for d in out if os.path.isdir(d)]


def logs():
    """見つかった牌譜のパス（小さい順）。同じ名前は最初に見つかったものだけ。"""
    seen, out = set(), []
    for d in log_dirs():
        for p in sorted(glob.glob(os.path.join(d, "*.xml")) + glob.glob(os.path.join(d, "*.mjlog"))):
            if os.path.basename(p) not in seen:
                seen.add(os.path.basename(p))
                out.append(p)
    return sorted(out, key=os.path.getsize)


def expected():
    """期待値 {牌譜の名前（拡張子なし）: {...}}。各フォルダの expected.json を合わせたもの。"""
    out = {}
    for d in log_dirs():
        p = os.path.join(d, "expected.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    out.setdefault(k, v)
    return out


def ref_of(path):
    return os.path.splitext(os.path.basename(path))[0]
