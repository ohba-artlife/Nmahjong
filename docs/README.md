# List of documents

| Document | Content |
|---|---|
| [overview.md](overview.md) | Overview: the five layers, the design ideas, file names, cross-layer verification, positions and the gateway for players, bundled data, compatibility, import |
| [install.md](install.md) | Installation, checking that it works, the list of commands, the pages, the JavaScript version |
| [conformance.md](conformance.md) | Conformance: test vectors, JSON Schemas, agreement of Python and JavaScript, the number of real games checked, what has not been checked |

## Specifications (spec/)
| Document | Layer |
|---|---|
| [spec/tileset.md](spec/tileset.md) | 1 tileset |
| [spec/ruleset.md](spec/ruleset.md) | 2 ruleset (the list of bundled rulesets is in §7) |
| [spec/wall.md](spec/wall.md) | 3 wall |
| [spec/record.md](spec/record.md) | 4 record |
| [spec/annotation.md](spec/annotation.md) | 5 annotation |

## Bundled rules (rules/)
| Document | Content |
|---|---|
| [rules/nm-defaults.md](rules/nm-defaults.md) | The default rules of N-tile mahjong (hand of 1, 4, 7, 10 or 13 tiles; two players) |
| [rules/tenhou-rules.md](rules/tenhou-rules.md) | Item-by-item comparison with the rule text published by Tenhou (the bundled tenhou-* rulesets) |

The list of rules of parlours and organisations, with its notes, is in [spec/ruleset.md](spec/ruleset.md) §7; the source of each rule is in `meta.source` of its file.

## Descriptions of the programs (programs/)
| Document | Content |
|---|---|
| [programs/recorder-gateway.md](programs/recorder-gateway.md) | The recorder, and the gateway for players |
| [programs/dealer.md](programs/dealer.md) | The game runner, and the bundled players |
| [programs/judge.md](programs/judge.md) | Judgement of yaku and fu for a win |
| [programs/layer5.md](programs/layer5.md) | Step-by-step evaluation, and the arena |
| [programs/js-game.md](programs/js-game.md) | Layers 4 and 5 in the JavaScript version |

## Design rationale (design/)
| Document | Content |
|---|---|
| [design/ruleset-survey.md](design/ruleset-survey.md) | Survey of major Japanese rules (the grounds and sources for the items of a ruleset) |
| [design/observation.md](design/observation.md) | Why a position is shown in the mjai form |
| [design/evaluation.md](design/evaluation.md) | Why values of an evaluation are held the way they are |

## Words used in the English documents

Mahjong terms are kept in their usual romanised form: yaku, han, fu, riichi, tenpai, dora, honba, pon, chi, kan, tsumo, ron.

| English | Japanese | Meaning |
|---|---|---|
| tileset | 牌表 | Layer 1: the list of tiles and their numbers |
| ruleset | ルール | Layer 2: the settings of a rule |
| wall | 牌山 | Layer 3: the order of all tiles of one round |
| record | 対局 | Layer 4: one game, with its rounds and events |
| annotation | 評価 | Layer 5: values given to decision points of a record |
| round | 局 | One deal, from the deal to a win or a draw |
| dealer | 親 | The player in the east seat of a round |
| non-dealer | 子 | Any other player |
| win | 和了 | Completing a hand (by tsumo or ron) |
| deal-in | 放銃 | Discarding the tile another player wins on |
| draw (of a round) | 流局 | A round that ends without a win. An exhaustive draw is one where the wall runs out |
| riichi sticks on the table | 供託 | Points placed for riichi and not yet taken |
| dead wall | 王牌 | The tiles at the end of the wall that are not drawn in ordinary turns |
| replacement tile | 嶺上牌 | The tile drawn from the dead wall after a kan or a nuki |
| nuki | 抜き | Setting a tile aside (for example North in three-player mahjong) and drawing a replacement; a tile set aside counts as a dora (nuki dora) |
| chips | 祝儀 | Payments counted separately from points |
| recorder | 記録係 | The program that builds a record event by event (`recorder`) |
| gateway | 接続口 | The program that connects a player (a person or an AI) to the table (`gateway`) |
| game runner | 進行役 | The program that runs a game: it deals, asks the players, and applies the rules (`dealer` module) |
| judgement | 判定 | Deciding yaku, han and fu of a win (`judge`) |
| arena | 対戦場 | The program that lets players play many games against each other |
| bundled | 同梱 | Shipped inside this repository |
| source | 出典 | The published text a rule was written from |
