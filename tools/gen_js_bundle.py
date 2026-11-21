"""Python 実装の既定値・語彙・同梱データを JS 用に書き出す。
  nmahjong/data/defaults.json  … ruleset の既定値（DEFAULT_*／ENABLED_DEFAULTS／_PASSTHROUGH／_FREE_KEY_OBJECTS／ENUM）
  js/bundled.js                … 牌表・ルール・既定値・語彙を 1 ファイルに（ブラウザで file:// から読める）
使い方: python3 tools/gen_js_bundle.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from nmahjong import ruleset as R, tileset as TS  # noqa: E402


def descriptions():
    """日本語の仕様書の表（| 項目 | MUST/MAY | 内容 |）から 項目名 → 説明 を拾う（画面のヒント用。画面は日本語）。
    日本語の仕様書が無いときは、いまの js/bundled.js に入っている説明をそのまま使う。"""
    path = os.path.join(ROOT, "docs", "spec", "ruleset" + "_JA" + ".md")
    if not os.path.exists(path):
        try:
            with open(os.path.join(ROOT, "js", "bundled.js"), encoding="utf-8") as fh:
                m = re.search(r"g\.NMAHJONG_BUNDLE = (\{.*\});\n if \(typeof module", fh.read(), re.S)
            return json.loads(m.group(1))["descriptions"]
        except (OSError, AttributeError, KeyError, ValueError):
            return {}
    # 見出し（## / ###）に含まれる節名（game_rules.flow など）を前置きにして、同じ項目名が別の節で別の意味になるのを分ける
    found = {}
    section = ""
    nested = False
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    for line in lines:
        h = re.match(r"^(#{2,4})\s+(.*)", line)
        if h:
            m2 = re.search(r"\b((?:wall_rules|game_rules|end|settlement)(?:\.[a-z_]+)*)\b", h.group(2))
            if m2:
                section = m2.group(1)
            elif len(h.group(1)) <= 3:      # ## / ### で節名が無ければ節の外
                section = ""
            nested = False
            continue
        bold = re.match(r"^\*\*(.+?)\*\*", line)
        if bold:   # 太字の小見出し（例：**mark 規則**）＝入れ子の表。項目名だけでは引けないようにする
            nested = "mark" in bold.group(1) or "規則" in bold.group(1)
            continue
        if not line.startswith("|"):
            continue
        m = re.match(r"^\|\s*([a-zA-Z0-9_.]+)\s*\|\s*(MUST|MAY|SHOULD)[^|]*\|\s*(.+?)\s*\|\s*$", line)
        if m:
            key, desc = m.group(1), re.sub(r"_JA(?=\.md)", "", m.group(3).replace("\\|", "|"))
            full = (section + "." + key) if section and not key.startswith(section) else key
            if nested or "." in key:
                full = full + "#nested"      # 入れ子の表、または「fu.enabled」のような複合名は、末尾 1 語だけでは引けないようにする
            found.setdefault(full, desc)
    # 画面はパスの末尾一致で引く。末尾の綴り（a.b.c／b.c／c）が 1 つの意味にしか使われていないものだけ登録する（違う意味の項目に別の説明が付くのを防ぐ）
    # キーは「節|末尾」。節（wall_rules／game_rules／end／settlement／top）が違えば別物として扱う
    suffixes = {}
    for full, desc in found.items():
        is_nested = full.endswith("#nested")
        parts = full.replace("#nested", "").split(".")
        sect = parts[0] if parts[0] in ("wall_rules", "game_rules", "end", "settlement") else "top"
        rest = parts[1:] if sect != "top" else parts
        for i in range(len(rest)):
            if is_nested and len(rest) - i == 1:
                continue        # 入れ子の表の項目名単体（when／value など）は登録しない
            suffixes.setdefault(sect + "|" + ".".join(rest[i:]), set()).add(desc)
    out = {k: next(iter(v)) for k, v in suffixes.items() if len(v) == 1}
    return out


def main():
    defaults = {
        "game_rules": R.DEFAULT_GAME_RULES, "end": R.DEFAULT_END, "settlement": R.DEFAULT_SETTLEMENT,
        "enabled_defaults": R.ENABLED_DEFAULTS, "optional_keys": R.OPTIONAL_KEYS, "additive_defaults": R.ADDITIVE_DEFAULTS, "passthrough": sorted(R._PASSTHROUGH),
        "free_key_objects": sorted(R._FREE_KEY_OBJECTS), "enum": R.ENUM,
        "wall_rules_keys": ["deal", "dead_wall", "dora_indicator", "ura_indicator", "kan_dora", "kan_ura", "rinshan", "break", "rinshan_reserved"],
        "top_keys": ["format", "version", "name", "id", "tileset", "players", "hand_size", "length", "rounds_total",
                     "winds", "wall_rules", "game_rules", "end", "settlement", "unknown", "meta"],
        "format": R.FORMAT, "version": R.VERSION,
    }
    with open(os.path.join(ROOT, "nmahjong", "data", "defaults.json"), "w", encoding="utf-8") as f:
        json.dump(defaults, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    bundle = {
        "defaults": defaults, "vocab": R.VOCAB,
        "yaku_tables": R.YAKU_TABLES,
        "tilesets": TS.bundled(), "rulesets": R.bundled(),
        "descriptions": descriptions(),
    }
    os.makedirs(os.path.join(ROOT, "js"), exist_ok=True)
    with open(os.path.join(ROOT, "js", "bundled.js"), "w", encoding="utf-8") as f:
        f.write("/* 生成物：tools/gen_js_bundle.py。手で編集しない */\n")
        f.write("(function(g){ g.NMAHJONG_BUNDLE = ")
        json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n if (typeof module !== 'undefined') module.exports = g.NMAHJONG_BUNDLE; })(typeof globalThis !== 'undefined' ? globalThis : this);\n")
    print("defaults.json / js/bundled.js", len(bundle["tilesets"]), "tilesets", len(bundle["rulesets"]), "rulesets")


if __name__ == "__main__":
    main()
