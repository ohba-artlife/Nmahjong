# Nmahjong

Data formats for N-tile mahjong (tileset, ruleset, wall, record, annotation), with a reference implementation in Python and a second implementation in JavaScript.

日本語版：[README_JA.md](README_JA.md)

## What this is

Storage formats (five layers: tileset, ruleset, wall, record, annotation) plus programs that create, verify and run them. It does not include a screen for playing mahjong, nor a strong AI.

- Import games that have already been played (for example from Tenhou) and verify the wall, the scores and the settlement. Create rulesets and walls.
- Build a game while it is being played: a recorder, a gateway for players, a game runner, judgement of yaku and fu for a win, evaluation, and an arena.
- Diagrams and a longer explanation are in `docs/overview.md`; the list of documents is in `docs/README.md`.

## Purpose

Mahjong is generalised by the **set of tiles**, the **hand size N** and the **number of players M (1 or more)**, so that everything from 1-tile mahjong to 13-tile mahjong, three-player mahjong and games with flower tiles is expressed in **one container**.
Tileset, ruleset, wall, record and annotation are defined as independent data, so that a generated wall, a wall read from a physical table and a wall reconstructed from an imported game are stored, verified and reproduced in the same shape.

## Overview (five layers)

```
before  tileset     which tiles exist, how many, and which number is which. Marks (red, pocchi) are held as facts   1.0
        ruleset     how the wall is consumed, the rules of play, the end, the settlement. 46 bundled rulesets      1.0
start   wall        a permutation of tile numbers. generated / observed / observed + filled. Always states
                    how much of it is fact                                                                          1.0
        record      source, players, rounds, events, results. Refers to the ruleset and the walls by id.
                    One game = one file                                                                             1.0
after   annotation  candidates and values at each decision point. The evaluator declares the names of its values.
                    Refers to the record by id                                                                      1.0
```

- Tiles are handled as **numbers**. Only the tileset gives a number its meaning.
- With all suits and four copies of each tile (`mpsz`), the numbers are the same as Tenhou's 0–135.
- An id is the hash (SHA-256) of the content. The same content gives the same id, whoever makes it.
- Import is from Tenhou (mjlog XML, and tenhou.net/6 JSON). Mahjong Soul is planned for version 2. Export is limited to Tenhou JSON and mjai, for verification and interoperation.
- A position is shown to an AI in an mjai-compatible form (no new format is invented). `legal_actions(ruleset, position)` lists the legal actions.

## What is bundled

- 46 rulesets (organisations, Tenhou, Mahjong Soul, a TV programme, parlours, three-player rules, N-tile mahjong; the list is in `docs/spec/ruleset.md` §7) and ruleset generators (the command `ruleset new` and the page `tools/rulegen.html`)
- Tables of yaku, scores and vocabulary, and the table that maps Tenhou's yaku
- Test vectors (wall generation) and JSON Schemas

## Requirements

- Reference implementation: Python 3.11 or later, standard library only (tested on 3.11, 3.12 and 3.13)
- Second implementation: JavaScript (browser and Node.js). It passes the same test vectors
- The container is JSON

## Quick start

```bash
pip install -e .
python -m nmahjong build    --tileset mpsz --seed 2026-11-11T10:00:00+09:00 > out.wall.json
python -m nmahjong validate out.wall.json
python -m nmahjong show     out.wall.json
python -m nmahjong ruleset  list
python -m nmahjong ruleset  new --from mleague --set settlement.uma=[20,10,-10,-20] --name my-rule
python -m nmahjong import   tenhou 2026111023gm-00a9-0000-1a2b3c4d.mjlog --out ./out     # reproduces the wall and verifies up to X5
python -m nmahjong import   tenhou-json log.json --out ./out                              # tenhou.net/6 JSON (no wall)
python -m nmahjong legal    ./out/*.record.json --round 0 --at 68 --seat 3 --phase A       # legal actions and the action actually taken
python -m nmahjong annotate ./out/*.record.json --out ./out                               # an annotation file by the bundled evaluator
python -m nmahjong mjai     ./out/*.record.json --seat 0                                  # mjai events (other players' tiles hidden)
```

Ruleset generator page: open `tools/rulegen.html` in a browser (no server needed). Choose a bundled ruleset as a template, change items, see the id and the difference, and download the file. The page itself is in Japanese.

## Input and output (summary)

| Data | File name | Main content |
|---|---|---|
| tileset | `{name}_{id64}.tileset.json` | name, id, tiles[] (id, kind, mark, name) |
| ruleset | `{name}_{id64}.ruleset.json` | tileset, players, hand_size, wall_rules, game_rules, end, settlement |
| wall | `{tileset}_{id64}.wall.json` | tileset, source, generation / observed + fill, device, order[], id |
| record | `{tileset}_{id64}.record.json` | source, ruleset, players, rounds[] (wall, state, events, result), final |
| annotation | `{record_id64}_{evaluator}.annotation.json` | record, evaluator (declares its metrics), points[] |

id64 is the 64 hexadecimal digits of SHA-256, as they are. Tileset names: `{suits}[-x{count}][-e{count}]` (for example `mpsz`, `mpsz-x28`). A reference is `{name, id}`, and the id is authoritative.
Tiles are written (for display, input and AI connection) in the mjai notation (`1m`–`9s`, `5mr`, `E S W N P F C`). `1z`–`7z` and `0m` can also be read.

## Status (version 1.0.0, 2026-11-22)

- Specification: all five layers are 1.0
- Reference implementation (Python): reading, writing, ids and verification of the five layers; judgement of yaku and fu; scores and settlement; positions and legal actions; recorder; gateway for players (mjai-compatible); game runner; evaluation; arena; import from Tenhou (XML reproduces the wall; JSON has no wall)
- Second implementation (JavaScript): ids, verification, judgement, recorder, game runner, evaluation. It gives the same results as Python on the same test vectors and test data
- Bundled: 10 tilesets, 46 rulesets
- What was checked (counts and details in `docs/conformance.md`): 1,005 Tenhou games (reproduction of the wall; yaku, fu and scores; settlement), more than 11,000 games of N-tile mahjong played by a separate implementation, comparison of Python and JavaScript, and an item-by-item comparison with the rule text published by Tenhou
- Not available yet: import from Mahjong Soul. Settings that the game runner cannot follow are listed in `docs/programs/dealer.md` §4

## Language

The documents are written in English. This page also has a Japanese version (`README_JA.md`). Messages of the programs, comments in the source code, and the notes inside bundled rulesets are in Japanese.

## Taking part, reporting, citing

- Bugs, descriptions that are wrong as mahjong, corrections of bundled rules: Issues (see `CONTRIBUTING.md`)
- Security problems: do not write them in a public issue; follow `SECURITY.md`
- Code of conduct: `CODE_OF_CONDUCT.md`
- How to cite: `CITATION.cff`
- Record of changes: `CHANGELOG.md`

## Licence

- Implementation (Python, JavaScript, tools, tests, bundled data): MIT (`LICENSE`)
- Specification documents (*.md): CC BY 4.0 (`LICENSE-SPEC`)
- Copyright holder: ohba-artlife

## Related documents

- `docs/README.md` list of documents
- `docs/overview.md` overview (five layers, cross-layer verification, positions and the gateway, bundled data, import)
- `docs/install.md` installation and the list of commands
- `docs/spec/` specification of each layer (`tileset.md` `ruleset.md` `wall.md` `record.md` `annotation.md`)
- `docs/rules/nm-defaults.md` the default rules of N-tile mahjong (the bundled nm-* rulesets)
- `docs/programs/` descriptions of the programs (recorder and gateway, game runner, judgement, evaluation and arena, JavaScript version)
- `docs/design/` design rationale (survey of major Japanese rules, how a position is shown, how values are held)
