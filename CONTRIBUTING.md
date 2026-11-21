# Contributing to Nmahjong

Thank you for your interest. Reports, corrections and code are all welcome.

## Ways to contribute

| What | Where |
|---|---|
| A bug, or a result that differs from a real game | Issues → "Bug report" |
| A bundled rule that differs from the rule of the organisation, service or parlour | Issues → "Rule correction" |
| A description that is wrong or odd as mahjong (terms, rules, yaku, scores, flow) | Issues → "Bug report" |
| A security problem | Do **not** open an issue. See [SECURITY.md](SECURITY.md) |
| A question or an idea | Issues |

## Rule corrections

The bundled rules (`nmahjong/data/rulesets/`) were written from published rule texts. Where a text did not state an item, the most plausible value was chosen and the item is listed in the rule's `unknown` field.

If you run or belong to the organisation, service or parlour, or you know its rule, please tell us:

1. the name of the bundled rule (for example `mleague`),
2. the item and the correct value,
3. a source that anyone can read (a URL or a published document). If no public source exists, say who you are in relation to the rule.

A correction changes the id of the rule, because the id is the hash of its content.

## Development

No third-party packages are needed. (If `jsonschema` is installed, two more tests run that check the bundled data against the JSON Schemas.)

- Python 3.11 or later (standard library only; tested on 3.11, 3.12 and 3.13)
- Node.js (for the JavaScript implementation; no dependencies)

```bash
git clone https://github.com/ohba-artlife/Nmahjong.git
cd Nmahjong
pip install -e .
python -m unittest discover -s tests        # Python tests (several minutes)
cd js && node test.js && node test_game.js  # JavaScript tests
```

## Rules for a change

1. **Two implementations must agree.** Python (`nmahjong/`) is the reference. JavaScript (`js/src/game_*.js`) must give the same ids, the same judgements and the same records. A change to one needs the same change to the other.
2. **Do not edit generated files by hand.** Edit the source and run the generator.

   | Generated | Source | Command |
   |---|---|---|
   | `nmahjong/data/rulesets/*.json` | `tools/gen_rulesets.py` | `python tools/gen_rulesets.py` |
   | `nmahjong/data/schema/*.json` | `tools/gen_schema.py` | `python tools/gen_schema.py` |
   | `tests/vectors/conformance.json` | the reference implementation | `python tools/gen_vectors.py` |
   | `js/bundled.js`, `nmahjong/data/defaults.json` | bundled data and docs | `python tools/gen_js_bundle.py` |
   | `js/nmahjong-game.js` | `js/src/game_*.js` | `python tools/gen_js_game.py` |
   | `js/testdata/` | `tests/` | `python tools/gen_js_testdata.py` |

3. **Existing ids must not change by accident.** A new setting is added as an optional key whose default is "as before", so that rules which do not use it keep their ids.
4. **A rule or a judgement needs a source and a test.** Quote the published sentence in the test's docstring, and build the game that shows it (`tests/scripted.py`).
5. **Say what the program cannot follow.** If a setting can be written but the dealer program has no behaviour for it, report it from `dealer.unsupported()` instead of silently ignoring it.
6. Update the documents under `docs/` and `CHANGELOG.md` in the same change.

## Pull requests

- Keep one purpose per pull request.
- All tests must pass (CI runs them on every pull request).
- Do not include game logs downloaded from online services, personal names, or e-mail addresses.

## Licence of contributions

By contributing you agree that your contribution is provided under the licences of this repository: MIT for code and bundled data (`LICENSE`), CC BY 4.0 for the specification documents (`LICENSE-SPEC`).
