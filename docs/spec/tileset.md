# tileset — specification of the tileset (nmahjong-tileset 1.0)

Key: MUST = required, MAY = optional, SHOULD = recommended. The container is JSON (UTF-8).

## 1 Purpose
To list, as facts, which tiles exist, how many, which number is which, and which tiles carry a physical mark. It does not hold the meaning of a tile (dora and so on).

## 2 Form

```json
{
  "format": "nmahjong-tileset",
  "version": "1.0",
  "name": "mpsz",
  "id": "sha256:…",
  "tiles": [
    {"id": 0,   "kind": "1m"},
    {"id": 16,  "kind": "5m", "mark": "red"},
    {"id": 124, "kind": "P",  "mark": "pocchi"},
    {"id": 135, "kind": "C"}
  ]
}
```
(Example with an extra tile: name `mpsz-e1`, with `{"id": 136, "kind": "ex", "name": "梅"}` added at the end. K = 137)

| Item | Required | Content |
|---|---|---|
| format | MUST | Fixed: `"nmahjong-tileset"` |
| version | MUST | `"1.0"` |
| name | MUST | `{suits}[-x{count}][-e{count}]`. The suits are those of `m p s z` that are used, in this order. `x` = the number of tiles removed, `e` = the number of tiles added. Examples: `m` / `mps` / `mpsz` / `mpsz-x28` / `mpsz-e8` / `mpsz-x28-e8`. **Marks (red and so on) are not part of the name** |
| id | MUST | `"sha256:"` + the 64 hexadecimal digits of SHA-256( the canonical JSON of `tiles` ). Canonical = keys in dictionary order, separators `,` and `:` only (no whitespace), UTF-8, non-ASCII characters as they are |
| tiles[] | MUST | One row = one tile. K = the number of rows. **1 ≤ K ≤ 256** |
| tiles[].id | MUST | Consecutive numbers starting at 0 |
| tiles[].kind | MUST | Suited tiles `1m`–`9m`, `1p`–`9p`, `1s`–`9s` / honours `E S W N P F C` / extra `ex` |
| tiles[].mark | MAY | A physical mark. A string. Known values: `red` `blue` `pocchi`. Any string is allowed. It has no meaning by itself |
| tiles[].name | MAY | A string. The name of an extra tile and the like |

## 3 Rules for numbers
- Each tile has **four copies** (copy 0→3). Anything other than four copies is expressed with x (removal) and e (addition)
- Order: suits m→p→s, numbers 1→9, copies 0→3 of each number, then honours E S W N P F C (four each), and extras last
- If tiles are removed (x), the numbers are closed up so that they stay consecutive
- Only with `mpsz` (nothing removed) are the numbers the same as Tenhou's 0–135 (characters 0–35, dots 36–71, bamboo 72–107, honours 108–135; by convention the red fives are 16, 52 and 88)

## 4 Reference
Walls, rulesets and records refer to a tileset by the pair `{ "name": "mpsz", "id": "sha256:…" }`. **The id is authoritative**; the name is for display.
Tilesets with the same name but different marks (with red tiles / without) have different ids and are treated as different tilesets.

## 5 Verification
1. `tiles[].id` are consecutive from 0 to K−1, and 1 ≤ K ≤ 256
2. The number of tiles computed from the name (36 each for m/p/s and 28 for z, summed, − x + e) = K
3. kind is in the vocabulary. mark and name are strings
4. id agrees with the hash of tiles

## 6 File name
`{name}_{id, 64 digits}.tileset.json` (the id as its 64 digits; not shortened; ASCII only)
Example: `mpsz_3a9f1c02be77…(64 digits).tileset.json`
