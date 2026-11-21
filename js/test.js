/* 試験 T8：Python 実装と同じテストベクタ・同梱データで一致することを確かめる。node test.js */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const NM = require("./nmahjong.js");
const B = require("./bundled.js");

let n = 0;
function t(name, fn) { fn(); n++; console.log("ok", name); }

t("T8-0 sha256 既知値", () => {
  assert.strictEqual(NM.hex(NM.sha256(new TextEncoder().encode("abc"))), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  assert.strictEqual(NM.hex(NM.sha256(new Uint8Array(0))), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  assert.strictEqual(NM.hex(NM.sha256(new TextEncoder().encode("a".repeat(200)))), require("crypto").createHash("sha256").update("a".repeat(200)).digest("hex"));
});

t("T8-1 牌山テストベクタ（K=136, seed 2026-11-11T10:00:00+09:00）", () => {
  const ts = B.tilesets.find(x => x.id === "sha256:a42613018724ca161585b15bae544fb4f8cb477a64efb3f944b0acb3d913db04");   // mpsz（赤 3 枚）
  const w = NM.wall.build(ts, "2026-11-11T10:00:00+09:00");
  assert.deepStrictEqual(w.order.slice(0, 4), [111, 48, 119, 67]);
  assert.strictEqual(w.id, "sha256:3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c");
  assert.deepStrictEqual(NM.wall.validate(w, ts), []);
  assert.strictEqual(NM.wall.filename(w), "mpsz_3fa2bbc6c633c1a4dbb05b1c2e7258a6c0119829dcebd9e035c89b8a15c07f1c.wall.json");
});

t("T8-2 壊した牌山を断る", () => {
  const ts = B.tilesets.find(x => x.id === "sha256:a42613018724ca161585b15bae544fb4f8cb477a64efb3f944b0acb3d913db04");
  const w = NM.wall.build(ts, "2026-11-11T10:00:00+09:00");
  const bad1 = JSON.parse(JSON.stringify(w)); bad1.order[0] = bad1.order[1];
  assert.throws(() => NM.wall.validate(bad1, ts), /2 回/);
  const bad2 = JSON.parse(JSON.stringify(w)); bad2.order.pop();
  assert.throws(() => NM.wall.validate(bad2, ts), /再現|K/);
  const bad3 = JSON.parse(JSON.stringify(w)); bad3.id = "sha256:" + "0".repeat(64);
  assert.throws(() => NM.wall.validate(bad3, ts), /id/);
  const bad4 = JSON.parse(JSON.stringify(w)); bad4.tileset.id = B.tilesets.find(x => x.name === "mpsz" && x.id !== ts.id).id;
  assert.throws(() => NM.wall.validate(bad4, ts), /id|tileset/);
  const nored = B.tilesets.find(x => x.name === "mpsz" && x.id !== ts.id);
  assert.notStrictEqual(NM.wall.build(nored, "2026-11-11T10:00:00+09:00").id, w.id);   // 牌表が違えば別 id
});

t("T8-3 同梱牌表の id が Python と一致", () => {
  for (const ts of B.tilesets) { assert.strictEqual(NM.tileset.computeId(ts), ts.id, ts.name); assert.deepStrictEqual(NM.tileset.validate(ts), []); }
  // 牌表を作る：同梱 10 本と同じ指定で作ると同じ id
  const red3 = { "5m": ["red"], "5p": ["red"], "5s": ["red"] };
  const sanma = ["2m", "3m", "4m", "5m", "6m", "7m", "8m"];
  const specs = [
    { colors: "mpsz", marks: red3 }, { colors: "mpsz" }, { colors: "mpsz", exclude: sanma, marks: red3 }, { colors: "mpsz", exclude: sanma },
    { colors: "mpsz", exclude: sanma, marks: { "5p": ["red", "red", "red", "red"], "5s": ["red", "red", "red", "red"] } },
    { colors: "m", marks: { "3m": ["red"], "5m": ["red"], "7m": ["red"] } }, { colors: "m" }, { colors: "mps" },
    { colors: "mpsz", marks: { "5m": ["red", "gold"], "5p": ["red", "gold"], "5s": ["red", "gold"], "P": ["pocchi", "reverse_pocchi"] } },
    { colors: "mpsz", marks: red3, extras: ["梅", "蘭", "菊", "竹", "春", "夏", "秋", "冬"] },
  ];
  const builtIds = specs.map(o => { const t = NM.tileset.build(o); assert.deepStrictEqual(NM.tileset.validate(t), []); return t.id; });
  assert.deepStrictEqual(builtIds.slice().sort(), B.tilesets.map(t => t.id).sort());
  assert.strictEqual(NM.tileset.build({ colors: "zsp" }).name, "psz");
  // エクストラ牌に印（花牌など。機能はルールの marks・nuki で付ける）。Python の tileset new --extra 梅=flower,蘭=flower,菊,竹 と同じ id
  const fl = NM.tileset.build({ colors: "mpsz", marks: { P: ["pocchi"] }, extras: [{ name: "梅", mark: "flower" }, { name: "蘭", mark: "flower" }, "菊", "竹"] });
  assert.strictEqual(fl.id, "sha256:35719497457bf1980500b0995e1d4cac16e1d970e67f4b82922337320ab39acf");
  assert.deepStrictEqual(fl.tiles.slice(136), [{ id: 136, kind: "ex", mark: "flower", name: "梅" }, { id: 137, kind: "ex", mark: "flower", name: "蘭" }, { id: 138, kind: "ex", name: "菊" }, { id: 139, kind: "ex", name: "竹" }]);
  assert.throws(() => NM.tileset.build({ colors: "" }), /色/);
  assert.throws(() => NM.tileset.build({ colors: "m", exclude: ["5p"] }), /無い/);
  assert.throws(() => NM.tileset.build({ colors: "m", marks: { "5m": ["a", "b", "c", "d", "e"] } }), /4 枚/);
  assert.strictEqual(B.tilesets.length, 10);
});

t("T8-4 同梱ルール 46 本の正規形と id が Python と一致", () => {
  assert.strictEqual(B.rulesets.length, 46);
  for (const rs of B.rulesets) {
    const n = NM.ruleset.normalize(rs);
    assert.strictEqual(NM.canonicalString(n), NM.canonicalString(rs), rs.name + " 正規形が変わる");
    assert.strictEqual(NM.ruleset.computeId(n), rs.id, rs.name);
    assert.deepStrictEqual(NM.ruleset.validate(rs), [], rs.name);
  }
});

t("T8-5 省略形から同じ id（既定値の埋め方が Python と同じ）", () => {
  const base = B.rulesets.find(x => x.name === "tenhou-4p-hanchan-red");
  // 既定値と同じ項目を消しても同じ id になる
  const sparse = JSON.parse(JSON.stringify(base));
  delete sparse.game_rules.scoring.round_to; delete sparse.end.cold_points; delete sparse.id;
  assert.strictEqual(NM.ruleset.finalize(sparse).id, base.id);
  // 変えれば変わる、未知キーは断る
  const changed = JSON.parse(JSON.stringify(base)); changed.game_rules.flow.chi = false; delete changed.id;
  assert.notStrictEqual(NM.ruleset.finalize(changed).id, base.id);
  const unknown = JSON.parse(JSON.stringify(base)); unknown.game_rules.bogus = 1;
  assert.throws(() => NM.ruleset.normalize(unknown), /未知/);
});

t("T8-6 正規化 JSON（キー順・非 ASCII・整数値）", () => {
  const s = new TextDecoder().decode(NM.canonicalJson({ b: 1, a: [1.5, 2, "あ", null, true], "ß": { z: 0, y: "x" } }));
  assert.strictEqual(s, '{"a":[1.5,2,"あ",null,true],"b":1,"ß":{"y":"x","z":0}}');
});

t("T8-V 適合性のテストベクタ（tests/vectors/conformance.json。Python と同じファイルを読んで計算し直す）", () => {
  const crypto = require("crypto");
  const root = path.join(__dirname, "..");
  const v = JSON.parse(fs.readFileSync(path.join(root, "tests", "vectors", "conformance.json"), "utf8"));
  const sha = bytes => crypto.createHash("sha256").update(Buffer.from(bytes)).digest("hex");
  assert.ok(v.canonical_json.length >= 9);
  for (const c of v.canonical_json) {
    assert.strictEqual(NM.canonicalString(c.value), c.canonical);
    assert.strictEqual(NM.sha256Id(c.value), c.id);
  }
  for (const c of v.fy_sha256_v1) {
    const order = NM.fyShuffle(Array.from({ length: c.n }, (_, i) => i), c.seed);
    assert.strictEqual(sha(order), c.sha256_of_bytes, `${c.n} ${c.seed}`);
    const head = c.order || c.head;
    assert.deepStrictEqual(order.slice(0, head.length), head);
  }
  assert.strictEqual(v.tilesets.length, 10);
  for (const c of v.tilesets) {
    const ts = JSON.parse(fs.readFileSync(path.join(root, c.file), "utf8"));
    assert.deepStrictEqual([NM.tileset.computeId(ts), ts.id, ts.name, ts.tiles.length], [c.id, c.id, c.name, c.K]);
  }
  for (const c of v.walls) {
    const ts = B.tilesets.find(x => x.id === c.tileset.id);
    const w = NM.wall.build(ts, c.seed);
    assert.deepStrictEqual([w.id, w.order.slice(0, 8), w.order.slice(-4), sha(w.order)], [c.id, c.head, c.tail, c.sha256_of_bytes], c.seed);
  }
  assert.strictEqual(v.rulesets.length, 46);
  for (const c of v.rulesets) {
    const rs = JSON.parse(fs.readFileSync(path.join(root, c.file), "utf8"));
    assert.deepStrictEqual([NM.ruleset.computeId(NM.ruleset.normalize(rs)), rs.id, rs.name], [c.id, c.id, c.name]);
  }
});

console.log(`${n} tests OK`);
