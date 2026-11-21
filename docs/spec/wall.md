# wall — specification of the wall (nmahjong-wall 1.0)

Key: MUST = required, MAY = optional, SHOULD = recommended. The container is JSON (UTF-8). For tilesets see tileset.md.

## 1 Purpose
To hold the order of the tiles (the order in which they are consumed) as one sequence. It does not hold the dead wall, the dora, the way of dealing or where taking starts (these are in wall_rules of the ruleset).
"How much is fact" (source) and "which table read it" (device) are separate axes; both can be written.

## 2 Form

```json
{
  "format": "nmahjong-wall",
  "version": "1.0",
  "tileset": { "name": "mpsz", "id": "sha256:…" },
  "source": "generated",
  "generation": { "method": "fy-sha256-v1", "seed": "2026-11-11T10:00:00+09:00" },
  "order": [111, 48, 119, "…"],
  "id": "sha256:3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c",
  "meta": { "created_at": "2026-11-11T10:00:00+09:00", "created_by": "nmahjong-cli" }
}
```

Example of a wall read by a physical table:
```json
{
  "format": "nmahjong-wall",
  "version": "1.0",
  "tileset": { "name": "mpsz", "id": "sha256:…" },
  "source": "observed",
  "device": { "id": "T-0001", "maker": "…", "model": "…", "firmware": "1.2", "at": "2026-11-13T19:05:31+09:00" },
  "order": [31, 7, 0, "…"],
  "id": "sha256:…"
}
```

| Item | Required | Content |
|---|---|---|
| format | MUST | Fixed: `"nmahjong-wall"` |
| version | MUST | `"1.0"` |
| tileset | MUST | `{ name, id }`. The numbers in order are indexes into this tileset |
| source | MUST | `generated` (all generated) / `observed` (all fact) / `filled` (part fact, the rest generated) |
| generation | depends on source | `{ method, seed, round? }`. It must be able to reproduce the whole order |
| observed | depends on source | The positions that are fact. A list of half-open ranges `[start, end)`. Ascending, merged, not overlapping, 0 ≤ start < end ≤ K |
| fill | depends on source | How the empty positions are filled: `{ method: "fy-sha256-v1", seed }` |
| device | MAY | The table that read the order. `{ id, maker?, model?, firmware?, at? }`. at is the time of reading |
| order | MUST | A permutation of numbers. Its length is always K. Position 0 is the tile taken first. The physical layout (four sides, two tiers) is not held |
| id | MUST | `"sha256:"` + SHA-256( **the 32 bytes of the tileset id** (its 64 hexadecimal digits as bytes) ‖ order as bytes, one byte per tile ). For filled it is also computed over the whole length. A different tileset gives a different id for the same order (so `mpsz` with red tiles and `mpsz` without do not collide). The definition was changed on 2026-11-15 (before: order only) |
| meta | MAY | created_at, created_by, from, ref, round and so on, freely |

Required / forbidden items per source:

| source | generation | observed | fill | device |
|---|---|---|---|---|
| generated | MUST | forbidden | forbidden | forbidden |
| observed | MAY (present for a reproduction of Tenhou; absent for a physical table) | forbidden | forbidden | MAY (SHOULD when a physical table read it) |
| filled | forbidden | MUST | MUST | forbidden |

Where a wall comes from:
- a. Random numbers in software (reproducible from a seed) → `generated`, no device
- b. A physical table built the wall and read the order from ID tags in the tiles → `observed`, with device
- d. An import in which part is fact and the rest is generated (Mahjong Soul) → `filled`, with the observed ranges and fill, and meta.from/ref
- e. An import in which everything is reproduced (Tenhou) → `observed`, with generation (tenhou-…-nm1, seed, round)

## 3 Generation procedure `fy-sha256-v1`
1. Turn the seed into UTF-8 bytes
2. Compute SHA-256( seed ‖ a 4-byte big-endian counter ) and use it, in order, as eight 32-bit big-endian random numbers. When they are used up, add 1 to the counter
3. On the initial sequence `[0,1,…,K-1]`, for i = K−1 … 1 in this order: bound = i+1, limit = floor(2^32 / bound) × bound; if the random number x ≥ limit, draw again; j = x mod bound; swap [i] and [j]
4. The result is order

The seed is a string. An ISO 8601 date and time to the second, with the time offset, is SHOULD. A device that makes several walls in the same second appends `/device-name`.

**Test vector** (K=136, seed `2026-11-11T10:00:00+09:00`):
order = [111,48,119,67,76,94,38,1,26,86,49,40,32,37,112,22,83,61,70,7,44,4,124,75,109,47,91,33,100,58,108,23,59,126,50,85,52,0,2,39,18,87,68,73,28,65,5,57,19,98,31,97,8,80,3,125,104,79,30,134,29,41,84,36,56,53,127,13,123,130,114,115,45,90,43,69,103,62,54,10,6,110,9,92,42,131,121,12,51,15,20,25,93,63,89,96,128,102,71,78,88,95,46,27,74,101,113,116,66,35,24,72,133,122,81,117,17,14,34,118,82,120,21,105,107,77,55,129,64,135,132,99,16,11,60,106]
id = `sha256:3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c` (paired with the tileset mpsz with three red tiles, id `sha256:a42613018724ca161585b15bae544fb4f8cb477a64efb3f944b0acb3d913db04`)

## 4 Reproduction procedure `tenhou-mt19937ar-sha512-n288-nm1`
1. The seed of Tenhou's SHUFFLE (base64) → 624 32-bit little-endian numbers → MT19937ar `init_by_array`
2. For round `round` (starting at 0), advance `genrand_int32` 288×(round+1) times and use the last 288 numbers
3. Take them 32 at a time as 128 little-endian bytes and apply SHA-512 → sixteen 32-bit little-endian numbers each, 144 in total
4. Make the 136-tile sequence yama with Tenhou's exchange shuffle (i = 0…135, j = i + rnd[i] mod (136−i)). Tenhou's direction: tiles are drawn from yama[135] downwards, and yama[0..13] is the dead wall. Dice = (rnd[135] mod 6, rnd[136] mod 6) (the 4th and 5th of INIT.seed, counting from 0)
5. **nm1 conversion**: arrange the first N×M+1 tiles as "N tiles each from the dealer (keeping Tenhou's order of taking: 4 tiles × 3, then 1) → one tile to the dealer", continue with the later draws (yama[pos] … yama[14]), and put the dead wall last, reversed (yama[13] … yama[0]). The set of tiles dealt to each player and the order of later draws are the same as Tenhou's

Items of generation: `{ method, seed, round, oya, players, hand }`. **Without oya (the dealer's seat in that round) the head cannot be rearranged**, so it is MUST. players and hand default to 4 and 13.

Offsets inside the dead wall (in the order of this specification, with the first of the last 14 tiles as 0): dora indicator **8**, ura **9**, kan dora **[6,4,2,0]**, kan ura **[7,5,3,1]**, replacement tiles **[12,13,10,11]** (in Tenhou's array: yama[5], [4], [7,9,11,13], [6,8,10,12], [1,0,3,2]).

For three-player games, the 108 tiles without 2m–8m (in ascending order of Tenhou's numbers) are shuffled directly with rnd[i] mod (108−i), and the numbers are mapped to the tileset `mpsz-x28`.

**Checked** (2026-11-15): on the real game log 2019051522gm-00a9-0000-8c64c236 (10 rounds, 3 kans), the deals of all four players, every draw, the replacement tiles, the dora indicators, the kan dora and the dice agree in every round (tests/test_tenhou_logs.py, which runs when logs are placed). After that, 1,005 games including 278 three-player games were checked in the same way (conformance.md §5).

## 5 Filling procedure (fill)
1. The tiles that were not seen = all numbers of the tileset − the numbers placed at observed positions. Arrange them **in ascending order of number**
2. Shuffle them with `fy-sha256-v1` (fill.seed)
3. Go through the positions not contained in observed in ascending order and place the tiles from the head

fill.seed is `"<origin>:<original ID>:<round>"` (for example `jantama:250101-abcd:3`).

## 5.1 Entrance for a physical table: a sequence of tag ids → tile numbers (tagmap)
The order that a physical table reads from the ID tags of the tiles (RFID and the like) arrives as a sequence of tag strings specific to the table. The mapping to tile numbers is held in a separate file, the **tagmap**, and `build_from_tags(tileset, tagmap, tags, device)` turns it into a wall with `source: observed` (no generation, with device).
```json
{ "format": "nmahjong-tagmap", "version": "1.0",
  "tileset": { "name": "mpsz", "id": "sha256:…" },
  "tags": { "E20000A1": 0, "E20000A2": 1, "…": 135 } }
```
- tags maps a tag string → a tile number. **Every tile must have a tag** (their number = K), and no tile number may be repeated. A different tileset needs a different tagmap
- The sequence read is in the order of consumption (the first is the tile taken first). An unknown tag, a duplicate or a missing tile is an error. A table that can read only part of the wall uses `filled` (§5)
- Command: `nmahjong build --tileset mpsz --tags read.txt --tagmap tagmap.json --device T-0001 --device-at 2026-…`
- The register of tables and tags (which table has the tiles with which tags) belongs to the application. This specification holds only the form of the mapping and the conversion

## 6 Representations
Three containers for the same order: a JSON array (authoritative) / bytes (one byte per tile, K bytes) / a comma-separated string.

## 7 Verification
1. tileset.id agrees with an existing tileset, and K agrees
2. The length of order is K, each number is 0 to K−1, and there are no duplicates
3. If generation is present, the order rebuilt from it is the same
4. If observed is present, the ranges are consistent, and the set of tiles at positions outside observed = the tileset − the observed tiles
5. If fill is present, running it again gives the same result
6. id agrees
7. The table of required / forbidden items per source is satisfied

## 8 File name
`{tileset.name}_{id, 64 digits}.wall.json` (the id as its 64 digits; not shortened; ASCII only)
Example: `mpsz_3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c.wall.json`
