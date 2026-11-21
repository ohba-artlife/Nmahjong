# CHANGELOG — Nmahjong

A summary of the changes of each version, newest first. The version number is "major change.added feature.fix".

The id of a bundled ruleset is the hash of its content, so correcting a ruleset changes its id. Rulesets whose ids change are named in the entry of that version.

## 1.0.0 (2026-11-22)

The first public version.

- Specification (1.0): the five layers tileset, ruleset, wall, record and annotation (`docs/spec/`)
- Reference implementation (Python, standard library only): reading, writing, ids and verification of the five layers; cross-layer verification; judgement of yaku and fu of a win; scores and settlement; positions and legal actions; recorder; gateway for players (mjai-compatible); game runner; evaluation; arena; import of Tenhou game logs; the command `nmahjong`
- Second implementation (JavaScript, no dependencies): ids, verification, judgement, recorder, game runner, evaluation. Tests confirm that it gives the same results as Python (`docs/conformance.md`)
- Bundled data: 10 tilesets and 46 rulesets (organisations, online services, a TV programme, parlours, three-player rules, N-tile mahjong; `docs/spec/ruleset.md` §7). Items that the source text does not state are set to the most plausible value and listed in `unknown` of the ruleset
- Conformance: test vectors, JSON Schemas, and the results of comparisons with large numbers of games (`docs/conformance.md`)
