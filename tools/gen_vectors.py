#!/usr/bin/env python3
"""適合性のテストベクタ tests/vectors/conformance.json を、参照実装（Python）から作る。

別の言語で実装する人が、同じ入力から同じ出力（同じ id）になることを確かめるための入力と期待値。
Python は tests/test_vectors.py、JavaScript は js/test.js が、このファイルを読んで計算し直す（docs/conformance.md）。
"""
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nmahjong import canon as C, ruleset as R, tileset as TS, wall as W  # noqa: E402

OUT = os.path.join(ROOT, "tests", "vectors", "conformance.json")

CANON_VALUES = [
    {},
    [],
    {"b": 1, "a": 2},
    {"a": [3, 2, 1], "b": {"d": None, "c": True}},
    {"n": 1.0, "m": -2.0, "x": 1.5, "z": 0},
    {"name": "東風戦", "tiles": ["1m", "中"]},
    {"s": "a\"b\\c\n", "t": ""},
    [{"id": 0, "kind": "1m"}, {"id": 1, "kind": "1m", "mark": "red"}],
    {"nested": {"deep": {"list": [1, [2, [3, {"k": False}]]]}}},
]
WALLS = [("mpsz", "2026-11-11T10:00:00+09:00"), ("mpsz-nored", "2026-11-11T10:00:00+09:00"), ("mpsz-x28", "sanma-1"),
         ("mps", "seed with spaces"), ("m", "種"), ("mpsz-e8", "2026-01-01T00:00:00Z")]
SHUFFLES = [(1, "a"), (2, "a"), (10, "a"), (10, "b"), (136, "2026-11-11T10:00:00+09:00"), (256, "max")]


def build() -> dict:
    v = {"format": "nmahjong-conformance-vectors", "version": "1.0",
         "note": "参照実装（Python）から tools/gen_vectors.py で作る。手で編集しない。説明は docs/conformance.md"}
    v["canonical_json"] = [{"value": x, "canonical": C.canonical_json(x).decode("utf-8"), "id": C.sha256_id(x)} for x in CANON_VALUES]
    v["fy_sha256_v1"] = []
    for n, seed in SHUFFLES:
        order = W.fy_sha256_v1(list(range(n)), seed)
        e = {"n": n, "seed": seed, "sha256_of_bytes": hashlib.sha256(bytes(order)).hexdigest()}
        if n <= 10:
            e["order"] = order
        else:
            e["head"] = order[:8]
        v["fy_sha256_v1"].append(e)
    defs = TS.bundled_definitions()
    v["tilesets"] = []
    for f in sorted(glob.glob(os.path.join(ROOT, "nmahjong", "data", "tilesets", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            ts = json.load(fh)
        v["tilesets"].append({"file": os.path.relpath(f, ROOT).replace(os.sep, "/"), "name": ts["name"], "K": len(ts["tiles"]), "id": TS.compute_id(ts)})
    v["walls"] = []
    for key, seed in WALLS:
        ts = TS.build(**defs[key])
        w = W.build(ts, seed)
        v["walls"].append({"tileset": {"name": ts["name"], "id": ts["id"]}, "seed": seed, "head": w["order"][:8], "tail": w["order"][-4:],
                           "sha256_of_bytes": hashlib.sha256(bytes(w["order"])).hexdigest(), "id": w["id"]})
    v["rulesets"] = []
    for f in sorted(glob.glob(os.path.join(ROOT, "nmahjong", "data", "rulesets", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            rs = json.load(fh)
        v["rulesets"].append({"file": os.path.relpath(f, ROOT).replace(os.sep, "/"), "name": rs["name"], "id": R.compute_id(R.normalize(rs))})
    return v


def dumps(v: dict) -> str:
    return json.dumps(v, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    s = dumps(build())
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(s)
    v = json.loads(s)
    print(f"{os.path.relpath(OUT, ROOT)}（正規化 JSON {len(v['canonical_json'])}、混ぜ方 {len(v['fy_sha256_v1'])}、牌表 {len(v['tilesets'])}、牌山 {len(v['walls'])}、ルール {len(v['rulesets'])}）")
