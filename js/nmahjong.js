/* Nmahjong 第二実装（JavaScript、依存なし）。Python 実装と同じテストベクタで order・id が一致することを js/test.js で確かめる。
   範囲（3-1）：正規化 JSON・SHA-256・牌表 id・牌山（fy-sha256-v1 生成・id・検証）・ルール（正規形・id・基本検証）。
   Node（require）とブラウザ（<script>、グローバル NMAHJONG）の両方で動く。 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory();
  else root.NMAHJONG = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // ---- SHA-256（純 JS。Node の crypto にも WebCrypto にも依らない） ---------------------------
  const K256 = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);

  function sha256(bytes) {
    const l = bytes.length;
    const padLen = ((l + 9 + 63) >> 6) << 6;
    const m = new Uint8Array(padLen);
    m.set(bytes);
    m[l] = 0x80;
    const bitLen = l * 8;
    m[padLen - 4] = (bitLen >>> 24) & 0xff; m[padLen - 3] = (bitLen >>> 16) & 0xff; m[padLen - 2] = (bitLen >>> 8) & 0xff; m[padLen - 1] = bitLen & 0xff;
    m[padLen - 5] = Math.floor(bitLen / 0x100000000) & 0xff;
    const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    const w = new Uint32Array(64);
    for (let off = 0; off < padLen; off += 64) {
      for (let i = 0; i < 16; i++) w[i] = (m[off + 4 * i] << 24) | (m[off + 4 * i + 1] << 16) | (m[off + 4 * i + 2] << 8) | m[off + 4 * i + 3];
      for (let i = 16; i < 64; i++) {
        const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
        const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
      }
      let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (let i = 0; i < 64; i++) {
        const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        const ch = (e & f) ^ (~e & g);
        const t1 = (h + S1 + ch + K256[i] + w[i]) >>> 0;
        const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + maj) >>> 0;
        h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0; H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
      H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0; H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
    }
    const out = new Uint8Array(32);
    for (let i = 0; i < 8; i++) { out[4 * i] = H[i] >>> 24; out[4 * i + 1] = (H[i] >>> 16) & 0xff; out[4 * i + 2] = (H[i] >>> 8) & 0xff; out[4 * i + 3] = H[i] & 0xff; }
    return out;
  }
  function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }
  function hex(bytes) { let s = ""; for (const b of bytes) s += (b < 16 ? "0" : "") + b.toString(16); return s; }
  function fromHex(h) { const o = new Uint8Array(h.length / 2); for (let i = 0; i < o.length; i++) o[i] = parseInt(h.substr(2 * i, 2), 16); return o; }
  function utf8(s) { return new TextEncoder().encode(s); }
  function concat(a, b) { const o = new Uint8Array(a.length + b.length); o.set(a); o.set(b, a.length); return o; }

  // ---- 正規化 JSON（Python の json.dumps(sort_keys, separators=(",",":"), ensure_ascii=False) と同じバイト列） -------
  function canonicalString(v) {
    if (v === null || typeof v === "boolean") return JSON.stringify(v);
    if (typeof v === "number") {
      if (!isFinite(v)) throw new ValidationError("NaN／Infinity は JSON にできない");
      return JSON.stringify(v);
    }
    if (typeof v === "string") return JSON.stringify(v);
    if (Array.isArray(v)) return "[" + v.map(canonicalString).join(",") + "]";
    if (typeof v === "object") {
      const keys = Object.keys(v).sort(cmpKey);
      return "{" + keys.map(k => JSON.stringify(k) + ":" + canonicalString(v[k])).join(",") + "}";
    }
    throw new ValidationError("JSON にできない値: " + typeof v);
  }
  // Python の sort_keys は文字列の比較（コードポイント順）。JS の既定 sort は UTF-16 単位なので揃える
  function cmpKey(a, b) {
    const ia = Array.from(a), ib = Array.from(b);
    for (let i = 0; i < Math.min(ia.length, ib.length); i++) {
      const ca = ia[i].codePointAt(0), cb = ib[i].codePointAt(0);
      if (ca !== cb) return ca - cb;
    }
    return ia.length - ib.length;
  }
  function canonicalJson(v) { return utf8(canonicalString(v)); }
  function sha256Id(v) { return "sha256:" + hex(sha256(canonicalJson(v))); }
  function idHex64(id) {
    if (typeof id !== "string" || !id.startsWith("sha256:") || !/^[0-9a-f]{64}$/.test(id.slice(7))) throw new ValidationError("id の形式が sha256:<64 桁> ではない: " + id);
    return id.slice(7);
  }

  class ValidationError extends Error { constructor(m) { super(m); this.name = "ValidationError"; } }

  function deepCopy(v) { return v === undefined ? undefined : JSON.parse(JSON.stringify(v)); }
  function isObj(v) { return v !== null && typeof v === "object" && !Array.isArray(v); }

  // ---- 牌表 --------------------------------------------------------------------------
  const tileset = {
    computeId(ts) { return sha256Id(ts.tiles); },
    K(ts) { return ts.tiles.length; },
    validate(ts) {
      const warns = [];
      if (ts.format !== "nmahjong-tileset") throw new ValidationError("format が nmahjong-tileset ではない");
      if (!Array.isArray(ts.tiles) || !ts.tiles.length) throw new ValidationError("tiles が空");
      ts.tiles.forEach((t, i) => { if (!isObj(t) || t.id !== i) throw new ValidationError(`tiles[${i}].id が ${i} ではない`); if (typeof t.kind !== "string") throw new ValidationError(`tiles[${i}].kind が無い`); });
      if (ts.id !== tileset.computeId(ts)) throw new ValidationError("id がハッシュと一致しない");
      return warns;
    },
    // 牌表を作る（Python の tileset.build と同じ結果・同じ id）。
    //   colors: "m" "p" "s" "z" の組（順は m,p,s,z に直す）。exclude: 除く牌種の配列（各 4 枚）。
    //   marks: { "5m": ["red"] } のように牌種ごとに「1 枚目から順に」印。
    //   extras: エクストラ牌の配列（1 要素 1 枚）。名前の文字列、または { name, mark }
    build(opt) {
      const colors = "mpsz".split("").filter(c => (opt.colors || "").indexOf(c) >= 0).join("");
      if (!colors) throw new ValidationError("色が 1 つも選ばれていない");
      const HON = ["E", "S", "W", "N", "P", "F", "C"];
      const kinds = [];
      for (const c of colors) { if (c === "z") kinds.push(...HON); else for (let n = 1; n <= 9; n++) kinds.push(n + c); }
      const exclude = Array.from(new Set(opt.exclude || []));
      for (const k of exclude) if (kinds.indexOf(k) < 0) throw new ValidationError("除く牌種 " + k + " は選んだ色に無い");
      const marks = opt.marks || {};
      for (const k of Object.keys(marks)) {
        if (kinds.indexOf(k) < 0) throw new ValidationError("印を付ける牌種 " + k + " は選んだ色に無い");   // 除いた牌種への印は無視（Python と同じ）
        if (!Array.isArray(marks[k]) || marks[k].length > 4 || marks[k].some(m => typeof m !== "string" || !m)) throw new ValidationError(k + " の印は 4 枚までの文字列の配列");
      }
      const extras = opt.extras || [];
      const tiles = [];
      for (const kind of kinds) {
        if (exclude.indexOf(kind) >= 0) continue;
        for (let copy = 0; copy < 4; copy++) {
          const t = { id: tiles.length, kind: kind };
          if (marks[kind] && copy < marks[kind].length) t.mark = marks[kind][copy];
          tiles.push(t);
        }
      }
      for (const x of extras) {          // 文字列（名前だけ）か { name, mark }（印つき。ルールの marks で機能を付けられる）
        const t = { id: tiles.length, kind: "ex" };
        if (isObj(x)) { if (x.mark !== undefined) { if (typeof x.mark !== "string" || !x.mark) throw new ValidationError("エクストラ牌の印は文字列"); t.mark = x.mark; } t.name = String(x.name); }
        else t.name = String(x);
        if (!t.name) throw new ValidationError("エクストラ牌の名前が空");
        tiles.push(t);
      }
      if (tiles.length < 1 || tiles.length > 256) throw new ValidationError("枚数 " + tiles.length + " は 1〜256 の外");
      const name = colors + (exclude.length ? "-x" + exclude.length * 4 : "") + (extras.length ? "-e" + extras.length : "");
      const ts = { format: "nmahjong-tileset", version: "1.0", name: name, tiles: tiles };
      ts.id = tileset.computeId(ts);
      return ts;
    },
    filename(ts) { return `${ts.name}_${idHex64(ts.id)}.tileset.json`; },
    label(ts, tid) { const t = ts.tiles[tid]; if (t.kind === "ex") return "ex:" + (t.name || tid); return t.kind + (t.mark === "red" && t.kind[0] === "5" ? "r" : ""); },
  };

  // ---- 牌山 --------------------------------------------------------------------------
  const FY = "fy-sha256-v1";
  function randStream(seed) {
    // SHA-256( seed ‖ BE32 counter ) → 8 個の BE u32。counter は 0 から
    const seedBytes = utf8(seed);
    let counter = 0, buf = [], i = 0;
    return function next() {
      if (i >= buf.length) {
        const c = new Uint8Array(4); c[0] = counter >>> 24; c[1] = (counter >>> 16) & 0xff; c[2] = (counter >>> 8) & 0xff; c[3] = counter & 0xff;
        const h = sha256(concat(seedBytes, c));
        buf = []; for (let j = 0; j < 8; j++) buf.push(((h[4 * j] << 24) | (h[4 * j + 1] << 16) | (h[4 * j + 2] << 8) | h[4 * j + 3]) >>> 0);
        counter += 1; i = 0;
      }
      return buf[i++];
    };
  }
  function fyShuffle(items, seed) {
    // i = K−1 .. 1、j は 0..i を棄却法で一様に
    const a = items.slice();
    const next = randStream(seed);
    for (let i = a.length - 1; i >= 1; i--) {
      const n = i + 1;
      const limit = Math.floor(0x100000000 / n) * n;
      let r;
      do { r = next(); } while (r >= limit);
      const j = r % n;
      const t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }
  const wall = {
    computeId(order, tilesetId) { return "sha256:" + hex(sha256(concat(fromHex(idHex64(tilesetId)), Uint8Array.from(order)))); },
    build(ts, seed, meta) {
      const K = tileset.K(ts);
      const order = fyShuffle(Array.from({ length: K }, (_, i) => i), seed);
      const w = { format: "nmahjong-wall", version: "1.0", tileset: { name: ts.name, id: ts.id }, source: "generated",
        generation: { method: FY, seed: seed }, order: order };
      w.id = wall.computeId(order, ts.id);
      if (meta) w.meta = meta;
      return w;
    },
    validate(w, ts) {
      const warns = [];
      if (w.format !== "nmahjong-wall") throw new ValidationError("format が nmahjong-wall ではない");
      if (w.version !== "1.0") throw new ValidationError("version が 1.0 ではない");
      if (!isObj(w.tileset) || typeof w.tileset.id !== "string") throw new ValidationError("tileset.id が無い");
      if (!Array.isArray(w.order) || !w.order.length) throw new ValidationError("order が空");
      const K = w.order.length;
      const seen = new Uint8Array(K);
      for (const x of w.order) {
        if (!Number.isInteger(x) || x < 0 || x >= K) throw new ValidationError("order に 0〜K−1 の外の番号: " + x);
        if (seen[x]) throw new ValidationError("order に同じ番号が 2 回: " + x);
        seen[x] = 1;
      }
      if (!["generated", "observed", "filled"].includes(w.source)) throw new ValidationError("source が語彙外");
      if (w.source === "generated") {
        if (!isObj(w.generation) || typeof w.generation.seed !== "string") throw new ValidationError("generated には generation.seed");
        if (w.generation.method === FY) {
          const re = fyShuffle(Array.from({ length: K }, (_, i) => i), w.generation.seed);
          if (re.some((v, i) => v !== w.order[i])) throw new ValidationError("order が seed から再現できない");
        }
      }
      if (w.id !== wall.computeId(w.order, w.tileset.id)) throw new ValidationError("id がハッシュと一致しない");
      if (ts) {
        if (ts.id !== w.tileset.id) throw new ValidationError("tileset.id が牌表と違う");
        if (tileset.K(ts) !== K) throw new ValidationError(`K ${K} ≠ 牌表 ${tileset.K(ts)}`);
      } else warns.push("牌表が無いので K と tileset.id は未照合");
      return warns;
    },
    filename(w) { return `${w.tileset.name}_${idHex64(w.id)}.wall.json`; },
  };

  // ---- ルール（正規形・id） ---------------------------------------------------------------
  // 既定値は data/defaults.json（Python 実装から生成）を setDefaults で渡す。bundled.js を読めば自動で入る
  let D = null;
  function setDefaults(d) { D = d; }
  function defaults() {
    if (D) return D;
    if (typeof globalThis !== "undefined" && globalThis.NMAHJONG_BUNDLE) { D = globalThis.NMAHJONG_BUNDLE.defaults; return D; }
    if (typeof require === "function") { try { D = require("./bundled.js").defaults; return D; } catch (e) { /* fallthrough */ } }
    throw new ValidationError("既定値（defaults）が読み込まれていない。bundled.js を読むか setDefaults を呼ぶ");
  }
  function enabledExtra(path, key, given) {
    const d = defaults();
    if (d.enabled_defaults[path] && given.enabled === true) return key in d.enabled_defaults[path];
    return path === "settlement.uma";
  }
  function merge(def, given, path, errors) {
    const d = defaults();
    if (isObj(def)) {
      if (given === undefined || given === null) return deepCopy(def);
      if (!isObj(given)) { errors.push(path + ": オブジェクトであるべき"); return deepCopy(def); }
      if (d.free_key_objects.includes(path)) return deepCopy(given);
      const out = {};
      for (const k of Object.keys(def)) out[k] = (k in given) ? merge(def[k], given[k], path + "." + k, errors) : deepCopy(def[k]);
      for (const k of Object.keys(given)) {
        if (!(k in def)) {
          const opt = d.optional_keys || {};
          if ((path + "." + k) in opt) { if (JSON.stringify(given[k]) !== JSON.stringify(opt[path + "." + k])) out[k] = deepCopy(given[k]); }
          else if (path === "game_rules.scoring" && k === "additive") {
            if (!isObj(given[k])) errors.push(path + ".additive: オブジェクトであるべき");
            else {
              for (const kk of Object.keys(given[k])) if (!(kk in d.additive_defaults)) errors.push(path + ".additive." + kk + ": 未知の項目");
              if (isObj(given[k].karasu)) for (const kk of Object.keys(given[k].karasu)) if (!["menzen", "open"].includes(kk)) errors.push(path + ".additive.karasu." + kk + ": 未知の項目");
              out[k] = deepCopy(given[k]);
            }
          }
          else if (enabledExtra(path, k, given)) out[k] = deepCopy(given[k]);
          else errors.push(path + "." + k + ": 未知の項目");
        }
      }
      if (d.enabled_defaults[path] && out.enabled === true) for (const [k, dv] of Object.entries(d.enabled_defaults[path])) if (!(k in out)) out[k] = deepCopy(dv);
      if (path === "game_rules.scoring" && out.table === "additive") {
        // 足し算の点数：書かなかった項目を既定で埋める
        const ad = isObj(out.additive) ? out.additive : {};
        const full = deepCopy(d.additive_defaults);
        for (const [k, v] of Object.entries(ad)) { if (k === "karasu" && isObj(v)) Object.assign(full.karasu, v); else full[k] = v; }
        out.additive = full;
      }
      return out;
    }
    return (given !== undefined && given !== null) || def === null ? deepCopy(given === undefined ? null : given) : deepCopy(def);
  }
  const ruleset = {
    normalize(rs) {
      const d = defaults();
      if (!isObj(rs)) throw new ValidationError("ruleset がオブジェクトではない");
      const errors = [];
      const out = {};
      for (const k of Object.keys(rs)) if (!d.top_keys.includes(k)) errors.push(k + ": 未知の項目");
      for (const k of ["format", "version", "name", "id", "tileset", "players", "hand_size", "length", "rounds_total", "winds", "unknown", "meta"]) if (k in rs) out[k] = deepCopy(rs[k]);
      if (isObj(rs.wall_rules)) { out.wall_rules = deepCopy(rs.wall_rules); for (const k of Object.keys(rs.wall_rules)) if (!d.wall_rules_keys.includes(k)) errors.push("wall_rules." + k + ": 未知の項目"); if (out.wall_rules.rinshan_reserved === false) delete out.wall_rules.rinshan_reserved; }
      else out.wall_rules = rs.wall_rules === undefined ? undefined : rs.wall_rules;
      for (const sect of ["game_rules", "end", "settlement"]) {
        const given = rs[sect] == null ? {} : rs[sect];
        const merged = merge(d[sect], given, sect, errors);
        for (const p of d.passthrough) {
          if (!p.startsWith(sect + ".")) continue;
          const key = p.slice(sect.length + 1);
          if (key.includes(".")) { const [a, b] = key.split("."); if (isObj(given[a]) && b in given[a]) merged[a][b] = deepCopy(given[a][b]); }
          else if (key in given) merged[key] = deepCopy(given[key]);
        }
        out[sect] = merged;
      }
      const sg = rs.settlement || {};
      if (!("uma" in sg) && Number.isInteger(rs.players) && rs.players !== 4) out.settlement.uma = new Array(rs.players).fill(0);
      if (errors.length) throw new ValidationError(errors.join("; "));
      if (out.wall_rules === undefined) delete out.wall_rules;
      return out;
    },
    computeId(norm) { const o = {}; for (const k of Object.keys(norm)) if (!["id", "name", "meta"].includes(k)) o[k] = norm[k]; return sha256Id(o); },
    finalize(rs) { const n = ruleset.normalize(rs); n.id = ruleset.computeId(n); return n; },
    filename(rs) { return `${rs.name}_${idHex64(rs.id)}.ruleset.json`; },
    // 基本検証：正規形にできる・id 一致・語彙（enum 表にある項目）。完全な §5 検証は Python 実装が正
    validate(rs) {
      const n = ruleset.normalize(rs);
      if (n.format !== "nmahjong-ruleset") throw new ValidationError("format が nmahjong-ruleset ではない");
      if (rs.id !== undefined && rs.id !== ruleset.computeId(n)) throw new ValidationError("id がハッシュと一致しない");
      const d = defaults();
      const errs = [];
      walk(n, "", (path, v) => {
        const key = path.split(".").pop();
        const parent = path.split(".").slice(-2).join(".");
        const vocab = d.enum[parent] || d.enum[key];
        if (vocab && typeof v === "string" && !vocab.includes(v)) errs.push(path + ": 語彙外 " + JSON.stringify(v));
      });
      if (errs.length) throw new ValidationError(errs.join("; "));
      return [];
    },
    // 画面用：正規形を path → 値 の一覧に
    flatten(obj, prefix) {
      const out = [];
      walk(obj, prefix || "", (p, v) => out.push([p, v]));
      return out;
    },
    setPath(obj, path, value) {
      const parts = path.split(".");
      let o = obj;
      for (let i = 0; i < parts.length - 1; i++) { if (!isObj(o[parts[i]])) o[parts[i]] = {}; o = o[parts[i]]; }
      o[parts[parts.length - 1]] = value;
    },
    diff(a, b) {
      const fa = new Map(ruleset.flatten(a)), fb = new Map(ruleset.flatten(b));
      const out = [];
      for (const [k, v] of fb) if (!fa.has(k) || JSON.stringify(fa.get(k)) !== JSON.stringify(v)) out.push([k, fa.has(k) ? fa.get(k) : undefined, v]);
      for (const [k, v] of fa) if (!fb.has(k)) out.push([k, v, undefined]);
      return out;
    },
  };
  function walk(v, path, fn) {
    if (isObj(v) && Object.keys(v).length) { for (const k of Object.keys(v)) walk(v[k], path ? path + "." + k : k, fn); }
    else fn(path, v);
  }

  return { sha256, hex, canonicalJson, canonicalString, sha256Id, idHex64, ValidationError, tileset, wall, ruleset, randStream, fyShuffle, setDefaults, FY };
});
