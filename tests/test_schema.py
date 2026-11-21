"""JSON スキーマ（nmahjong/data/schema/）：同梱データ・examples・実牌譜の取り込み結果が通り、壊したものを断る。jsonschema が無ければ飛ばす。"""
import copy
import glob
import json
import os
import unittest

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
SCHEMA = os.path.join(ROOT, "nmahjong", "data", "schema")


@unittest.skipUnless(jsonschema is not None and os.path.isdir(SCHEMA), "jsonschema かスキーマが無い")
class TestSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = {n: load(os.path.join(SCHEMA, f"{n}.schema.json")) for n in ("tileset", "wall", "ruleset", "record", "annotation")}
        for s in cls.S.values():
            jsonschema.Draft202012Validator.check_schema(s)

    def _ok(self, obj, kind):
        jsonschema.validate(obj, self.S[kind])

    def test_bundled_and_examples(self):
        from nmahjong import ruleset as R, tileset as TS
        for ts in TS.bundled():
            self._ok(ts, "tileset")
        for rs in R.bundled():
            self._ok(rs, "ruleset")
        kinds = set()
        for f in glob.glob(os.path.join(ROOT, "examples", "*.json")):
            o = load(f)
            kind = o["format"].split("-")[1]
            self._ok(o, kind)
            kinds.add(kind)
        self.assertEqual(kinds, {"tileset", "ruleset", "wall", "record", "annotation"})      # 見本は 5 層がそろっている

    def test_rejects_broken(self):
        from nmahjong import tileset as TS, wall as W
        ts = TS.find(name="mpsz")
        w = W.build(ts, "x")
        bad = copy.deepcopy(w); bad["order"][0] = bad["order"][1]           # uniqueItems
        with self.assertRaises(jsonschema.ValidationError):
            self._ok(bad, "wall")
        bad = copy.deepcopy(w); bad["source"] = "guessed"
        with self.assertRaises(jsonschema.ValidationError):
            self._ok(bad, "wall")
        bad = copy.deepcopy(ts); bad["tiles"][0]["id"] = -1
        with self.assertRaises(jsonschema.ValidationError):
            self._ok(bad, "tileset")
        from nmahjong import ruleset as R
        rs = copy.deepcopy(R.bundled()[0]); rs["game_rules"]["flow"]["kuikae"] = "sometimes"
        with self.assertRaises(jsonschema.ValidationError):
            self._ok(rs, "ruleset")
        rs = copy.deepcopy(R.bundled()[0]); rs["game_rules"]["bogus"] = 1
        with self.assertRaises(jsonschema.ValidationError):
            self._ok(rs, "ruleset")


if __name__ == "__main__":
    unittest.main()
