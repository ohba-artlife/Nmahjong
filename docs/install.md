# Installation and use

## Requirements
- Python 3.11 or later (standard library only; no additional packages are needed; tested on 3.11, 3.12 and 3.13)
- For the JavaScript version: Node.js, or a browser (no dependencies)

## Installation
```bash
git clone https://github.com/ohba-artlife/Nmahjong.git
cd Nmahjong
pip install -e .
python -m nmahjong --version
```

## Checking that it works
```bash
# 1. The wall must match the test vector (spec/wall.md §3)
python -m nmahjong build --tileset mpsz --seed 2026-11-11T10:00:00+09:00 | python -m nmahjong validate -
# Expected: OK. The id of the wall is sha256:3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c

# 2. All bundled rulesets must pass verification (items not found in the source are listed as "missing")
python -m nmahjong ruleset validate nmahjong/data/rulesets/*.ruleset.json

# 3. Tests (Python)
python -m unittest discover -s tests

# 4. Tests (JavaScript)
cd js && node test.js && node test_game.js
```
The tests that use Tenhou game logs (tests/test_tenhou_logs.py) run only when logs are placed. Without logs they are skipped (tests/data/tenhou/README.md).

## Commands
```
nmahjong build     --tileset NAME[@ID] --seed SEED                     make a wall from a seed and write it to standard output (fy-sha256-v1)
nmahjong build     --tileset NAME --tags READ.txt --tagmap MAP.json [--device ID]
                                                                       a sequence of tag ids read by a physical table → an observed wall
nmahjong validate  FILE…                                               verify the five layers (the kind is decided by "format"; for cross-layer checks, files in the same folder are looked up)
nmahjong show      FILE                                                show numbers as tile names
nmahjong tileset   list | show NAME | new --colors … [--mark …] [--out DIR]
nmahjong ruleset   list | show NAME | new --from NAME --name NAME [--set path=value …] [--out DIR] | diff A B | validate FILE…
nmahjong import    tenhou FILE… [--out DIR]                            Tenhou mjlog (XML) → walls and a record (the wall is reproduced and compared)
nmahjong import    tenhou-json FILE… [--out DIR]                       Tenhou JSON (tenhou.net/6) → a record (no wall)
nmahjong export    tenhou-json RECORD                                  a record → Tenhou JSON
nmahjong observe   RECORD --round N --at K --seat S [--full] [--names] a position (--full shows every player's hand)
nmahjong legal     RECORD --round N --at K --seat S [--phase A|B|C] [--mjai]
                                                                       legal actions (--mjai gives the request_action form) and the action actually taken
nmahjong judge     RECORD [--round N]                                  judge yaku, fu and han of the wins and compare with the record (programs/judge.md)
nmahjong play      RULESET [--seed S] [--bot simple|tsumogiri] [--player SEAT=COMMAND] [--annotate] [--out DIR]
                                                                       let the game runner run one game (programs/dealer.md). --annotate evaluates every discard
nmahjong arena     RULESET --entrant NAME=simple --entrant NAME=COMMAND [--games N] [--seed S] [--out DIR]
                                                                       arena: let players play many games and print a table of results (programs/layer5.md)
nmahjong annotate  RECORD [--evaluator nm-waits] [--out DIR]           make an annotation file with a bundled evaluator
nmahjong mjai      RECORD [--seat S]                                   a record → a sequence of mjai events (JSON Lines). --seat hides the other players' tiles
```
`validate` on an annotation file (*.annotation.json) goes as far as the cross-layer check (comparison with the legal actions) when the record (*.record.json) and the walls are in the same folder.

The messages printed by the commands are in Japanese.

The shortest example:
```bash
python -m nmahjong ruleset list
python -m nmahjong ruleset new --from mleague --set 'settlement.uma=[20,10,-10,-20]' --name my-rule --out ./out
python -m nmahjong play nm-2p-4-mps --seed demo --out ./out      # one game between bundled players
python -m nmahjong validate ./out/*.record.json
python -m nmahjong judge    ./out/*.record.json
python -m nmahjong annotate ./out/*.record.json --out ./out
python -m nmahjong mjai     ./out/*.record.json --seat 0
```

## Pages (just open them in a browser; no server needed)
- Ruleset page `tools/rulegen.html`: choose a bundled ruleset as a template → change items → the id and the difference from the template appear at once → download (the file name is `{name}_{id}.ruleset.json`). A ruleset.json of your own can also be loaded and edited
- Tileset page `tools/tilesetgen.html`: choose the suits, the number of red tiles, the kinds to remove and the extra tiles, and you get a tileset file and its id. The tileset can then be used in the ruleset page through "牌表を読み込み…" (load a tileset)

Both pages are in Japanese.

## JavaScript version
- `js/nmahjong.js`: canonical JSON, SHA-256, tileset ids, generation and verification of walls, the normal form and id of a ruleset and its basic verification
- `js/bundled.js`: bundled data (tilesets, rulesets, defaults). It is generated; do not edit it by hand
- `js/nmahjong-game.js`: layers 4 and 5 (scores, positions and legal actions, judgement of yaku and fu, verification of records, recorder, game runner and bundled players, evaluation, arena). How to use it is in programs/js-game.md
- In Node.js use `require("./nmahjong.js")`; in a browser load it with `<script>` and use the global `NMAHJONG`

## Regenerating generated files (for developers)
| What is made | Command |
|---|---|
| Bundled tilesets and rulesets (nmahjong/data/tilesets, rulesets) | `python3 tools/gen_tilesets.py`, `python3 tools/gen_rulesets.py` |
| Defaults and the bundled data for JavaScript (nmahjong/data/defaults.json, js/bundled.js) | `python3 tools/gen_js_bundle.py` (run it after changing defaults on the Python side; tests/test_ruleset.py detects a mismatch) |
| Layers 4 and 5 for JavaScript (js/nmahjong-game.js ← js/src/game_*.js) | `python3 tools/gen_js_game.py` |
| JSON Schemas (nmahjong/data/schema) | `python3 tools/gen_schema.py` |
| Example games (examples/) | `python3 tools/gen_examples.py` |
| 13-tile games for tests, and test data for JavaScript | `python3 tools/gen_test_games.py`, `python3 tools/gen_js_testdata.py` |
| Conformance test vectors (tests/vectors/conformance.json) | `python3 tools/gen_vectors.py` |

## Uninstalling
`pip uninstall nmahjong`. Files you made are where you pointed `--out`; delete them by hand.
