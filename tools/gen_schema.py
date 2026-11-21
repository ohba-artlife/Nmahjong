"""5 層の JSON スキーマ（draft 2020-12）を nmahjong/data/schema/ に書き出す。
ruleset のスキーマは Python 実装の既定値・語彙から機械的に作る（手で書くとずれる）。
スキーマは「形」の検査。id の一致・層またぎ・ルール依存の意味（X1〜X14）は validate が正。
使い方: python3 tools/gen_schema.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from nmahjong import record as REC, ruleset as R  # noqa: E402

OUT = os.path.join(ROOT, "nmahjong", "data", "schema")
ID = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
REF = {"type": "object", "required": ["id"], "properties": {"name": {"type": "string"}, "id": ID}}
TILE = {"type": "integer", "minimum": 0}
TILES = {"type": "array", "items": TILE}
NAME = {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"}


def base(title, fmt):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"https://nmahjong.dev/schema/{fmt}.schema.json",
            "title": title, "type": "object", "additionalProperties": False,
            "properties": {"format": {"const": f"nmahjong-{fmt}"}, "version": {"const": "1.0"}, "id": ID}}


def tileset_schema():
    s = base("Nmahjong tileset 1.0", "tileset")
    s["required"] = ["format", "version", "name", "id", "tiles"]
    s["properties"].update({
        "name": NAME, "aliases": {"type": "array", "items": {"type": "string"}},
        "tiles": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "kind"], "additionalProperties": False,
                  "properties": {"id": TILE, "kind": {"type": "string"}, "mark": {"type": "string"}, "name": {"type": "string"}}}},
        "meta": {"type": "object"}})
    return s


def wall_schema():
    s = base("Nmahjong wall 1.0", "wall")
    s["required"] = ["format", "version", "tileset", "source", "order", "id"]
    s["properties"].update({
        "tileset": REF, "source": {"enum": ["generated", "observed", "filled"]},
        "generation": {"type": "object", "required": ["method", "seed"], "properties": {"method": {"type": "string"}, "seed": {"type": "string"},
                       "round": {"type": "integer", "minimum": 0}, "oya": {"type": "integer", "minimum": 0}, "players": {"type": "integer", "minimum": 1}, "hand": {"type": "integer", "minimum": 1}}},
        "observed": {"type": "array", "items": {"type": "array", "items": {"type": "integer", "minimum": 0}, "minItems": 2, "maxItems": 2}},
        "fill": {"type": "object", "required": ["method", "seed"], "properties": {"method": {"type": "string"}, "seed": {"type": "string"}}},
        "device": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "maker": {"type": "string"}, "model": {"type": "string"}, "firmware": {"type": "string"}, "at": {"type": "string"}}},
        "order": {"type": "array", "minItems": 1, "items": TILE, "uniqueItems": True},
        "meta": {"type": "object"}})
    return s


def _schema_of(default, path):
    """既定値の形からスキーマ。語彙（ENUM）があれば enum。null 既定は null か数値/文字列。"""
    key = path.split(".")[-1]
    parent = ".".join(path.split(".")[-2:])
    vocab = R.ENUM.get(parent) or R.ENUM.get(key)
    if isinstance(default, bool):
        return {"type": "boolean"}
    if isinstance(default, int):
        return {"type": "integer"}
    if isinstance(default, float):
        return {"type": "number"}
    if isinstance(default, str):
        return {"enum": vocab} if vocab and default in vocab else {"type": "string"}
    if default is None:
        return {"type": ["null", "integer", "number", "string", "object", "array"]}
    if isinstance(default, list):
        return {"type": "array"}
    if isinstance(default, dict):
        if path in R._FREE_KEY_OBJECTS:
            return {"type": "object"}
        props = {k: _schema_of(v, f"{path}.{k}") for k, v in default.items()}
        extra = R.ENABLED_DEFAULTS.get(path, {})
        for k, v in extra.items():
            props.setdefault(k, _schema_of(v, f"{path}.{k}"))
        ap = False
        if path in ("settlement.uma",):
            ap = True
        return {"type": "object", "properties": props, "additionalProperties": ap}
    return {}


def ruleset_schema():
    s = base("Nmahjong ruleset 1.0（形だけ。既定値の補完・語彙・整合は validate が正）", "ruleset")
    s["required"] = ["format", "version", "name", "tileset", "players", "hand_size", "length", "winds", "wall_rules"]
    s["properties"].update({
        "name": NAME, "tileset": REF,
        "players": {"type": "integer", "minimum": 1}, "hand_size": {"type": "integer", "minimum": 1},
        "length": {"enum": R.ENUM["length"]}, "rounds_total": {"type": "integer", "minimum": 1},
        "winds": {"type": "array", "items": {"enum": ["E", "S", "W", "N"]}},
        "wall_rules": {"type": "object", "additionalProperties": False, "required": ["deal", "dead_wall", "break"], "properties": {
            "deal": {"enum": R.ENUM["deal"]}, "dead_wall": {"type": "integer", "minimum": 0},
            "dora_indicator": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            "ura_indicator": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            "kan_dora": {"type": "array", "items": {"type": "integer"}}, "kan_ura": {"type": "array", "items": {"type": "integer"}},
            "rinshan": {"oneOf": [{"const": "live"}, {"type": "array", "items": {"type": "integer"}}]},
            "rinshan_reserved": {"type": "boolean"},
            "break": {"type": "object", "required": ["by"], "properties": {"by": {"enum": R.ENUM["break.by"]}}}}},
        "game_rules": _schema_of(R.DEFAULT_GAME_RULES, "game_rules"),
        "end": _schema_of(R.DEFAULT_END, "end"),
        "settlement": _schema_of(R.DEFAULT_SETTLEMENT, "settlement"),
        "unknown": {"type": "array", "items": {"type": "string"}},
        "meta": {"type": "object"}})
    # passthrough（形が複数ある項目）は型を緩める
    st = s["properties"]["settlement"]["properties"]
    st["uma"] = {"oneOf": [{"type": "array", "items": {"type": "number"}}, {"type": "object"}]}
    st["payout"] = {"type": ["null", "object"]}
    st["chips"] = {"type": "array"}; st["external_points"] = {"type": "array"}
    g = s["properties"]["game_rules"]["properties"]
    g["mark_overrides"] = {"type": "array"}
    g["pao"]["properties"]["yakuman"] = {"type": "array", "items": {"type": "string"}}
    # 「あるときだけ書く」項目
    sc = g["scoring"]["properties"]
    sc["table"] = {"oneOf": [{"enum": ["standard", "additive"]}, {"type": "string", "pattern": "^custom:.+"}]}
    sc["additive"] = _schema_of(R.ADDITIVE_DEFAULTS, "game_rules.scoring.additive")
    sc["tsumo_table"] = {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "integer", "minimum": 0}, "minItems": 2, "maxItems": 2}}
    g["yaku"]["properties"]["wheel"] = {"enum": ["2to8", "any_suit"]}
    g["flow"]["properties"]["next_dealer"] = {"enum": ["rotate", "winner"]}
    return s


def record_schema():
    s = base("Nmahjong record 1.0", "record")
    ev = {"type": "object", "required": ["t"], "properties": {
        "t": {"enum": sorted(REC.EVENT_TYPES)},
        "who": {"type": "integer", "minimum": 0}, "from": {"type": "integer", "minimum": 0}, "tile": TILE, "tiles": TILES,
        "kind": {"type": "string"}, "tsumogiri": {"type": "boolean"}, "riichi": {"type": "boolean"}, "open": {}, "rinshan": {"type": "boolean"},
        "reason": {"type": "string"}, "resume": {"type": "boolean"}, "hands": {"type": "array", "items": TILES}, "at": {"type": "string"}}}
    win = {"type": "object", "required": ["who", "from", "tile", "hand", "yaku", "fu", "han", "points", "deltas"], "properties": {
        "who": {"type": "integer"}, "from": {"type": "integer"}, "tile": {"type": ["integer", "null"]}, "hand": TILES,
        "melds": {"type": "array", "items": {"type": "object", "required": ["kind", "tiles"], "properties": {"kind": {"enum": R.VOCAB["meld_kinds"]}, "tiles": TILES, "from": {"type": "integer"}}}},
        "yaku": {"type": "array", "items": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "han": {"type": "integer"}, "yakuman": {"type": "integer"}}}},
        "fu": {"type": "integer"}, "han": {"type": "integer"}, "yakuman": {"type": "integer"}, "points": {"type": "integer"},
        "ura_indicators": TILES, "deltas": {"type": "array", "items": {"type": "integer"}}, "chips": {"type": "array"}, "pao": {"type": "integer"}, "reverse": {"type": "boolean"},
        "additive": {"type": "object", "additionalProperties": False, "required": ["han", "yakuman", "base", "dealer", "honba", "karasu", "each"],
                     "properties": {k: {"type": "integer", "minimum": 0} for k in ("han", "yakuman", "base", "dealer", "honba", "karasu", "each")}}}}
    draw = {"type": "object", "required": ["reason", "deltas"], "properties": {"reason": {"enum": R.VOCAB["draw_reasons"]},
            "tenpai": {"type": "array"}, "hands": {"type": "array"}, "deltas": {"type": "array", "items": {"type": "integer"}}}}
    s["required"] = ["format", "version", "id", "source", "ruleset", "players", "end", "rounds", "final"]
    s["properties"].update({
        "source": {"type": "object", "required": ["kind", "from"], "properties": {"kind": {"enum": R.VOCAB["source_kinds"]}, "from": {"type": "string"}, "ref": {"type": ["string", "null"]}}},
        "ruleset": REF,
        "players": {"type": "array", "items": {"type": "object", "required": ["seat"], "properties": {
            "seat": {"type": "integer", "minimum": 0}, "name": {"type": "string"}, "external": {"type": "array"}, "ranks": {"type": "array"}, "rating": {"type": "object"}}}},
        "end": {"enum": R.VOCAB["record_end"]}, "parent": {"type": ["null", "object"]},
        "started_at": {"type": "string"}, "ended_at": {"type": "string"},
        "rounds": {"type": "array", "items": {"type": "object", "required": ["index", "wall", "state", "events", "result"], "properties": {
            "index": {"type": "integer", "minimum": 0}, "wall": {"oneOf": [{"type": "null"}, REF]},
            "state": {"type": "object", "required": ["bakaze", "kyoku", "honba", "kyotaku", "oya", "scores"], "properties": {
                "bakaze": {"enum": ["E", "S", "W", "N"]}, "kyoku": {"type": "integer", "minimum": 1}, "honba": {"type": "integer", "minimum": 0},
                "kyotaku": {"type": "integer", "minimum": 0}, "oya": {"type": "integer", "minimum": 0}, "scores": {"type": "array", "items": {"type": "integer"}},
                "dice": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 6}}}},
            "events": {"type": "array", "minItems": 1, "items": ev},
            "result": {"type": ["object", "null"], "properties": {"wins": {"type": "array", "items": win}, "draw": {"oneOf": [{"type": "null"}, draw]}, "scores": {"type": "array", "items": {"type": "integer"}}}}}}},
        "final": {"type": "object", "required": ["scores", "rank", "settled"], "properties": {
            "scores": {"type": "array", "items": {"type": "integer"}}, "rank": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            "settled": {"type": "array", "items": {"type": "number"}}, "chips": {"type": "array"}, "external_points": {"type": "array"}}},
        "meta": {"type": "object"}})
    return s


def annotation_schema():
    from nmahjong import annotation as A
    s = base("Nmahjong annotation 1.0", "annotation")
    action = {"type": "object", "required": ["type"], "properties": {"type": {"enum": list(A.ACTION_TYPES)}, "tile": TILE, "tiles": TILES,
              "kind": {"enum": R.VOCAB["kan_kinds"]}, "open": {"type": "boolean"}, "reason": {"type": "string"}, "values": {"type": "object"}}}
    s["required"] = ["format", "version", "id", "record", "evaluator", "points"]
    s["properties"].update({
        "record": REF,
        "evaluator": {"type": "object", "required": ["name", "version", "visibility", "metrics"], "additionalProperties": False, "properties": {
            "name": {"type": "string", "pattern": "^[a-z0-9-]+$"}, "version": {"type": "string"}, "visibility": {"enum": list(A.VISIBILITY)},
            "metrics": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["name", "scope", "kind"], "additionalProperties": False, "properties": {
                "name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}, "scope": {"enum": list(A.SCOPES)}, "kind": {"enum": list(A.KINDS)},
                "higher_is_better": {"type": "boolean"}, "primary": {"type": "boolean"}, "unit": {"type": "string"}}}},
            "params": {"type": "object"}, "run_at": {"type": "string"}}},
        "points": {"type": "array", "items": {"type": "object", "required": ["round", "at", "phase", "actor", "actual", "candidates", "best", "loss"], "additionalProperties": False, "properties": {
            "round": {"type": "integer", "minimum": 0}, "at": {"type": "integer", "minimum": 0}, "phase": {"enum": list(A.PHASES)}, "actor": {"type": "integer", "minimum": 0},
            "actual": action, "candidates": {"type": "array", "minItems": 1, "items": action}, "estimates": {"type": "object"},
            "best": {"type": "integer", "minimum": 0}, "loss": {"type": "number", "minimum": 0}, "verdict": {"enum": list(A.VERDICTS)}, "note": {"type": ["string", "null"]}}}}})
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("tileset", tileset_schema), ("wall", wall_schema), ("ruleset", ruleset_schema), ("record", record_schema), ("annotation", annotation_schema)):
        with open(os.path.join(OUT, f"{name}.schema.json"), "w", encoding="utf-8") as f:
            json.dump(fn(), f, ensure_ascii=False, indent=1)
            f.write("\n")
    print("schema/", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
