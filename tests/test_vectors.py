"""適合性のテストベクタ（tests/vectors/conformance.json、docs/conformance.md）。
同じファイルを JavaScript 版（js/test.js）も読んで計算し直す。ここでは参照実装（Python）が期待値どおりになること、
ファイルが tools/gen_vectors.py の出力そのままであることを確かめる。"""
import hashlib
import json
import os
import sys
import unittest

from nmahjong import canon as C, ruleset as R, tileset as TS, wall as W

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tests", "vectors", "conformance.json")


class TestConformanceVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PATH, encoding="utf-8") as f:
            cls.text = f.read()
        cls.v = json.loads(cls.text)

    def load(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)

    def test_V1_canonical_json_and_id(self):
        self.assertGreaterEqual(len(self.v["canonical_json"]), 9)
        for c in self.v["canonical_json"]:
            self.assertEqual(C.canonical_json(c["value"]).decode("utf-8"), c["canonical"])
            self.assertEqual(C.sha256_id(c["value"]), c["id"])
            self.assertEqual("sha256:" + hashlib.sha256(c["canonical"].encode("utf-8")).hexdigest(), c["id"])

    def test_V2_shuffle(self):
        for c in self.v["fy_sha256_v1"]:
            order = W.fy_sha256_v1(list(range(c["n"])), c["seed"])
            self.assertEqual(sorted(order), list(range(c["n"])))
            self.assertEqual(hashlib.sha256(bytes(order)).hexdigest(), c["sha256_of_bytes"], c)
            self.assertEqual(order[:len(c.get("order", c.get("head")))], c.get("order", c.get("head")))

    def test_V3_tileset_ids(self):
        self.assertEqual(len(self.v["tilesets"]), 10)
        for c in self.v["tilesets"]:
            ts = self.load(c["file"])
            self.assertEqual((TS.compute_id(ts), ts["id"], ts["name"], len(ts["tiles"])), (c["id"], c["id"], c["name"], c["K"]))

    def test_V4_walls(self):
        for c in self.v["walls"]:
            ts = TS.find(id=c["tileset"]["id"])
            w = W.build(ts, c["seed"])
            self.assertEqual((w["id"], w["order"][:8], w["order"][-4:]), (c["id"], c["head"], c["tail"]), c["seed"])
            self.assertEqual(hashlib.sha256(bytes(w["order"])).hexdigest(), c["sha256_of_bytes"])
            self.assertEqual(W.validate(w, ts), [])
        # 仕様書（docs/spec/wall.md §3）に書いてある id と同じ
        self.assertEqual(self.v["walls"][0]["id"], "sha256:3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c")

    def test_V5_ruleset_ids(self):
        self.assertEqual(len(self.v["rulesets"]), 46)
        for c in self.v["rulesets"]:
            rs = self.load(c["file"])
            self.assertEqual((R.compute_id(R.normalize(rs)), rs["id"], rs["name"]), (c["id"], c["id"], c["name"]))

    def test_V6_file_is_generated(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import gen_vectors
        finally:
            sys.path.pop(0)
        self.assertEqual(gen_vectors.dumps(gen_vectors.build()), self.text)


if __name__ == "__main__":
    unittest.main()
