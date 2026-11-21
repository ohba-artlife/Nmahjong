# examples — a full set of samples (five layers)

One game run by the library itself: the bundled ruleset `nm-2p-4-mps` (4-tile mahjong; 108 tiles of characters, dots and bamboo; two players; east-south), played between the bundled players `simple`.
6 rounds (6 wins, 0 draws), final points [26600, 23400].

| Layer | File | Content |
|---|---|---|
| tileset | `mps_09aebf0d52e66ffe2f1dc98c681c9218dc6a07e945602e265af3af0f4c012fbc.tileset.json` | 108 tiles of characters, dots and bamboo, no red tiles |
| ruleset | `nm-2p-4-mps_5dd7872205e34b48f43c05d1a165e2736b8b24c7762e637b44db85981f3b625a.ruleset.json` | nm-2p-4-mps (bundled; docs/rules/nm-defaults.md §2) |
| wall | `mps_6505b74bf7120c1150304b1c3e6c0f6534ea071093b8a807a4816630ebec891e.wall.json` | The wall of round 1 (source generated, seed `2026-11-18T10:00:00+09:00`) |
| wall | `mps_3e24574e3a77cc8b38a075a0b8f7b7404b3f3703908e6e6c76ac460ca69e6ddd.wall.json` | The wall of round 2 (source generated, seed `2026-11-18T10:00:01+09:00`) |
| wall | `mps_eaed6715d59dbda1e21fe46930eaaf6e2830699097b542aef38ec67161486fea.wall.json` | The wall of round 3 (source generated, seed `2026-11-18T10:00:02+09:00`) |
| wall | `mps_a3b867ada7a192b8e3c97324934bc6fad5b7a7d3f23aa927dc9efe38bcae108a.wall.json` | The wall of round 4 (source generated, seed `2026-11-18T10:00:03+09:00`) |
| wall | `mps_a07871f7c5301da0b2efebdd329e917722c9dbd3fdd1940a3a4af098d6fea430.wall.json` | The wall of round 5 (source generated, seed `2026-11-18T10:00:04+09:00`) |
| wall | `mps_209ee8a7758836e8d45045fda4b2b096aa41e52b784b9a4f0ce4d157ab6f1f9d.wall.json` | The wall of round 6 (source generated, seed `2026-11-18T10:00:05+09:00`) |
| record | `mps_f2f809c6c3a420889a07743d95bc988ad65cbfd82e8db80b3a51cf5825970653.record.json` | The record made by the game runner (dealer), which dealt the walls and added the players' actions one by one |
| annotation | `f2f809c6c3a420889a07743d95bc988ad65cbfd82e8db80b3a51cf5825970653_nm-waits.annotation.json` | The bundled evaluator nm-waits (the number of kinds of waiting tiles for each discard), made each time a discard arrived |

- How it is made: `python3 tools/gen_examples.py` (the seeds and the players are fixed, so the ids are the same however many times it is made)
- Verification: `python3 -m nmahjong validate examples/*.json` (references are looked up in the same folder, and the cross-layer checks pass)
- An example of running a game with the command: `python3 -m nmahjong play nm-2p-4-mps --seed demo --annotate --out /tmp/out` (the seed differs, so it is a different game)
