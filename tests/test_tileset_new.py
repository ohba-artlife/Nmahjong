"""牌表を作る（1 層）：コマンド tileset new が、同梱 10 本と同じ指定から同じ id を作る。画面（tools/tilesetgen.html）は同じ JS（js/test.js で確認）。"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

from nmahjong import tileset as TS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args):
    return subprocess.run([sys.executable, "-m", "nmahjong", "tileset", "new", *args], cwd=ROOT, capture_output=True, text=True)


class TestTilesetNew(unittest.TestCase):
    def test_N1_same_ids_as_bundled(self):
        red3 = ["--mark", "5m=red", "--mark", "5p=red", "--mark", "5s=red"]
        sanma = ["--exclude", "2m,3m,4m,5m,6m,7m,8m"]
        specs = {
            "mpsz": ["--colors", "mpsz"] + red3, "mpsz-nored": ["--colors", "mpsz"],
            "mpsz-x28": ["--colors", "mpsz"] + sanma + red3, "mpsz-x28-nored": ["--colors", "mpsz"] + sanma,
            "mpsz-x28-allred": ["--colors", "mpsz"] + sanma + ["--mark", "5p=red,red,red,red", "--mark", "5s=red,red,red,red"],
            "m": ["--colors", "m", "--mark", "3m=red", "--mark", "5m=red", "--mark", "7m=red"], "m-nored": ["--colors", "m"], "mps": ["--colors", "mps"],
            "mpsz-pocchi": ["--colors", "mpsz", "--mark", "5m=red,gold", "--mark", "5p=red,gold", "--mark", "5s=red,gold", "--mark", "P=pocchi,reverse_pocchi"],
            "mpsz-e8": ["--colors", "mpsz"] + red3 + ["--extra", "梅,蘭,菊,竹,春,夏,秋,冬"],
        }
        want = {k: TS.build(**kw)["id"] for k, kw in TS.bundled_definitions().items()}
        self.assertEqual(set(specs), set(want))
        for key, args in specs.items():
            r = run(*args)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(want[key], r.stdout, key)

    def test_N2_new_tileset_is_saved_and_valid(self):
        with tempfile.TemporaryDirectory() as d:
            r = run("--colors", "sp", "--mark", "5p=red,red", "--exclude", "1s", "--extra", "春,夏", "--out", d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            f = glob.glob(os.path.join(d, "*.tileset.json"))
            self.assertEqual(len(f), 1)
            with open(f[0], encoding="utf-8") as fh:
                ts = json.load(fh)
            self.assertEqual((ts["name"], len(ts["tiles"])), ("ps-x4-e2", 70))
            self.assertEqual([t["id"] for t in ts["tiles"] if t.get("mark") == "red"], [16, 17])
            self.assertEqual(TS.validate(ts), [])
            v = subprocess.run([sys.executable, "-m", "nmahjong", "validate", f[0]], cwd=ROOT, capture_output=True, text=True)
            self.assertIn(": OK", v.stdout)

    def test_N4_extras_with_marks_and_rule_functions(self):
        # エクストラ牌（花牌）に印を付け、ルールで機能を持たせる：印 flower＝ドラ、エクストラ牌＝抜きドラ、白の 1 枚＝ポッチ
        from nmahjong import observe as O, recorder as RC, ruleset as R, wall as W
        with tempfile.TemporaryDirectory() as d:
            r = run("--colors", "mpsz", "--mark", "P=pocchi", "--extra", "梅=flower,蘭=flower,菊,竹", "--out", d)
            self.assertIn("sha256:35719497457bf1980500b0995e1d4cac16e1d970e67f4b82922337320ab39acf", r.stdout)
            with open(glob.glob(os.path.join(d, "*.tileset.json"))[0], encoding="utf-8") as fh:
                ts = json.load(fh)
        self.assertEqual([(t["id"], t["name"], t.get("mark")) for t in ts["tiles"] if t["kind"] == "ex"],
                         [(136, "梅", "flower"), (137, "蘭", "flower"), (138, "菊", None), (139, "竹", None)])
        base = R.find(name="tenhou-4p-hanchan-red")
        rs = R.new_from(base, "flower-test", {
            "tileset": TS.ref(ts),
            "game_rules.marks": {"pocchi": {"effects": ["almighty"], "when": {"state": "riichi", "how": "tsumo"}}, "flower": {"effects": ["dora"]}},
            "game_rules.nuki": {"enabled": True, "tiles": ["ex"], "value": 1},
            "wall_rules.dead_wall": 18, "wall_rules.rinshan": [17, 16, 15, 14, 13, 12, 11, 10], "wall_rules.dora_indicator": [8],
            "wall_rules.ura_indicator": [9], "wall_rules.kan_dora": [6, 4, 2, 0], "wall_rules.kan_ura": [7, 5, 3, 1]})
        _, warns = R.validate(rs, ts)
        self.assertFalse([w for w in warns if "mark" in w or "印" in w or "nuki" in w])     # 印・抜きについての警告は無い
        ex = [136, 137, 138, 139]
        rest = [i for i in range(140) if i not in ex]
        order = [ex[0]] + rest[:51] + [ex[1]] + rest[51:-17] + [ex[2], ex[3]] + rest[-17:]     # 親の配牌に梅、第 1 ツモが蘭
        wall = W.build_observed(ts, order)
        rec = RC.Recorder(rs, ts)
        rec.start_round({"bakaze": "E", "kyoku": 1, "honba": 0, "kyotaku": 0, "oya": 0, "scores": [25000] * 4}, wall)
        rec.push({"t": "draw", "who": 0, "tile": ex[1]})
        obs = O.observe(rec.rec, 0, 2, 0, rs, ts, rec.walls)
        nuki = [a["tile"] for a in O.legal_actions(rs, ts, obs, phase="A") if a["type"] == "nuki"]
        self.assertEqual(nuki, [136, 137])                               # 抜けるのは花牌だけ
        rec.push({"t": "nuki", "who": 0, "tile": ex[1]})
        rec.push({"t": "draw", "who": 0, "tile": order[140 - 18 + 17], "rinshan": True})   # 嶺上から補充
        with self.assertRaises(Exception):
            rec.push({"t": "nuki", "who": 0, "tile": rest[0]})           # 花牌でない牌は抜けない
        rec.push({"t": "nuki", "who": 0, "tile": ex[0]})
        self.assertEqual(O.observe(rec.rec, 0, 5, 0, rs, ts, rec.walls)["nuki"][0], [137, 136])

    def test_N3_errors(self):
        for args in (["--colors", "m", "--exclude", "5p"], ["--colors", "m", "--mark", "5p=red"], ["--colors", "m", "--mark", "5m=a,b,c,d,e"], ["--colors", "x"]):
            r = run(*args)
            self.assertNotEqual(r.returncode, 0, args)


if __name__ == "__main__":
    unittest.main()
