"""T7-2：examples/ の 5 層（ライブラリ自身で進めた 4 枚麻雀の 1 対局）が CLI の validate（層またぎ込み）を全部通り、
tools/gen_examples.py で作り直しても同じファイル（同じ id）になる。"""
import json
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "examples")


def snapshot():
    """examples/ の全ファイルの中身（名前 → バイト列）。"""
    out = {}
    for fn in sorted(os.listdir(EX)):
        p = os.path.join(EX, fn)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                out[fn] = f.read()
    return out


@unittest.skipUnless(os.path.isdir(EX), "examples なし")
class TestExamples(unittest.TestCase):
    def test_validate_all(self):
        files = sorted(fn for fn in os.listdir(EX) if fn.endswith(".json"))
        with open(os.path.join(EX, next(f for f in files if f.endswith(".record.json"))), encoding="utf-8") as fh:
            rec = json.load(fh)
        self.assertEqual(len(files), 4 + len(rec["rounds"]))     # 牌表 1・ルール 1・牌山（局の数）・対局 1・評価 1
        kinds = {fn.split(".")[-2] for fn in files}
        self.assertEqual(kinds, {"tileset", "ruleset", "wall", "record", "annotation"})
        r = subprocess.run([sys.executable, "-m", "nmahjong", "validate"] + [os.path.join(EX, f) for f in files],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count(": OK"), len(files), r.stdout)
        self.assertNotIn("未照合", r.stdout)      # 参照先が同じフォルダにあるので層またぎまで行う

    def test_regenerating_gives_the_same_files(self):
        before = snapshot()
        keep = os.path.join(ROOT, "examples.keep")
        shutil.copytree(EX, keep)
        try:
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_examples.py")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            after = snapshot()
            self.assertEqual(sorted(before), sorted(after))
            for fn in before:
                self.assertEqual(before[fn], after[fn], fn)
        finally:
            shutil.rmtree(EX)
            shutil.move(keep, EX)


if __name__ == "__main__":
    unittest.main()
