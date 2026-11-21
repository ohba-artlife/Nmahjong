"""試験 T1 牌表。"""
import copy
import unittest

from nmahjong import tileset as TS
from nmahjong.canon import ValidationError


class TestTileset(unittest.TestCase):
    def setUp(self):
        self.defs = TS.bundled_definitions()
        self.mpsz = TS.build(**self.defs["mpsz"])

    def test_T1_1_mpsz_matches_tenhou_numbering(self):
        ts = self.mpsz
        self.assertEqual(len(ts["tiles"]), 136)
        self.assertEqual(ts["tiles"][0]["kind"], "1m")
        self.assertEqual(ts["tiles"][35]["kind"], "9m")
        self.assertEqual(ts["tiles"][36]["kind"], "1p")
        self.assertEqual(ts["tiles"][72]["kind"], "1s")
        self.assertEqual(ts["tiles"][108]["kind"], "E")
        self.assertEqual(ts["tiles"][135]["kind"], "C")
        for red in (16, 52, 88):
            self.assertEqual(ts["tiles"][red].get("mark"), "red")
            self.assertEqual(ts["tiles"][red]["kind"][0], "5")

    def test_T1_2_x28_is_108(self):
        ts = TS.build(**self.defs["mpsz-x28"])
        self.assertEqual(len(ts["tiles"]), 108)
        self.assertEqual([t["kind"] for t in ts["tiles"][:8]], ["1m"] * 4 + ["9m"] * 4)
        TS.validate(ts)

    def test_T1_3_all_bundled_validate_and_names(self):
        for key, kw in self.defs.items():
            ts = TS.build(**kw)
            self.assertEqual(TS.validate(ts), [])
            self.assertEqual(TS.expected_count(ts["name"]), len(ts["tiles"]))
            TS.filename(ts)

    def test_T1_4_id_is_hash_of_tiles_only(self):
        a = TS.build(**self.defs["mpsz"])
        b = copy.deepcopy(a)
        b["name"] = "mpsz"  # same
        self.assertEqual(a["id"], b["id"])
        nored = TS.build(**self.defs["mpsz-nored"])
        self.assertEqual(nored["name"], a["name"])
        self.assertNotEqual(nored["id"], a["id"], "印の有無で id は変わる")

    def test_T1_5_rejects_broken(self):
        ts = copy.deepcopy(self.mpsz)
        ts["tiles"][5]["id"] = 99
        with self.assertRaises(ValidationError):
            TS.validate(ts)
        ts = copy.deepcopy(self.mpsz)
        ts["tiles"][5]["kind"] = "10m"
        with self.assertRaises(ValidationError):
            TS.validate(ts)
        ts = copy.deepcopy(self.mpsz)
        ts["name"] = "mps"
        with self.assertRaises(ValidationError):
            TS.validate(ts)
        ts = copy.deepcopy(self.mpsz)
        ts["id"] = "sha256:" + "0" * 64
        with self.assertRaises(ValidationError):
            TS.validate(ts)
        ts = copy.deepcopy(self.mpsz)
        ts["tiles"].append({"id": 136, "kind": "1m"})
        with self.assertRaises(ValidationError):
            TS.validate(ts)

    def test_T1_6_labels(self):
        ts = self.mpsz
        self.assertEqual(TS.tile_label(ts, 0), "1m")
        self.assertEqual(TS.tile_label(ts, 16), "5mr")
        self.assertEqual(TS.tile_label(ts, 16, "z"), "0m")
        self.assertEqual(TS.tile_label(ts, 108), "E")
        self.assertEqual(TS.tile_label(ts, 108, "z"), "1z")
        self.assertEqual(TS.parse_label(ts, "5mr"), [16])
        self.assertEqual(TS.parse_label(ts, "0p"), [52])
        self.assertEqual(TS.parse_label(ts, "1z"), [108, 109, 110, 111])
        self.assertEqual(len(TS.parse_label(ts, "5m")), 4)

    def test_T1_7_extras(self):
        ts = TS.build(**self.defs["mpsz-e8"])
        self.assertEqual(len(ts["tiles"]), 144)
        self.assertEqual(ts["tiles"][136]["kind"], "ex")
        self.assertEqual(TS.tile_label(ts, 136), "ex:梅")
        TS.validate(ts)


if __name__ == "__main__":
    unittest.main()
