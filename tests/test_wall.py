"""試験 T2 牌山、T6-1 天鳳の山の作り方（実牌譜との一致は test_tenhou_logs.py）。"""
import copy
import unittest

from nmahjong import tileset as TS, wall as W
from nmahjong.canon import ValidationError
from nmahjong.tenhou import shuffle as TH

VECTOR_SEED = "2026-11-11T10:00:00+09:00"
VECTOR_ORDER = [111,48,119,67,76,94,38,1,26,86,49,40,32,37,112,22,83,61,70,7,44,4,124,75,109,47,91,33,100,58,108,23,59,126,50,85,52,0,2,39,18,87,68,73,28,65,5,57,19,98,31,97,8,80,3,125,104,79,30,134,29,41,84,36,56,53,127,13,123,130,114,115,45,90,43,69,103,62,54,10,6,110,9,92,42,131,121,12,51,15,20,25,93,63,89,96,128,102,71,78,88,95,46,27,74,101,113,116,66,35,24,72,133,122,81,117,17,14,34,118,82,120,21,105,107,77,55,129,64,135,132,99,16,11,60,106]
VECTOR_ID = "sha256:3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c"
# 作りものの種で作った山（四麻 3 局・三麻 3 局）の「天鳳の向きの並びの sha256 先頭 : サイコロ : 山の id 先頭」
EXPECTED_MADE_UP = [
    "9bf9994da6901f2a:54:4a606e1ffcd3c9ac",
    "bd1d992d7fb4f192:51:3d7cdf6958ed2972",
    "ee23eaae50d572ad:21:788debd330047dfc",
    "f163f5d1b1262e62:54:5f19468d1067ef3e",
    "db4803c03a8ffa80:51:89b07f08113985c5",
    "5a6fbe5b04fd5a51:21:18c2e5fca069b112",
]


class TestWall(unittest.TestCase):
    def setUp(self):
        self.ts = TS.build(**TS.bundled_definitions()["mpsz"])

    def test_T2_1_vector(self):
        w = W.build(self.ts, VECTOR_SEED)
        self.assertEqual(w["order"], VECTOR_ORDER)
        self.assertEqual(w["id"], VECTOR_ID)
        self.assertEqual(W.validate(w, self.ts), [])

    def test_T2_2_reproducible_and_seed_sensitive(self):
        a = W.build(self.ts, VECTOR_SEED)
        b = W.build(self.ts, VECTOR_SEED)
        c = W.build(self.ts, "2026-11-11T10:00:01+09:00")
        self.assertEqual(a["order"], b["order"])
        self.assertNotEqual(a["order"], c["order"])

    def test_T2_3_small_and_large_K(self):
        for key in ("m-nored", "mpsz-x28", "mpsz-e8"):
            ts = TS.build(**TS.bundled_definitions()[key])
            w = W.build(ts, VECTOR_SEED)
            self.assertEqual(sorted(w["order"]), list(range(TS.K(ts))))
            W.validate(w, ts)

    def test_T2_4_rejects_broken(self):
        w = W.build(self.ts, VECTOR_SEED)
        for mutate in (
            lambda x: x["order"].__setitem__(0, x["order"][1]),            # 重複
            lambda x: x.__setitem__("id", "sha256:" + "0" * 64),            # id 不一致
            lambda x: x["generation"].__setitem__("seed", "x"),             # 再構築不一致
            lambda x: x.__setitem__("source", "observed") or x.pop("generation") and x.__setitem__("fill", {}),
            lambda x: x.__setitem__("device", {"id": "T1"}),                # generated に device
            lambda x: x["order"].pop(),                                      # 長さ
            lambda x: x.__setitem__("extra", 1),
        ):
            bad = copy.deepcopy(w)
            mutate(bad)
            with self.assertRaises(ValidationError):
                W.validate(bad, self.ts)

    def test_T2_5_filled(self):
        placed = {0: 5, 1: 17, 2: 99, 52: 3, 135: 120}
        w = W.build_filled(self.ts, placed, "jantama:test:0")
        self.assertEqual(w["observed"], [[0, 3], [52, 53], [135, 136]])
        self.assertEqual([w["order"][p] for p in placed], list(placed.values()))
        self.assertEqual(W.validate(w, self.ts), [])
        bad = copy.deepcopy(w)
        bad["order"][3], bad["order"][4] = bad["order"][4], bad["order"][3]
        bad["id"] = W.compute_id(bad["order"], self.ts["id"])
        with self.assertRaises(ValidationError):
            W.validate(bad, self.ts)

    def test_T2_6_observed_device(self):
        w = W.build(self.ts, VECTOR_SEED)
        w = {k: v for k, v in w.items() if k != "generation"}
        w["source"] = "observed"
        w["device"] = {"id": "T-0001", "model": "X", "at": "2026-11-13T19:05:31+09:00"}
        self.assertEqual(W.validate(w, self.ts), [])
        w["device"]["role"] = "x"
        with self.assertRaises(ValidationError):
            W.validate(w, self.ts)

    def test_T2_13_id_depends_on_tileset(self):
        nored = TS.build(**TS.bundled_definitions()["mpsz-nored"])
        a = W.build(self.ts, VECTOR_SEED)
        b = W.build(nored, VECTOR_SEED)
        self.assertEqual(a["order"], b["order"], "並びは牌表の印に依らない")
        self.assertNotEqual(a["id"], b["id"], "id は牌表が違えば別")
        self.assertNotEqual(W.filename(a), W.filename(b))

    def test_T2_7_filename_and_representations(self):
        w = W.build(self.ts, VECTOR_SEED)
        self.assertEqual(W.filename(w), "mpsz_" + VECTOR_ID[7:] + ".wall.json")
        self.assertEqual(len(W.to_bytes(w["order"])), 136)
        self.assertEqual(W.to_csv(w["order"]).split(",")[0], "111")
        self.assertEqual(W.from_bytes(W.to_bytes(w["order"])), w["order"])
        self.assertEqual(W.from_csv(W.to_csv(w["order"])), w["order"])


class TestTenhouShuffle(unittest.TestCase):
    """T6-1（牌譜を使わない部分）：天鳳の山の作り方（MT19937 → SHA-512 → 混ぜる → 山の向きの変換）。
    実牌譜との一致は tests/test_tenhou_logs.py（牌譜を置いたときだけ動く）。"""

    def test_mt19937_reference_vector(self):
        # 松本・西村の mt19937ar.c に付いている出力例（init_by_array {0x123, 0x234, 0x345, 0x456} の最初の 5 つ）
        mt = TH.MT19937([0x123, 0x234, 0x345, 0x456])
        self.assertEqual([mt.genrand_int32() for _ in range(5)], [1067595299, 955945823, 477289528, 4107218783, 4228976476])

    def _seed(self):
        import base64
        import hashlib
        raw = b"".join(hashlib.sha256(b"nmahjong-test-seed-%d" % i).digest() for i in range(78))     # 2496 バイト＝624 語
        return TH.PREFIX + base64.b64encode(raw).decode()

    def test_made_up_seed_gives_fixed_walls(self):
        """作りものの種（天鳳の牌譜の種ではない）で、山が変わらないこと・山として正しいことを確かめる。"""
        import hashlib
        seed = self._seed()
        ts4 = TS.find(name="mpsz")
        ts3 = TS.find(name="mpsz-x28")
        got = []
        for players, ts in ((4, ts4), (3, ts3)):
            for k in (0, 1, 7):
                yama, dice = TH.tenhou_wall(seed, k, players)
                self.assertEqual(sorted(yama), sorted(t for t in range(136) if players == 4 or t not in TH.EXCL_3P))
                self.assertTrue(all(0 <= d < 6 for d in dice))
                w = W.build_tenhou(ts, seed, k, k % players, players)
                self.assertEqual(W.validate(w, ts), [])
                self.assertEqual((w["source"], w["generation"]["method"]), ("observed", TH.METHOD))
                got.append(hashlib.sha256(bytes(yama)).hexdigest()[:16] + ":%d%d" % dice + ":" + w["id"][7:23])
        self.assertEqual(got, EXPECTED_MADE_UP)
        # 同じ種・同じ局なら同じ山、局が違えば違う山
        self.assertEqual(TH.tenhou_wall(seed, 3), TH.tenhou_wall(seed, 3))
        self.assertNotEqual(TH.tenhou_wall(seed, 3)[0], TH.tenhou_wall(seed, 4)[0])

    def test_seed_must_be_whole_words(self):
        with self.assertRaises(ValueError):
            TH.parse_seed(TH.PREFIX + "AAAAAAA=")


class TestObservedTags(unittest.TestCase):
    """T2-14（2-3 実卓の入口）：タグ id の列＋対応表 → observed の wall。"""

    def setUp(self):
        from nmahjong import tileset as TS
        self.ts = TS.find(name="mpsz")
        self.K = TS.K(self.ts)
        self.tm = {"format": W.TAGMAP_FORMAT, "version": "1.0", "tileset": TS.ref(self.ts),
                   "tags": {f"E2{i:04X}": i for i in range(self.K)}}

    def test_from_tags(self):
        order = W.fy_sha256_v1(list(range(self.K)), "x")
        tags = [f"E2{t:04X}" for t in order]
        w = W.build_from_tags(self.ts, self.tm, tags, device={"id": "T-0001", "at": "2026-11-16T10:00:00+09:00"})
        self.assertEqual(w["source"], "observed")
        self.assertEqual(w["order"], order)
        self.assertNotIn("generation", w)
        self.assertEqual(W.validate(w, self.ts), [])
        self.assertEqual(w["id"], W.compute_id(order, self.ts["id"]))

    def test_rejects(self):
        from nmahjong.canon import ValidationError
        tags = [f"E2{t:04X}" for t in range(self.K)]
        with self.assertRaises(ValidationError):
            W.build_from_tags(self.ts, self.tm, tags[:-1])             # 不足
        with self.assertRaises(ValidationError):
            W.build_from_tags(self.ts, self.tm, tags[:-1] + ["ZZZZ"])  # 未知
        with self.assertRaises(ValidationError):
            W.build_from_tags(self.ts, self.tm, tags[:-1] + [tags[0]])  # 重複
        bad = dict(self.tm, tags=dict(self.tm["tags"]))
        bad["tags"]["E20001"] = 0                                        # 同じ牌番号に 2 タグ
        with self.assertRaises(ValidationError):
            W.validate_tagmap(bad, self.ts)


if __name__ == "__main__":
    unittest.main()
