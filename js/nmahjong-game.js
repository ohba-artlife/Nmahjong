/* Nmahjong 第二実装（JavaScript）の 4 層・5 層：点数、局面の再現と合法手、役と符の判定、対局の検証、記録係、進行役、逐次の評価。
   Python 実装（nmahjong/scoring.py・observe.py・judge.py・record.py・recorder.py・dealer.py・evaluate.py）を同じ手順で移したもの。
   Python と同じ結果になることを js/test_game.js で確かめる。nmahjong.js と bundled.js が要る。
   Node（require）とブラウザ（<script>、グローバル NMAHJONG_GAME）の両方で動く。
   生成物：js/src/game_*.js をつないだもの（tools/gen_js_game.py）。直すときは src を直す。 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory(require("./nmahjong.js"), require("./bundled.js"));
  else root.NMAHJONG_GAME = factory(root.NMAHJONG, root.NMAHJONG_BUNDLE);
})(typeof globalThis !== "undefined" ? globalThis : this, function (NM, BUNDLE) {
  "use strict";
  const ValidationError = NM.ValidationError;
  const VOCAB = BUNDLE.vocab;
  const YAKU_TABLES = BUNDLE.yaku_tables;
  const deepCopy = v => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
  const isObj = v => v !== null && typeof v === "object" && !Array.isArray(v);
  const sum = a => a.reduce((x, y) => x + y, 0);
  const range = n => Array.from({ length: n }, (_, i) => i);
  const numSort = a => a.slice().sort((x, y) => x - y);
  const canon = v => (v === undefined ? "undefined" : NM.canonicalString(v));      // キーの並びに依らない比較
  const eq = (a, b) => a === b || canon(a) === canon(b);
  const mod = (a, m) => ((a % m) + m) % m;

  // ruleset の正規形は何度も引くので、オブジェクトごとに覚えておく
  const _normCache = new WeakMap();
  function normalize(rs) {
    let n = _normCache.get(rs);
    if (!n) { n = NM.ruleset.normalize(rs); _normCache.set(rs, n); }
    return n;
  }

  // ==== 点数と精算（scoring.py） ===============================================================
  const ceil100 = x => Math.ceil(x / 100) * 100;

  function basePoints(fu, han, yakuman, sc) {
    const lm = sc.limits;
    if (yakuman) return 2000 * lm.yakuman_base * Math.min(yakuman, lm.max_multiple);
    if (sc.table === "custom:nm1-limits") {
      if (lm.kazoe_from && han >= lm.kazoe_from) return 2000 * lm.yakuman_base;
      if (han >= lm.sanbaiman_from) return 6000;
      if (han >= 8) return 4000;
      return 3000;
    }
    if (lm.kazoe_from && han >= lm.kazoe_from) return 2000 * lm.yakuman_base;
    if (han >= lm.sanbaiman_from) return 6000;
    if (han >= 8) return 4000;
    if (han >= 6) return 3000;
    if (han >= 5) return 2000;
    if (!sc.fu.enabled) fu = 20;
    const b = fu * Math.pow(2, han + 2);
    if (b >= 2000 || (sc.mangan_round_up && b >= 1920)) return 2000;
    return b;
  }

  /* [合計点, 支払い内訳（相手ごと）]。本場・供託は含まない。 */
  /* 三人打ちのツモの払い（scoring.tsumo_loss）。loss＝そのまま、add_1000＝各自 +1000、marudori＝ロンの点を分ける（子のツモは子＝ロン÷3 切り捨て・親＝残り、親のツモはロン÷2 切り上げ）、
     north_split＝子のツモは子×1.5 切り捨て・親＋子÷2 切り上げ（親のツモは丸取りと同じ）、none（方式の指定なし）＝丸取り。 */
  function threePlayerTsumo(parts, b, isDealer, mode) {
    if (mode === "add_1000") return parts.map(p => p + 1000);
    if (mode === "marudori" || mode === "north_split" || mode === "none") {
      const ron = ceil100(b * (isDealer ? 6 : 4));
      if (isDealer) { const each = ceil100(ron / 2); return [each, each]; }
      if (mode === "north_split") { const c = parts[1]; return [ceil100(parts[0] + c / 2), Math.floor(Math.floor(c * 3 / 2) / 100) * 100]; }
      const child = Math.floor(ron / 300) * 100;
      return [ron - child, child];
    }
    return parts;
  }
  // ---- 足し算の点数（scoring.table＝additive） ----
  // カラス（抜く牌を 1 枚も持たない和了）か。"menzen"／"open"／null
  function karasuKind(kindsInHand, nukiCount, menzen, nukiRule) {
    if (!(nukiRule && nukiRule.enabled)) return null;
    const tiles = nukiRule.tiles || [];
    if (nukiCount || kindsInHand.some(k => tiles.includes(k))) return null;
    return menzen ? "menzen" : "open";
  }
  // 1 人が払う点と内訳。点＝（翻×per_han＋役満の点＋base＋親なら dealer＋本場×honba）×multiplier を round_to の単位に切り上げ、カラスの点を足す
  function additivePoints(han, yakuman, isDealer, honba, karasu, sc) {
    const a = sc.additive;
    const ym = yakuman ? Math.min(yakuman, sc.limits.max_multiple) : 0;
    const hon = (isDealer || !a.honba_dealer_only) ? honba : 0;
    const parts = { han: han * a.per_han, yakuman: ym * a.yakuman, base: a.base, dealer: isDealer ? a.dealer : 0, honba: hon * a.honba };
    const raw = (parts.han + parts.yakuman + parts.base + parts.dealer + parts.honba) * a.multiplier;
    let each = Math.ceil(raw / a.round_to) * a.round_to;
    parts.karasu = karasu ? a.karasu[karasu] : 0;
    each += parts.karasu;
    parts.each = each;
    return [each, parts];
  }
  function totalPoints(fu, han, yakuman, isDealer, isTsumo, players, sc) {
    if (sc.table === "additive") throw new ValidationError("scoring.table＝additive の点数は additivePoints で出す（本場とカラスが要る）");
    const b = basePoints(fu, han, yakuman, sc);
    const pay = sc.payment;
    if (pay === "standard" && (sc.round_to || 100) !== 100) {     // 1000 点単位：各自の払い（ロンは合計）を切り上げる
      const u = sc.round_to;
      let parts = totalPoints(fu, han, yakuman, isDealer, isTsumo, players, Object.assign({}, sc, { round_to: 100, tsumo_table: null }))[1].map(p => Math.ceil(p / u) * u);
      const tt = sc.tsumo_table;
      if (tt && isTsumo && !isDealer && players === 3) {
        // 子のツモの払いを表で決める（店の点数表。キー＝同じ手のロンの点、値＝[親の払い, 子の払い]）。表に無い点は上の式
        const ron = totalPoints(fu, han, yakuman, false, false, players, sc)[0];
        if (String(ron) in tt) parts = tt[String(ron)].slice();
      }
      return [sum(parts), parts];
    }
    if (sc.tsumo_table && pay === "standard" && isTsumo && !isDealer && players === 3) {
      const ron = totalPoints(fu, han, yakuman, false, false, players, sc)[0];
      if (String(ron) in sc.tsumo_table) { const parts = sc.tsumo_table[String(ron)].slice(); return [sum(parts), parts]; }
    }
    if (pay === "standard") {
      if (isTsumo) {
        if (players === 1) return [0, []];
        let parts = isDealer ? new Array(players - 1).fill(ceil100(b * 2)) : [ceil100(b * 2)].concat(new Array(players - 2).fill(ceil100(b)));
        if (players === 3) parts = threePlayerTsumo(parts, b, isDealer, sc.tsumo_loss || "none");
        return [sum(parts), parts];
      }
      const total = ceil100(b * (isDealer ? 6 : 4));
      return [total, [total]];
    }
    if (isTsumo && pay === "4p_dealer_share_from_opponent") { const share = ceil100(b * 2); return [share, [share]]; }
    if (isTsumo) {
      const four = isDealer ? ceil100(b * 2) * 3 : ceil100(b * 2) + 2 * ceil100(b);
      if (pay === "4p_total_from_opponent") return [four, [four]];
      if (pay === "4p_child_half_from_opponent") { const half = Math.floor((ceil100(b * 2) + 2 * ceil100(b)) / 2); return [half, [half]]; }
    }
    const total = ceil100(b * (isDealer ? 6 : 4));
    return [total, [total]];
  }

  function ranks(scores, tie) {
    const M = scores.length;
    const order = range(M).sort((i, j) => (scores[j] - scores[i]) || (i - j));
    const out = new Array(M).fill(0);
    if (tie === "seat_order") { order.forEach((i, r) => { out[i] = r + 1; }); return out; }
    let r = 0;
    order.forEach((i, k) => { if (k === 0 || scores[i] !== scores[order[k - 1]]) r = k + 1; out[i] = r; });
    return out;
  }

  function rankShare(arr, rk, i, tie) {
    const r = rk[i];
    if (tie === "seat_order") return arr[r - 1];
    const same = range(rk.length).filter(j => rk[j] === r);
    if (same.length === 1) return arr[r - 1];
    return sum(same.map((_, k) => arr[r - 1 + k])) / same.length;
  }

  const round4 = x => { const v = Math.round(x * 10000) / 10000; return Object.is(v, -0) ? 0 : v; };

  function settle(scores, st, rounding) {
    const M = scores.length;
    const unit = st.unit.points_per_unit;
    const rd = rounding || st.rounding || { score_to_1000: "none", remainder_to_top: false };
    const rk = ranks(scores, st.tie);
    const raw = scores.map(s => {
      if (rd.score_to_1000 === "none") return (s - st.return_points) / unit;
      const thr = rd.score_to_1000 === "half_up_600" ? 600 : 500;
      const a = Math.abs(s), q = Math.floor(a / 1000), r = a % 1000;
      let k = q + (r >= thr ? 1 : 0);
      if (s < 0) k = -k;
      return k - Math.floor(st.return_points / 1000);
    });
    let arr = st.uma;
    if (isObj(arr)) {
      const th = arr.threshold === undefined ? "return" : arr.threshold;
      const thv = th === "return" ? st.return_points : th === "start" ? st.start_points : th;
      const inc = arr.includes_threshold === undefined ? true : arr.includes_threshold;
      let nf = scores.filter(s => (inc ? s >= thv : s > thv)).length;
      nf = Math.min(Math.max(nf, 1), M - 1);
      arr = arr.by_floating[String(nf)];
    }
    const out = range(M).map(i => raw[i] + rankShare(arr, rk, i, st.tie));
    const okaTotal = (st.return_points - st.start_points) * M / unit;
    const tops = range(M).filter(i => rk[i] === 1);
    if (okaTotal && st.oka !== "none") for (const i of tops) out[i] += okaTotal / tops.length;
    if (rd.remainder_to_top) {
      const others = sum(range(M).filter(i => !tops.includes(i)).map(i => out[i]));
      for (const i of tops) out[i] = -others / tops.length;
    }
    return out.map(round4);
  }

  // ---- 祝儀（settlement.chips） ----
  const CHIP_YAKU = { haitei: ["haitei"], houtei: ["houtei"], tsumo: ["menzen_tsumo"] };
  // 和了 1 つに付く祝儀の枚数を、払い手の決まりごとに返す：{loser, all}。loser＝ロンは放銃者、ツモは残りの全員。all＝いつも残りの全員
  function winChips(rules, ts, tiles, yaku, yakuman, tsumo, menzen, winTile) {
    const out = { loser: 0, all: 0 };
    const han = {}; for (const y of yaku) han[y.name] = y.han || 0;
    for (const c of rules || []) {
      const w = c.when === undefined ? "always" : c.when;
      if ((w === "menzen" && !menzen) || (w === "tsumo" && !tsumo) || (w === "ron" && tsumo) || !(c.payer in out)) continue;
      let n;
      if (c.on === "win_with_mark") {
        const pool = c.win_tile ? [winTile] : tiles;
        n = pool.filter(t => t !== null && t !== undefined && (!("mark" in c) || (ts.tiles[t].mark === undefined ? null : ts.tiles[t].mark) === c.mark)
          && (!("tile_kind" in c) || ts.tiles[t].kind === c.tile_kind) && (!("tile_id" in c) || t === c.tile_id)
          && ("mark" in c || "tile_kind" in c || "tile_id" in c)).length;
      } else if (c.on === "win_kind") {
        const k = c.kind;
        if (k === "uradora") n = han.ura_dora || 0;
        else if (k === "yakuman") n = yakuman;
        else if (k === "ron") n = tsumo ? 0 : 1;
        else n = (CHIP_YAKU[k] || [k]).some(name => name in han) ? 1 : 0;
      } else continue;
      out[c.payer] += c.count * (c.per === "tile" ? n : (n ? 1 : 0));
    }
    return out;
  }
  // winChips の結果を席ごとの増減にする。reverse（逆ポッチ）なら和了者が払う側
  function chipDeltas(wc, who, frm, players, reverse) {
    const d = new Array(players).fill(0);
    for (let s = 0; s < players; s++) {
      if (s === who) continue;
      const n = wc.all + ((who === frm || s === frm) ? wc.loser : 0);
      d[s] -= n; d[who] += n;
    }
    return reverse ? d.map(x => (x === 0 ? 0 : -x)) : d;
  }
  const scoring = { basePoints, totalPoints, additivePoints, karasuKind, winChips, chipDeltas, ranks, settle };

  // ==== 局面の再現と合法手（observe.py） =========================================================
  const SUITS = "mps";
  const WINDS = ["E", "S", "W", "N"];
  const DRAGONS = ["P", "F", "C"];
  const HONORS = WINDS.concat(DRAGONS);
  const KIND_ORDER = [];
  for (const s of SUITS) for (let n = 1; n <= 9; n++) KIND_ORDER.push(n + s);
  for (const h of HONORS) KIND_ORDER.push(h);
  const KIND_INDEX = {};
  KIND_ORDER.forEach((k, i) => { KIND_INDEX[k] = i; });
  const isNumber = k => k.length === 2 && k[0] >= "0" && k[0] <= "9" && SUITS.includes(k[1]);
  const isYao = k => HONORS.includes(k) || (isNumber(k) && (k[0] === "1" || k[0] === "9"));
  const YAO = KIND_ORDER.filter(isYao);
  const kindOf = (ts, t) => ts.tiles[t].kind;
  const markOf = (ts, t) => (ts.tiles[t].mark === undefined ? null : ts.tiles[t].mark);
  const nextKind = (k, d) => { const n = Number(k[0]) + d; return n >= 1 && n <= 9 ? n + k[1] : null; };
  const kindCmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);      // Python の sorted(文字列) と同じ並び（符号位置順）
  function countKinds(kinds) { const c = {}; for (const k of kinds) c[k] = (c[k] || 0) + 1; return c; }

  function newState(M) {
    return { M, hands: range(M).map(() => []), melds: range(M).map(() => []), discards: range(M).map(() => []),
      riichi: new Array(M).fill(false), riichi_pending: null, nuki: range(M).map(() => []), dora_indicators: [],
      kans: 0, draws: 0, calls: 0, drawn: null, last_discard: null, just_called: null, first_draw_done: new Array(M).fill(false), ended: false };
  }
  function stRemove(st, who, tiles) {
    for (const t of tiles) {
      const i = st.hands[who].indexOf(t);
      if (i < 0) throw new ValidationError(`seat ${who} の手牌に牌 ${t} が無い（再生失敗）`);
      st.hands[who].splice(i, 1);
    }
  }
  function initialHands(rnd, norm, wall) {
    const M = norm.players, N = norm.hand_size, oya = rnd.state.oya;
    if (!wall) {
      const hands = rnd.events[0].hands;
      if (!hands) throw new ValidationError("wall が無く deal.hands も無いので局面を再生できない");
      return hands.map(h => h.slice());
    }
    const hands = range(M).map(() => []);
    for (let s = 0; s < M; s++) hands[(oya + s) % M] = wall.order.slice(s * N, (s + 1) * N);
    return hands;
  }
  const isSubset = (a, b) => a.every(x => b.includes(x));

  /* events[0..upto]（upto を含む）を適用した状態。 */
  function replay(rnd, norm, wall, upto) {
    const st = newState(norm.players);
    st.hands = initialHands(rnd, norm, wall);
    const evs = rnd.events;
    if (upto < 0 || upto >= evs.length) throw new ValidationError(`at=${upto} が events の範囲外`);
    for (let i = 0; i <= upto; i++) applyEvent(st, evs[i], i);
    return st;
  }
  function applyEvent(st, e, i) {
    const t = e.t;
    if (t === "deal") return;
    if (t === "dora") st.dora_indicators.push(e.tile);
    else if (t === "draw") {
      st.hands[e.who].push(e.tile);
      st.drawn = [e.who, e.tile];
      st.just_called = null;
      if (!e.rinshan) st.draws += 1;
      st.first_draw_done[e.who] = true;
    } else if (t === "discard") {
      const w = e.who;
      stRemove(st, w, [e.tile]);
      const isRiichi = Boolean(e.riichi) || st.riichi_pending === w;
      st.discards[w].push({ tile: e.tile, tsumogiri: Boolean(e.tsumogiri), riichi: isRiichi, called: false });
      if (isRiichi) st.riichi[w] = true;
      st.riichi_pending = null;
      st.last_discard = [w, e.tile];
      st.drawn = null;
      st.just_called = null;
    } else if (t === "chi" || t === "pon") {
      const w = e.who, frm = e.from;
      const called = st.last_discard ? st.last_discard[1] : null;
      let own = e.tiles.filter(x => x !== called);
      if (own.length !== e.tiles.length - 1) own = e.tiles.slice(0, -1);
      stRemove(st, w, own);
      const df = st.discards[frm];
      if (df.length) df[df.length - 1].called = true;
      const meld = { kind: t, tiles: e.tiles.slice(), from: frm, called };
      st.melds[w].push(meld);
      st.calls += 1;
      st.just_called = [w, meld];
      st.drawn = null;
    } else if (t === "kan") {
      const w = e.who, kind = e.kind;
      if (kind === "ankan") {
        stRemove(st, w, e.tiles);
        st.melds[w].push({ kind: "ankan", tiles: e.tiles.slice(), from: w });
      } else if (kind === "minkan") {
        const frm = e.from;
        const called = st.last_discard ? st.last_discard[1] : null;
        stRemove(st, w, e.tiles.filter(x => x !== called));
        const df = st.discards[frm];
        if (df.length) df[df.length - 1].called = true;
        st.melds[w].push({ kind: "minkan", tiles: e.tiles.slice(), from: frm, called });
      } else {
        const pon = st.melds[w].find(m => m.kind === "pon" && isSubset(m.tiles, e.tiles));
        if (!pon) throw new ValidationError(`seat ${w} の加槓に対応するポンが無い`);
        stRemove(st, w, e.tiles.filter(x => !pon.tiles.includes(x)));
        pon.kind = "kakan";
        pon.tiles = e.tiles.slice();
      }
      st.kans += 1;
      st.calls += 1;
      st.drawn = null;
    } else if (t === "riichi") st.riichi_pending = e.who;
    else if (t === "nuki") { stRemove(st, e.who, [e.tile]); st.nuki[e.who].push(e.tile); st.drawn = null; }
    else if (t === "win" || t === "draw_end") st.ended = true;
    else if (t === "abort") { if (!e.resume) st.ended = true; }
    else if (t === "chombo") { /* 何もしない */ }
    else throw new ValidationError(`events[${i}].t が不明: ${JSON.stringify(t)}`);
  }

  function remainingOf(norm, K, st) {
    const live = K - norm.wall_rules.dead_wall;
    const rin = norm.wall_rules.rinshan;
    let used = rin === "live" ? 0 : st.kans + sum(st.nuki.map(x => x.length));
    if (norm.wall_rules.rinshan_reserved && Array.isArray(rin)) used = Math.max(0, used - rin.length);   // 補充用に取ってある牌を使う間は、ツモれる牌は減らない
    return live - norm.hand_size * norm.players - st.draws - used;
  }

  function phaseOf(evs, at, seat) {
    const e = evs[at];
    if (e.t === "draw" && e.who === seat) return "A";
    if (e.t === "discard" && e.who !== seat) return "C";
    if ((e.t === "chi" || e.t === "pon") && e.who === seat) return "B";
    return null;
  }

  function findRound(rec, roundIndex) {
    const rnd = rec.rounds.find(r => r.index === roundIndex);
    if (!rnd) throw new ValidationError(`round ${roundIndex} が無い`);
    return rnd;
  }
  function wallOf(rnd, walls, must) {
    if (!rnd.wall) return null;
    const w = (walls || {})[rnd.wall.id];
    if (!w && must) throw new ValidationError(`round ${rnd.index} の wall ${rnd.wall.id.slice(0, 20)}… が読めない`);
    return w || null;
  }

  /* 局面のスナップショット。full でなければ seat 以外の手牌は出さない。 */
  function observe(rec, roundIndex, at, seat, rs, ts, walls, full) {
    const norm = normalize(rs);
    const M = norm.players;
    if (!(seat >= 0 && seat < M)) throw new ValidationError(`seat ${seat} が範囲外`);
    const rnd = findRound(rec, roundIndex);
    const wall = wallOf(rnd, walls, true);
    const st = replay(rnd, norm, wall, at);
    const evs = rnd.events;
    const jc = st.just_called && st.just_called[0] === seat ? st.just_called[1] : null;
    const obs = {
      seat, round: roundIndex, at, phase: phaseOf(evs, at, seat),
      state: Object.assign({}, rnd.state),
      hand: numSort(st.hands[seat]),
      melds: st.melds.map(ms => ms.map(m => { const o = {}; for (const k of Object.keys(m)) if (k !== "called") o[k] = m[k]; return o; })),
      discards: st.discards.map(ds => ds.map(d => d.tile)),
      discard_flags: st.discards.map(ds => ds.map(d => ({ tsumogiri: d.tsumogiri, riichi: d.riichi, called: d.called }))),
      riichi: st.riichi.slice(),
      nuki: st.nuki.map(x => x.slice()),
      dora_indicators: st.dora_indicators.slice(),
      remaining: remainingOf(norm, ts.tiles.length, st),
      kans: st.kans,
      drawn: st.drawn && st.drawn[0] === seat ? st.drawn[1] : null,
      last_discard: st.last_discard ? { who: st.last_discard[0], tile: st.last_discard[1] } : null,
      just_called: jc ? jc.kind : null,
      just_called_tiles: jc ? jc.tiles.slice() : null,
      just_called_tile: jc ? (jc.called === undefined ? null : jc.called) : null,
      first_turn: st.calls === 0 && !st.nuki.some(x => x.length) && st.discards[seat].length === 0,   // 抜きも鳴きと同じ扱い
      ended: st.ended,
    };
    // フリテンの判定用：同巡に他家が出した牌、立直より後に他家が出した牌（いま反応する牌は含めない）
    let passed = [];
    const passedRiichi = [];
    let inRiichi = false;
    for (let i = 0; i < at; i++) {
      const e = evs[i], t = e.t;
      if (t === "discard" && e.who === seat) {
        passed = [];
        if (e.riichi || (i > 0 && evs[i - 1].t === "riichi" && evs[i - 1].who === seat)) inRiichi = true;
      } else if (e.who !== seat && (t === "discard" || t === "nuki" || (t === "kan" && e.kind === "kakan"))) {
        let x = "tile" in e ? e.tile : null;
        if (x === null) {
          const prev = replay(rnd, norm, wall, i - 1).melds[e.who].filter(m => m.kind === "pon" && isSubset(m.tiles, e.tiles));
          const y = e.tiles.find(v => !prev.length || !prev[0].tiles.includes(v));
          x = y === undefined ? null : y;
        }
        if (x !== null) { passed.push(x); if (inRiichi) passedRiichi.push(x); }
      }
    }
    obs.passed = passed;
    obs.passed_riichi = passedRiichi;
    if (full) obs.hands = st.hands.map(numSort);
    return obs;
  }

  // ---- 和了形 ----
  function meldsFrom(c, kinds, i, need) {
    if (need === 0) return Object.values(c).every(v => v === 0);
    while (i < kinds.length && !c[kinds[i]]) i++;
    if (i >= kinds.length) return false;
    const k = kinds[i];
    if (c[k] >= 3) {
      c[k] -= 3;
      const ok = meldsFrom(c, kinds, i, need - 1);
      c[k] += 3;
      if (ok) return true;
    }
    if (isNumber(k)) {
      const k2 = nextKind(k, 1), k3 = nextKind(k, 2);
      if (k2 && k3 && c[k2] > 0 && c[k3] > 0) {
        c[k]--; c[k2]--; c[k3]--;
        const ok = meldsFrom(c, kinds, i, need - 1);
        c[k]++; c[k2]++; c[k3]++;
        if (ok) return true;
      }
    }
    return false;
  }
  const _completeCache = new Map();
  function completeKinds(kinds, meldCount, N) {
    const key = kinds.slice().sort().join(",") + "|" + meldCount + "|" + N;
    const hit = _completeCache.get(key);
    if (hit !== undefined) return hit;
    const c = countKinds(kinds);
    let ok = false;
    const need = Math.floor((N - 1) / 3) - meldCount;
    if (Object.keys(c).every(k => k in KIND_INDEX) && kinds.length === need * 3 + 2) {
      if (N === 13 && meldCount === 0) {
        const ks = Object.keys(c);
        if (ks.length === 7 && ks.every(k => c[k] === 2)) ok = true;
        else if (kinds.length === 14 && ks.length === YAO.length && YAO.every(k => c[k])) ok = true;
      }
      if (!ok) {
        const ks = KIND_ORDER.filter(k => c[k] > 0);
        for (const pair of ks) {
          if (c[pair] >= 2) {
            c[pair] -= 2;
            ok = meldsFrom(c, ks, 0, need);
            c[pair] += 2;
            if (ok) break;
          }
        }
      }
    }
    if (_completeCache.size > 500000) _completeCache.clear();
    _completeCache.set(key, ok);
    return ok;
  }
  function isComplete(ts, tiles, meldCount, N) { return completeKinds(tiles.map(t => ts.tiles[t].kind), meldCount, N); }
  const _haveCache = new WeakMap();
  function kindsIn(ts) {
    let h = _haveCache.get(ts);
    if (!h) { h = new Set(ts.tiles.map(t => t.kind)); _haveCache.set(ts, h); }
    return h;
  }
  /* 手牌（3k+1 枚）に加えると和了形になる牌の種類（Set）。 */
  // ツモった牌が「何にでも使える」印（白ポッチなど）で、その条件（立直中 など）に合い、残りの手が聴牌しているか
  function almightyTsumo(g, ts, hand, drawn, meldCount, N, riichi) {
    if (drawn === null || drawn === undefined || !hand.includes(drawn)) return false;
    const t = ts.tiles[drawn];
    const m = t.mark === undefined ? null : t.mark;
    let rules = (g.mark_overrides || []).filter(o => o.tile_id === drawn || ("tile_kind" in o && o.tile_kind === t.kind && (o.mark === undefined ? null : o.mark) === m)).slice(0, 1);
    if (!rules.length && m !== null && g.marks && m in g.marks) rules = [g.marks[m]];
    for (const r of rules) {
      const w = r.when || {};
      if ((r.effects || []).includes("almighty") && (w.how === undefined ? "any" : w.how) !== "ron" && ((w.state === undefined ? "any" : w.state) !== "riichi" || riichi)) {
        const rest = hand.slice(); rest.splice(rest.indexOf(drawn), 1);
        return waits(ts, rest, meldCount, N).size > 0;
      }
    }
    return false;
  }
  function waits(ts, hand, meldCount, N) {
    const out = new Set();
    if (hand.length % 3 !== 1) return out;
    const base = hand.map(t => ts.tiles[t].kind);
    const have = kindsIn(ts);
    for (const k of KIND_ORDER) if (have.has(k) && completeKinds(base.concat([k]), meldCount, N)) out.add(k);
    return out;
  }
  /* 聴牌として数える待ち：waits のうち、自分の手牌（副露を除く）で全部の枚数を使っている牌種を除く。空なら聴牌ではない。 */
  function tenpaiWaits(ts, hand, meldCount, N) {
    const held = {}, total = {};
    for (const t of hand) { const k = ts.tiles[t].kind; held[k] = (held[k] || 0) + 1; }
    for (const x of ts.tiles) total[x.kind] = (total[x.kind] || 0) + 1;
    return new Set([...waits(ts, hand, meldCount, N)].filter(k => (held[k] || 0) < (total[k] || 0)));
  }
  const sameSet = (a, b) => a.size === b.size && [...a].every(x => b.has(x));

  // ---- 合法手 ----
  const menzenOf = melds => melds.every(m => m.kind === "ankan");
  const isKan = m => m.kind === "ankan" || m.kind === "minkan" || m.kind === "kakan";
  function furiten(ts, obs, ws) {
    const own = new Set(obs.discards[obs.seat].map(t => kindOf(ts, t)));
    for (const t of obs.passed || []) own.add(kindOf(ts, t));
    for (const t of obs.passed_riichi || []) own.add(kindOf(ts, t));
    return [...ws].some(k => own.has(k));
  }
  // 鳴いた直後の打牌で禁止される種類（喰い替え）。call＝chi／pon、called＝鳴いた牌、meldTiles＝できた面子の 3 枚
  function kuikaeKinds(ts, mode, call, called, meldTiles) {
    const out = new Set();
    if (mode === "allowed") return out;
    const ck = kindOf(ts, called);
    out.add(ck);
    if (mode === "forbidden" && call === "chi") {
      const nums = meldTiles.map(t => Number(kindOf(ts, t)[0])).sort((a, b) => a - b);
      if (Number(ck[0]) === nums[0]) { const nk = nextKind(ck, 3); if (nk) out.add(nk); }
      else if (Number(ck[0]) === nums[2]) { const nk = nextKind(ck, -3); if (nk) out.add(nk); }
    }
    return out;
  }
  function kuikaeForbidden(ts, obs, norm) {
    if (!obs.just_called || obs.just_called_tile === null || obs.just_called_tile === undefined) return new Set();
    return kuikaeKinds(ts, norm.game_rules.flow.kuikae, obs.just_called, obs.just_called_tile, obs.just_called_tiles);
  }
  // この鳴きをしたあとに、切れる牌が手に残るか。残らない鳴き（喰い替えしかできない鳴き）はできない
  function callLeavesDiscard(ts, norm, hand, call, called, meldTiles) {
    const forbid = kuikaeKinds(ts, norm.game_rules.flow.kuikae, call, called, meldTiles);
    const rest = hand.slice();
    for (const t of meldTiles) if (t !== called) rest.splice(rest.indexOf(t), 1);
    return rest.some(t => !forbid.has(kindOf(ts, t)));
  }
  const uniqSorted = a => numSort([...new Set(a)]);
  const pyStr = v => (v === null ? "None" : String(v));           // Python の key=str と同じ並びにする

  function discardsOf(ts, obs, norm, hand, myRiichi) {
    if (myRiichi) return obs.drawn !== null && obs.drawn !== undefined ? [{ type: "discard", tile: obs.drawn }] : [];
    const forbid = kuikaeForbidden(ts, obs, norm);
    return uniqSorted(hand).filter(t => !forbid.has(kindOf(ts, t))).map(t => ({ type: "discard", tile: t }));
  }

  /* 取れる行動の一覧。obs は observe() の戻り値。phase を省くと obs.phase。 */
  function legalActions(rs, ts, obs, phase) {
    const norm = normalize(rs);
    const g = norm.game_rules, fl = g.flow;
    const M = norm.players, N = norm.hand_size;
    const seat = obs.seat;
    const hand = obs.hand.slice();
    const melds = obs.melds[seat];
    const standard = g.agari_form === "standard";
    phase = phase || obs.phase;
    const acts = [];
    if (obs.ended || !phase) return acts;
    if (phase === "B" && obs.phase === "C") return acts;
    const myRiichi = obs.riichi[seat];
    const remaining = obs.remaining;
    const scores = obs.state.scores;
    const myKans = melds.filter(isKan).length;
    const perOk = fl.max_kans_per_player === null || fl.max_kans_per_player === undefined || myKans < fl.max_kans_per_player;

    if (phase === "A") {
      const drawn = obs.drawn;
      if (standard && (isComplete(ts, hand, melds.length, N) || almightyTsumo(g, ts, hand, drawn, melds.length, N, myRiichi))) acts.push({ type: "tsumo" });
      if (standard && fl.ryukyoku.nine_terminals && obs.first_turn && !melds.length) {
        const yao = new Set(hand.map(t => kindOf(ts, t)).filter(isYao));
        if (yao.size >= 9) acts.push({ type: "draw_declare", reason: "nine_terminals" });
      }
      const nk = g.nuki;
      if (nk.enabled && remaining >= 1) for (const t of uniqSorted(hand)) if (nk.tiles.includes(kindOf(ts, t))) acts.push({ type: "nuki", tile: t });   // 海底では抜けない（カンと同じ）
      const canKan = remaining >= 1 && obs.kans < fl.max_kans && perOk;
      if (canKan) {
        if (fl.kan_kinds.includes("ankan")) {
          const seen = [];
          for (const t of hand) { const k = kindOf(ts, t); if (!seen.includes(k)) seen.push(k); }      // Python の Counter と同じ（初めて出た順）
          for (const k of seen) {
            const tiles = numSort(hand.filter(t => kindOf(ts, t) === k));
            if (tiles.length !== 4) continue;
            if (myRiichi) {
              const mode = fl.riichi.ankan_after;
              if (mode === "none") continue;
              if (drawn === null || kindOf(ts, drawn) !== k) continue;
              if (mode === "if_shape_unchanged" && standard) {
                const before = hand.filter(t => t !== drawn);
                const after = hand.filter(t => kindOf(ts, t) !== k);
                if (!sameSet(waits(ts, before, melds.length, N), waits(ts, after, melds.length + 1, N))) continue;
              }
            }
            acts.push({ type: "kan", kind: "ankan", tiles });
          }
        }
        if (fl.kan_kinds.includes("kakan")) {
          for (const m of melds) {
            if (m.kind !== "pon") continue;
            const pk = kindOf(ts, m.tiles[0]);
            for (const t of uniqSorted(hand)) {
              if (kindOf(ts, t) !== pk) continue;
              if (myRiichi && (drawn === null || t !== drawn)) continue;
              acts.push({ type: "kan", kind: "kakan", tiles: numSort(m.tiles.concat([t])) });
            }
          }
        }
      }
      const rr = fl.riichi;
      if (standard && !myRiichi && menzenOf(melds)) {
        const okPoints = scores[seat] >= rr.min_points || rr.below_min === "allowed";
        const okDraw = rr.without_draw || remaining >= M;
        const okHoutei = rr.on_houtei || remaining >= 1;
        if (okPoints && okDraw && okHoutei) {
          const seen = new Set();
          for (const t of numSort(hand)) {
            const key = kindOf(ts, t) + "|" + pyStr(markOf(ts, t));
            if (seen.has(key)) continue;
            seen.add(key);
            const rest = hand.slice();
            rest.splice(rest.indexOf(t), 1);
            const ws = waits(ts, rest, melds.length, N);
            if (!tenpaiWaits(ts, rest, melds.length, N).size) continue;
            if (!rr.furiten_riichi && furiten(ts, obs, ws)) continue;
            acts.push({ type: "riichi", tile: t });
            if (fl.open_riichi.enabled) acts.push({ type: "riichi", tile: t, open: true });
          }
        }
      }
      acts.push({ type: "pass" });
      return acts;
    }

    if (phase === "B") return discardsOf(ts, obs, norm, hand, myRiichi);

    const ld = obs.last_discard;
    if (!ld || ld.who === seat) return acts;
    const tile = ld.tile;
    const k = kindOf(ts, tile);
    if (standard && isComplete(ts, hand.concat([tile]), melds.length, N)) {
      if (!furiten(ts, obs, waits(ts, hand, melds.length, N))) acts.push({ type: "ron" });
    }
    if (remaining >= 1 && !myRiichi) {
      const same = numSort(hand.filter(t => kindOf(ts, t) === k));
      if (same.length >= 2 && fl.pon) {
        const seen = new Set();
        for (let i = 0; i < same.length; i++) for (let j = i + 1; j < same.length; j++) {
          const key = [pyStr(markOf(ts, same[i])), pyStr(markOf(ts, same[j]))].sort().join("|");
          if (seen.has(key)) continue;
          seen.add(key);
          const tiles = numSort([same[i], same[j], tile]);
          if (callLeavesDiscard(ts, norm, hand, "pon", tile, tiles)) acts.push({ type: "pon", tiles });
        }
      }
      if (same.length >= 3 && obs.kans < fl.max_kans && fl.kan_kinds.includes("minkan") && perOk) {
        acts.push({ type: "kan", kind: "minkan", tiles: numSort(same.slice(0, 3).concat([tile])) });
      }
      if (fl.chi && isNumber(k) && ld.who === mod(seat - 1, M)) {
        const byk = {};
        for (const t of hand) (byk[kindOf(ts, t)] = byk[kindOf(ts, t)] || []).push(t);
        for (const [a, b] of [[-2, -1], [-1, 1], [1, 2]]) {
          const ka = nextKind(k, a), kb = nextKind(k, b);
          if (ka && kb && byk[ka] && byk[kb]) {
            const seen = new Set();
            for (const ta of byk[ka]) for (const tb of byk[kb]) {
              const key = pyStr(markOf(ts, ta)) + "|" + pyStr(markOf(ts, tb));
              if (seen.has(key)) continue;
              seen.add(key);
              const tiles = numSort([ta, tb, tile]);
              if (callLeavesDiscard(ts, norm, hand, "chi", tile, tiles)) acts.push({ type: "chi", tiles });
            }
          }
        }
      }
    }
    acts.push({ type: "pass" });
    return acts;
  }

  /* 候補の同一性（type と牌）を文字列にしたもの。 */
  function actionKey(a) {
    const t = a.type;
    if (t === "discard" || t === "riichi" || t === "nuki") return JSON.stringify([t, a.tile === undefined ? null : a.tile, Boolean(a.open)]);
    if (t === "chi" || t === "pon") return JSON.stringify([t, numSort(a.tiles || [])]);
    if (t === "kan") return JSON.stringify([t, a.kind === undefined ? null : a.kind, numSort(a.tiles || [])]);
    if (t === "draw_declare") return JSON.stringify([t, a.reason === undefined ? null : a.reason]);
    return JSON.stringify([t]);
  }

  /* 判断点で実際に選ばれた行動を、記録の次の出来事から作る。 */
  function actualAction(rec, roundIndex, at, seat, phase) {
    const rnd = rec.rounds.find(r => r.index === roundIndex);
    if (!rnd) return null;
    const evs = rnd.events;
    let j = at + 1;
    while (j < evs.length && ((evs[j].t === "abort" && evs[j].resume) || evs[j].t === "dora")) j++;
    const nxt = j < evs.length ? evs[j] : null;
    if (phase === "A" || phase === "B") {
      if (!nxt) return null;
      if (nxt.t === "win" && nxt.who === seat && nxt.from === seat) return { type: "tsumo" };
      if (nxt.t === "kan" && nxt.who === seat) return { type: "kan", kind: nxt.kind, tiles: numSort(nxt.tiles) };
      if (nxt.t === "nuki" && nxt.who === seat) return { type: "nuki", tile: nxt.tile };
      if (nxt.t === "riichi" && nxt.who === seat) {
        const d = j + 1 < evs.length ? evs[j + 1] : null;
        if (d && d.t === "discard") { const a = { type: "riichi", tile: d.tile }; if (nxt.open) a.open = true; return a; }
        return null;
      }
      if (nxt.t === "draw_end") return { type: "draw_declare", reason: nxt.reason === undefined ? null : nxt.reason };
      if (nxt.t === "discard" && nxt.who === seat) return phase === "A" ? { type: "pass" } : { type: "discard", tile: nxt.tile };
      return null;
    }
    if (!nxt) return { type: "pass" };
    if ((nxt.t === "chi" || nxt.t === "pon") && nxt.who === seat) return { type: nxt.t, tiles: numSort(nxt.tiles) };
    if (nxt.t === "kan" && nxt.who === seat && nxt.kind === "minkan") return { type: "kan", kind: "minkan", tiles: numSort(nxt.tiles) };
    if (nxt.t === "draw_end" && nxt.reason === "three_ron") return { type: "ron" };   // 三家和の流局：他家の全員がロンと言っている
    for (let k = j; k < evs.length && evs[k].t === "win"; k++) if (evs[k].who === seat && evs[k].from !== seat) return { type: "ron" };
    return { type: "pass" };
  }

  /* カン・抜きで見せた牌 tile を、obs の席がロンできるか（槍槓。形とフリテンだけ。役の有無は見ない）。
     kind は "kakan"／"ankan"／"nuki"。暗槓の牌は、ルールが認めていて（flow.kokushi_ankan_chankan）国士無双の形のときだけ。 */
  function canRob(norm, ts, obs, kind, tile) {
    const g = norm.game_rules;
    if (g.agari_form !== "standard" || !["kakan", "ankan", "nuki"].includes(kind)) return false;
    const N = norm.hand_size, hand = obs.hand.slice(), melds = obs.melds[obs.seat];
    if (kind === "ankan") {
      if (!g.flow.kokushi_ankan_chankan || melds.length || N !== 13 || hand.length !== 13) return false;
      const ks = new Set(hand.concat([tile]).map(t => ts.tiles[t].kind));
      if (ks.size !== YAO.length || !YAO.every(k => ks.has(k))) return false;
    }
    if (!isComplete(ts, hand.concat([tile]), melds.length, N)) return false;
    return !furiten(ts, obs, waits(ts, hand, melds.length, N));
  }
  const observeMod = { replay, observe, legalActions, actualAction, actionKey, isComplete, waits, tenpaiWaits, furiten, canRob, remainingOf, phaseOf, kindOf };

  // ==== 和了の役と符の判定（judge.py） ===========================================================
  const DRAGON_YAKU = { P: "yakuhai_haku", F: "yakuhai_hatsu", C: "yakuhai_chun" };
  const GREEN = ["2s", "3s", "4s", "6s", "8s", "F"];
  const isTerm = k => isNumber(k) && (k[0] === "1" || k[0] === "9");
  const YAKU_NAMES = Object.keys(VOCAB.yaku);
  const YAKUMAN_NAMES = Object.keys(VOCAB.yakuman);
  const yakuOrder = n => (YAKU_NAMES.includes(n) ? YAKU_NAMES.indexOf(n) : 100 + YAKUMAN_NAMES.indexOf(n));

  /* 採用している役 → 翻の指定。値：{closed, open} か {yakuman: k}。不採用の役は入らない。 */
  function yakuTable(norm) {
    const y = norm.game_rules.yaku;
    const base = YAKU_TABLES[y.base] || { yaku: {}, yakuman: {} };
    const raw = {};
    for (const [k, v] of Object.entries(base.yaku)) raw[k] = v;
    for (const [k, v] of Object.entries(base.yakuman)) raw[k] = v === 1 ? "yakuman" : "yakuman:" + v;
    for (const [k, v] of Object.entries(y.overrides || {})) raw[k] = v;
    const out = {};
    for (const [k, v] of Object.entries(raw)) {
      if (v === false || v === null || v === undefined || v === true) continue;
      if (typeof v === "number") out[k] = { closed: v, open: v };
      else if (isObj(v)) out[k] = { closed: v.closed === undefined ? null : v.closed, open: v.open === undefined ? null : v.open };
      else if (typeof v === "string" && v.startsWith("yakuman")) out[k] = { yakuman: v.includes(":") ? Number(v.split(":")[1]) : 1 };
    }
    return out;
  }

  /* 表示牌の次の牌種。牌表にある牌種の中で回る。 */
  function doraNext(ts, kind) {
    const have = kindsIn(ts);
    let ring;
    if (isNumber(kind)) ring = range(9).map(i => (i + 1) + kind[1]).filter(k => have.has(k));
    else if (WINDS.includes(kind)) ring = WINDS.filter(k => have.has(k));
    else if (DRAGONS.includes(kind)) ring = DRAGONS.filter(k => have.has(k));
    else return null;
    return ring.includes(kind) ? ring[(ring.indexOf(kind) + 1) % ring.length] : null;
  }

  function markRules(norm, ts, tid) {
    const g = norm.game_rules;
    const m = markOf(ts, tid);
    for (const o of g.mark_overrides || []) {
      if (o.tile_id === tid || ("tile_kind" in o && o.tile_kind === ts.tiles[tid].kind && (o.mark === undefined ? null : o.mark) === m)) return [o];
    }
    return m !== null && g.marks && m in g.marks ? [g.marks[m]] : [];
  }
  // 条件に how（tsumo／ron）がある印の効果は、和了牌にだけ働く。how が無い（any）印は、手の内のどの牌にも働く
  function onWinTile(rule, tid, ctx) {
    const how = (rule.when || {}).how;
    return how === undefined || how === "any" || tid === ctx.tile;
  }
  function whenOk(rule, ctx, menzen) {
    const w = rule.when;
    if (!w || !Object.keys(w).length) return true;
    if ((w.state || "any") === "riichi" && !(ctx.riichi || ctx.double_riichi)) return false;
    const how = w.how || "any";
    if (how === "tsumo" && !ctx.tsumo) return false;
    if (how === "ron" && ctx.tsumo) return false;
    if (w.ippatsu_only && !ctx.ippatsu) return false;
    if (w.rinshan_ok === false && ctx.rinshan) return false;
    if (w.haitei_ok === false && (ctx.haitei || ctx.houtei)) return false;
    if (w.menzen_only && !menzen) return false;
    return true;
  }

  function splitSets(c, kinds, i, need, acc, out) {
    if (need === 0) { if (kinds.every(k => !c[k])) out.push(acc.slice()); return; }
    while (i < kinds.length && !c[kinds[i]]) i++;
    if (i >= kinds.length) return;
    const k = kinds[i];
    if (c[k] >= 3) {
      c[k] -= 3; acc.push(["pon", k]);
      splitSets(c, kinds, i, need - 1, acc, out);
      acc.pop(); c[k] += 3;
    }
    if (isNumber(k) && Number(k[0]) <= 7) {
      const k2 = (Number(k[0]) + 1) + k[1], k3 = (Number(k[0]) + 2) + k[1];
      if (c[k2] > 0 && c[k3] > 0) {
        c[k]--; c[k2]--; c[k3]--; acc.push(["chi", k]);
        splitSets(c, kinds, i, need - 1, acc, out);
        acc.pop(); c[k]++; c[k2]++; c[k3]++;
      }
    }
  }
  /* 牌種の列を「need 面子＋雀頭」に切る全部の方法。[[雀頭, [[pon|chi, 牌種]…]]…] */
  function decompositions(kinds, need) {
    const c = countKinds(kinds);
    if (Object.keys(c).some(k => !(k in KIND_INDEX)) || kinds.length !== need * 3 + 2) return [];
    const ks = KIND_ORDER.filter(k => c[k] > 0);
    const out = [];
    for (const p of ks) {
      if (c[p] >= 2) {
        c[p] -= 2;
        const got = [];
        splitSets(c, ks, 0, need, [], got);
        c[p] += 2;
        for (const g of got) out.push([p, g]);
      }
    }
    return out;
  }
  const chiKinds = k => [0, 1, 2].map(d => (Number(k[0]) + d) + k[1]);

  function shapesOf(kinds, melds, N, g) {
    const out = [];
    const need = Math.floor((N - 1) / 3) - melds.length;
    if (need >= 0) for (const [p, sets] of decompositions(kinds, need)) out.push(["standard", p, sets]);
    if (N === 13 && !melds.length && kinds.length === 14) {
      const c = countKinds(kinds);
      const ks = Object.keys(c);
      if (ks.every(k => c[k] === 2 || c[k] === 4) && (ks.length === 7 || g.yaku.chiitoi_four_of_kind)) out.push(["chiitoi"]);
      if (ks.length === YAO.length && YAO.every(k => c[k])) out.push(["kokushi"]);
    }
    return out;
  }

  function situational(g, ctx, menzen) {
    const out = [];
    if (ctx.double_riichi) out.push("double_riichi", "riichi");
    else if (ctx.riichi) out.push("riichi");
    if (ctx.open_riichi) out.push("open_riichi");
    if (ctx.ippatsu && g.flow.ippatsu !== false) out.push("ippatsu");
    if (ctx.tsumo && menzen) out.push("menzen_tsumo");
    for (const k of ["haitei", "houtei", "rinshan", "chankan", "tenhou", "chiihou", "renhou"]) if (ctx[k]) out.push(k);
    return out;
  }
  function wholeHand(g, allKinds, menzen) {
    const out = [];
    if (allKinds.every(k => !isYao(k)) && (menzen || g.flow.open_tanyao !== false)) out.push("tanyao");
    const suits = new Set(allKinds.filter(isNumber).map(k => k[1]));
    const honors = allKinds.some(k => HONORS.includes(k));
    if (suits.size === 1 && honors) { out.push("honitsu"); if (suits.has("m")) out.push("manzu_honitsu"); }
    if (suits.size === 1 && !honors) out.push("chinitsu");
    if (!suits.size) out.push("tsuuiisou");
    if (allKinds.every(isTerm)) out.push("chinroutou");
    if (allKinds.every(isYao)) out.push("honroutou");
    if (allKinds.every(k => GREEN.includes(k)) && (!g.flow.ryuuiisou_requires_hatsu || allKinds.includes("F"))) out.push("ryuuiisou");
    return out;
  }

  function candidates(norm, ctx, kinds, winKind, melds, ts, menzen, N) {
    const g = norm.game_rules;
    const fuRule = g.scoring.fu;
    const seat = ctx.seat_wind, rnd = ctx.round_wind;
    const tsumo = ctx.tsumo;
    const kind = t => ts.tiles[t].kind;
    let allKinds = kinds.slice();
    for (const m of melds) allKinds = allKinds.concat(m.tiles.map(kind));
    const nk = g.nuki || {};
    const nukiKinds = nk.enabled ? (nk.tiles || []) : [];
    const pairYakuhai = p => {
      let n = 0;
      if (DRAGONS.includes(p)) n++;
      if (p === seat) n++;
      if (p === rnd) n++;
      if (nukiKinds.includes(p) && nk.as_yakuhai === "common" && p !== seat && p !== rnd) n++;
      return n;
    };
    const situ = situational(g, ctx, menzen);
    const whole = wholeHand(g, allKinds, menzen);
    const out = [];
    for (const shape of shapesOf(kinds, melds, N, g)) {
      if (shape[0] === "kokushi") {
        const c = countKinds(kinds);
        const names = new Set(situ);
        names.add(c[winKind] === 2 ? "kokushi13" : "kokushi");
        if (c[winKind] === 2) names.add("kokushi");
        out.push({ names, fu: tsumo ? 30 : 40, form: "kokushi", wait: "kokushi" });
        continue;
      }
      if (shape[0] === "chiitoi") {
        const names = new Set(situ.concat(whole, ["chiitoitsu"]));
        if (kinds.every(k => HONORS.includes(k))) names.add("tsuuiisou_chiitoi");
        const uniq = [...new Set(kinds)].sort(kindCmp);
        // 大車輪：一色の 2〜8 の七対子（既定）。yaku.wheel＝any_suit なら清一色の七対子ならどの並びでも（関西の三人打ち）
        for (const s of SUITS) if (eq(uniq, [2, 3, 4, 5, 6, 7, 8].map(n => n + s))) names.add("daisharin");
        if (g.yaku.wheel === "any_suit" && whole.includes("chinitsu")) names.add("daisharin");
        if (whole.includes("honitsu")) names.add("shousharin");            // 小車輪：混一色の七対子（どの色でも）
        out.push({ names, fu: 25, form: "chiitoi", wait: "tanki" });
        continue;
      }
      const pair = shape[1], csets = shape[2];
      const waitsList = [];
      if (pair === winKind) waitsList.push(["tanki", null]);
      csets.forEach(([t, k], j) => {
        if (csets.slice(0, j).some(([t2, k2]) => t2 === t && k2 === k)) return;
        if (t === "pon" && k === winKind) waitsList.push(["shanpon", j]);
        if (t === "chi" && chiKinds(k).includes(winKind)) {
          const pos = chiKinds(k).indexOf(winKind), n0 = Number(k[0]);
          if (pos === 1) waitsList.push(["kanchan", j]);
          else if ((pos === 2 && n0 === 1) || (pos === 0 && n0 === 7)) waitsList.push(["penchan", j]);
          else waitsList.push(["ryanmen", j]);
        }
      });
      for (const [wait, wj] of waitsList) {
        const sets = csets.map(([t, k], j) => ({ t, k, open: t === "pon" && wait === "shanpon" && wj === j && !tsumo }));
        for (const m of melds) {
          const ks = m.tiles.map(kind).sort((a, b) => KIND_INDEX[a] - KIND_INDEX[b]);
          if (m.kind === "chi") sets.push({ t: "chi", k: ks[0], open: true });
          else if (m.kind === "pon") sets.push({ t: "pon", k: ks[0], open: true });
          else sets.push({ t: "kan", k: ks[0], open: m.kind !== "ankan" });
        }
        const names = new Set(situ.concat(whole));
        const chis = sets.filter(s => s.t === "chi");
        const trips = sets.filter(s => s.t !== "chi");
        const pyk = pairYakuhai(pair);
        const pinfuShape = chis.length === sets.length && sets.length >= 1 && pyk === 0 && wait === "ryanmen";
        const pinfu = pinfuShape && menzen && (!tsumo || fuRule.menzen_tsumo_pinfu);
        if (pinfu) names.add("pinfu");
        for (const s of trips) {
          if (DRAGONS.includes(s.k)) names.add(DRAGON_YAKU[s.k]);
          if (s.k === seat) names.add("yakuhai_seat");
          if (s.k === rnd) names.add("yakuhai_round");
        }
        const tw = trips.filter(s => WINDS.includes(s.k)), td = trips.filter(s => DRAGONS.includes(s.k));
        if (td.length === 3) names.add("daisangen");
        if (td.length === 2 && DRAGONS.includes(pair)) names.add("shousangen");
        if (tw.length === 4) names.add("daisuushii");
        if (tw.length === 3 && WINDS.includes(pair)) names.add("shousuushii");
        if (tw.length === 3) names.add("sanpuu");
        const ck = countKinds(chis.map(s => s.k));
        const dup = sum(Object.values(ck).map(v => Math.floor(v / 2)));
        if (dup >= 2) names.add("ryanpeikou");
        if (dup >= 1) names.add("iipeikou");
        for (const n of "1234567") if ([...SUITS].every(s => ck[n + s])) names.add("sanshoku");
        for (const s of SUITS) if (["1", "4", "7"].every(n => ck[n + s])) names.add("ittsu");
        const tk = countKinds(trips.map(s => s.k));
        for (const n of "123456789") if ([...SUITS].every(s => tk[n + s])) names.add("sanshoku_doukou");
        for (const s of SUITS) {
          let run = 0;
          for (let n = 1; n <= 9; n++) {
            run = tk[n + s] ? run + 1 : 0;
            if (run >= 3) names.add("sanrenkou");
            if (run >= 4) names.add("suurenkou");
          }
        }
        if (sets.length && !chis.length) names.add("toitoi");
        const closedTrips = trips.filter(s => !s.open);
        if (closedTrips.length === 3) names.add("sanankou");
        if (closedTrips.length === 4) { names.add("suuankou"); if (wait === "tanki") names.add("suuankou_tanki"); }
        const kans = sets.filter(s => s.t === "kan");
        if (kans.length === 3) names.add("sankantsu");
        if (kans.length === 4) names.add("suukantsu");
        if (chis.length) {
          const each = trips.every(s => isYao(s.k)) && chis.every(s => s.k[0] === "1" || s.k[0] === "7") && isYao(pair);
          if (each) names.add(allKinds.some(k => HONORS.includes(k)) ? "chanta" : "junchan");
        }
        if (menzen && !melds.length && kinds.length === 14 && kinds.every(isNumber) && new Set(kinds.map(k => k[1])).size === 1) {
          const c = {};
          for (let n = 1; n <= 9; n++) c[n] = 0;
          for (const k of kinds) c[Number(k[0])]++;
          if (c[1] >= 3 && c[9] >= 3 && [2, 3, 4, 5, 6, 7, 8].every(n => c[n] >= 1)) {
            if (g.flow.chuuren_any_suit !== false || kinds[0][1] === "m") {
              names.add("chuuren");
              c[Number(winKind[0])]--;
              if (c[1] === 3 && c[9] === 3 && [2, 3, 4, 5, 6, 7, 8].every(n => c[n] === 1)) names.add("junsei_chuuren");
            }
          }
        }
        let fu = 20;
        for (const s of sets) {
          if (s.t === "chi") continue;
          let v = s.open ? 2 : 4;
          if (isYao(s.k)) v *= 2;
          if (s.t === "kan") v *= 4;
          fu += v;
        }
        if ((pair === seat || pair === rnd) && seat === rnd && WINDS.includes(pair)) fu += fuRule.double_wind_pair;
        else fu += 2 * pyk;
        if (wait === "tanki" || wait === "kanchan" || wait === "penchan") fu += 2;
        if (wait === "tanki" && pyk) fu += fuRule.yakuhai_tanki_fu || 0;
        if (tsumo) { if (!pinfu && !(ctx.rinshan && fuRule.rinshan_tsumo_fu === 0)) fu += 2; }
        else if (menzen) fu += 10;
        if (!menzen && fu === 20) fu = fuRule.open_pinfu_fu;
        fu = Math.floor((fu + 9) / 10) * 10;
        out.push({ names, fu, form: "standard", wait });
      }
    }
    return out;
  }

  const SUPERSEDE = [["double_riichi", "riichi"], ["ryanpeikou", "iipeikou"], ["chinitsu", "honitsu"], ["junchan", "chanta"],
    ["kokushi13", "kokushi"], ["junsei_chuuren", "chuuren"], ["suuankou_tanki", "suuankou"], ["suurenkou", "sanrenkou"],
    ["tsuuiisou", "honroutou"], ["chinroutou", "honroutou"], ["tsuuiisou", "honitsu"], ["chinroutou", "junchan"],
    ["manzu_honitsu", "honitsu"], ["daisharin", "chiitoitsu"], ["tsuuiisou_chiitoi", "tsuuiisou"],
    ["shousharin", "chiitoitsu"], ["shousharin", "honitsu"],
    ["daisuushii", "shousuushii"], ["honroutou", "chanta"], ["ryanpeikou", "chiitoitsu"]];

  function finishCandidate(norm, ts, table, ctx, cand, hand, melds, menzen) {
    const g = norm.game_rules, sc = g.scoring;
    const kind = t => ts.tiles[t].kind;
    const got = {};
    for (const n of cand.names) {
      const spec = table[n];
      if (!spec) continue;
      if ("yakuman" in spec) { got[n] = ["yakuman", spec.yakuman]; continue; }
      const v = menzen ? spec.closed : spec.open;
      if (v) got[n] = ["han", v];
    }
    if ("open_riichi" in got && (g.flow.open_riichi || {}).enabled) {
      const orr = g.flow.open_riichi;
      const tot = "double_riichi" in got ? (orr.with_double_riichi_han === undefined ? 3 : orr.with_double_riichi_han) : (orr.han_total === undefined ? 2 : orr.han_total);
      delete got.riichi; delete got.double_riichi;
      got.open_riichi = ["han", tot];
    }
    for (const [hi, lo] of SUPERSEDE) if (hi in got) delete got[lo];
    let fu = cand.fu;
    if (cand.form === "chiitoi" && "chiitoitsu" in got && sc.fu.chiitoi === "50fu_1han") { fu = 50; got.chiitoitsu = ["han", 1]; }
    if (cand.form === "chiitoi" && !("chiitoitsu" in got) && !("daisharin" in got) && !("shousharin" in got) && !("tsuuiisou_chiitoi" in got) && !("tsuuiisou" in got)) return null;
    if (cand.form === "kokushi" && !("kokushi" in got) && !("kokushi13" in got)) return null;
    if (ctx.open_riichi_deal_in && !Object.keys(got).some(n => got[n][0] === "yakuman")) got.open_riichi_deal_in = ["yakuman", 1];   // 役満でない手でも、役満の点を払う
    const ymNames = Object.keys(got).filter(n => got[n][0] === "yakuman").sort((a, b) => yakuOrder(a) - yakuOrder(b));
    const ymSum = sum(ymNames.map(n => got[n][1]));
    if (ymNames.length && !sc.limits.stack_with_normal) {
      return { ok: true, yaku: ymNames.map(n => ({ name: n, yakuman: got[n][1] })), fu, han: 0, yakuman: ymSum, wait: cand.wait, form: cand.form };
    }
    const yaku = Object.keys(got).filter(n => got[n][0] === "han").sort((a, b) => yakuOrder(a) - yakuOrder(b)).map(n => ({ name: n, han: got[n][1] }));
    let yakuHan = sum(yaku.map(y => y.han));
    const allTiles = hand.concat(...melds.map(m => m.tiles));
    let markDora = 0, markYaku = 0, reverse = false;
    for (const t of allTiles) {
      for (const r of markRules(norm, ts, t)) {
        if (!whenOk(r, ctx, menzen)) continue;
        const eff = r.effects || [];
        const val = r.value === undefined ? 1 : r.value;
        if (eff.includes("dora")) markDora += val;
        if (eff.includes("yaku")) markYaku += val;
        if (eff.includes("reverse") && onWinTile(r, t, ctx)) reverse = true;
      }
    }
    yakuHan += markYaku;
    const sh = sc.shibari;
    const need = sh.from_honba !== null && sh.from_honba !== undefined && (ctx.honba || 0) >= sh.from_honba ? sh.han : 1;
    if (!ymNames.length && yakuHan < need) return null;
    const d = g.dora, vals = d.values || {};
    const nuki = (ctx.nuki || []).slice();
    const countTiles = allTiles.concat(nuki).map(kind);
    const count = (inds, firstKey, kanKey, ura) => {
      let n = 0;
      (inds || []).forEach((ind, i) => {
        const v0 = vals[i === 0 ? firstKey : kanKey];
        const v = v0 === undefined ? 1 : v0;
        if (ura && markRules(norm, ts, ind).some(r => r.as_ura_indicator === "choose_any")) {
          // 裏ドラ表示牌がこの印の牌（白ポッチ）：好きな牌を裏ドラにできる＝手の中でいちばん多い牌種の枚数
          const c = {}; for (const k of countTiles) c[k] = (c[k] || 0) + 1;
          n += Math.max(...Object.values(c)) * v;
          return;
        }
        const nk2 = doraNext(ts, kind(ind));
        n += countTiles.filter(k => k === nk2).length * v;
      });
      return n;
    };
    const extra = [];
    if (d.indicator) { const n = count(ctx.dora_indicators, "indicator", "kan"); if (n) extra.push({ name: "dora", han: n }); }
    if (d.ura && (ctx.riichi || ctx.double_riichi || ctx.open_riichi)) { const n = count(ctx.ura_indicators, "ura", "kan_ura", true); if (n) extra.push({ name: "ura_dora", han: n }); }
    if (markDora) extra.push({ name: "aka_dora", han: markDora });
    const nkr = g.nuki || {};
    if (nkr.enabled && nuki.length) extra.push({ name: "nuki_dora", han: nuki.length * (nkr.value === undefined ? 1 : nkr.value) });
    if (markYaku) yaku.push({ name: "mark_yaku", han: markYaku });
    const outYaku = ymNames.map(n => ({ name: n, yakuman: got[n][1] })).concat(yaku, extra);
    const res = { ok: true, yaku: outYaku, fu, han: sum(outYaku.map(y => y.han || 0)), wait: cand.wait, form: cand.form };
    if (!sc.fu.enabled) res.fu = 20;
    if (ymNames.length) res.yakuman = ymSum;
    if (reverse) res.reverse = true;
    return res;
  }

  /* 和了 1 つの役・符・翻。ctx は winContext／contextAt が作る形。 */
  function judge(rs, ts, ctx) {
    const norm = normalize(rs);
    const g = norm.game_rules, sc = g.scoring, N = norm.hand_size;
    const table = yakuTable(norm);
    const kind = t => ts.tiles[t].kind;
    const melds = ctx.melds || [];
    const hand = ctx.hand.slice();
    const menzen = melds.every(m => m.kind === "ankan");
    const wild = hand.filter(t => markRules(norm, ts, t).some(r => (r.effects || []).includes("almighty") && whenOk(r, ctx, menzen) && onWinTile(r, t, ctx)));
    if (wild.length > 2) throw new ValidationError("オールマイティの牌が手の内に 3 枚以上ある和了は判定していない");
    const have = KIND_ORDER.filter(k => kindsIn(ts).has(k));
    let assigns = [{}];
    for (const t of wild) { const nxt = []; for (const a of assigns) for (const k of have) nxt.push(Object.assign({}, a, { [t]: k })); assigns = nxt; }
    // 抜く牌を手の内・副露に残したままの和了を認めないルール（nuki.win_with_nuki_in_hand＝false）：その牌が無いと和了できない役満だけは認める
    const nk = g.nuki || {};
    const NUKI_KEPT_OK = ["kokushi", "kokushi13", "chinroutou", "tsuuiisou", "tsuuiisou_chiitoi", "shousuushii", "daisuushii"];
    const kept = !!nk.enabled && nk.win_with_nuki_in_hand === false &&
      hand.concat(...melds.map(m => m.tiles)).some(t => (nk.tiles || []).includes(kind(t)));
    let blocked = false;
    let best = null, bestKey = null, anyShape = false;
    const keyGt = (a, b) => { for (let i = 0; i < a.length; i++) { if (a[i] !== b[i]) return a[i] > b[i]; } return false; };
    for (const a of assigns) {
      const kinds = hand.map(t => (t in a ? a[t] : kind(t)));
      const winKind = ctx.tile in a ? a[ctx.tile] : kind(ctx.tile);
      const cands = candidates(norm, ctx, kinds, winKind, melds, ts, menzen, N);
      if (cands.length) anyShape = true;
      for (const c0 of cands) {
        const c = finishCandidate(norm, ts, table, ctx, c0, hand, melds, menzen);
        if (!c) continue;
        if (kept && !c.yaku.some(y => NUKI_KEPT_OK.includes(y.name))) { blocked = true; continue; }
        const key = [basePoints(c.fu, c.han, c.yakuman || 0, sc), c.yakuman || 0, c.han, c.fu];
        if (best === null || keyGt(key, bestKey)) { best = c; bestKey = key; }
      }
    }
    if (best === null && blocked) return { ok: false, reason: "抜く牌を手に残したままでは和了できない" };
    if (best === null) return { ok: false, reason: anyShape ? "役が無い" : "和了形ではない" };
    if (g.flow.atozuke === "kanzen_sakizuke" && !ctx._no_sakizuke_check && !best.yakuman) {
      const bad = yakulessWaits(rs, ts, ctx, hand, melds, N);
      if (bad.length) return { ok: false, reason: "完全先付け：役の無い待ち（" + bad.join("・") + "）がある" };
    }
    return best;
  }
  // 完全先付け（片和了なし）：この聴牌の待ちのうち、役が付かない牌種。1 つでもあれば、どの牌でも和了できない。
  // 役は、その牌で同じ和了り方（ロン／ツモ）をしたものとして数え、偶然の役（一発・海底・河底・嶺上・槍槓）とドラは数えない
  function yakulessWaits(rs, ts, ctx, hand, melds, N) {
    const rest = hand.slice(); rest.splice(rest.indexOf(ctx.tile), 1);
    const byKind = {};
    ts.tiles.forEach((t, i) => { (byKind[t.kind] = byKind[t.kind] || []).push(i); });
    const used = new Set(rest.concat(...melds.map(m => m.tiles)));
    const bad = [];
    const ws = [...waits(ts, rest, melds.length, N)].sort((a, b) => KIND_ORDER.indexOf(a) - KIND_ORDER.indexOf(b));
    for (const k of ws) {
      const cands = byKind[k] || [];
      let tid = cands.find(t => !used.has(t) && (ts.tiles[t].mark === undefined || ts.tiles[t].mark === null));
      if (tid === undefined) tid = cands.find(t => !used.has(t));
      if (tid === undefined) tid = cands[0];
      const c2 = Object.assign({}, ctx, { hand: rest.concat([tid]), tile: tid, _no_sakizuke_check: true, dora_indicators: [], ura_indicators: [], nuki: [],
        ippatsu: false, haitei: false, houtei: false, rinshan: false, chankan: false });
      if (!judge(rs, ts, c2).ok) bad.push(k);
    }
    return bad;
  }

  function indicatorsFromWall(wall, norm, n, kindFirst, kindKan) {
    const wr = norm.wall_rules;
    const order = wall.order;
    const liveEnd = order.length - wr.dead_wall;
    const offs = (wr[kindFirst] || []).concat(wr[kindKan] || []);
    return offs.slice(0, Math.max(n, 0)).map(o => order[liveEnd + o]);
  }
  function uraIndicators(wall, norm, nDora) {
    const g = norm.game_rules;
    const nKan = g.dora.kan_ura ? Math.max(0, nDora - 1) : 0;
    return indicatorsFromWall(wall, norm, 1, "ura_indicator", "kan_ura").slice(0, 1).concat(indicatorsFromWall(wall, norm, nKan, "kan_ura", "kan_ura"));
  }

  /* events[0..upto] まで進んだ局面で、who が frm の牌 tile で和了るときの状況（frm＝who ならツモ）。 */
  function contextAt(rec, roundIndex, upto, who, frm, tile, rs, ts, walls, ura) {
    const norm = normalize(rs);
    const g = norm.game_rules, M = norm.players;
    const rnd = findRound(rec, roundIndex);
    const evs = rnd.events;
    const wall = wallOf(rnd, walls, false);
    const st = replay(rnd, norm, wall, upto);
    const tsumo = who === frm;
    const oya = rnd.state.oya;
    const hand = st.hands[who].concat(tsumo ? [] : [tile]);
    const before = evs.slice(0, upto + 1).filter(x => x.t !== "dora" && x.t !== "abort");
    const last = before.length ? before[before.length - 1] : {};
    const robbed = !tsumo && (last.t === "kan" || last.t === "nuki");
    const chankan = robbed && (last.t === "kan" || Boolean((g.nuki || {}).chan_nuki));
    const remaining = remainingOf(norm, ts.tiles.length, st);
    let lastDraw = null;
    for (let i = before.length - 1; i >= 0; i--) if (before[i].t === "draw" && before[i].who === who) { lastDraw = before[i]; break; }
    const rinshan = tsumo && Boolean(lastDraw && lastDraw.rinshan);
    const isCall = x => x.t === "chi" || x.t === "pon" || x.t === "kan" || x.t === "nuki";
    let riichi = false, dbl = false, ippatsu = false, openR = false;
    const ri = before.findIndex(x => x.t === "riichi" && x.who === who);
    if (ri >= 0 && st.riichi[who]) {
      riichi = true;
      openR = Boolean(before[ri].open);
      const prior = before.slice(0, ri);
      dbl = !prior.some(isCall) && !prior.some(x => x.t === "discard" && x.who === who);
      let after = before.slice(ri + 2);
      if (robbed && after.length) after = after.slice(0, -1);
      ippatsu = !after.some(isCall) && !after.some(x => x.t === "discard" && x.who === who);
    }
    // オープン立直への放銃の役満払い（先に立直していた人は exempt_prior_riichi で外れ、追っかけは chaser_pays＝false なら外れる）
    let dealIn = false;
    const orr = g.flow.open_riichi || {};
    if (openR && !tsumo && orr.enabled && orr.deal_in === "yakuman") {
      const fi = before.findIndex(x => x.t === "riichi" && x.who === frm);
      if (fi < 0) dealIn = true;
      else if (fi < ri) dealIn = orr.exempt_prior_riichi === false;
      else dealIn = orr.chaser_pays !== false;
    }
    const calls = before.some(isCall);
    const ownDiscards = before.some(x => x.t === "discard" && x.who === who);
    const anyDiscards = before.some(x => x.t === "discard");
    const ownDraws = before.filter(x => x.t === "draw" && x.who === who).length;
    const ctx = {
      who, from: frm, tile, tsumo, hand,
      melds: st.melds[who].map(m => ({ kind: m.kind, tiles: m.tiles.slice() })),
      seat_wind: norm.winds[mod(who - oya, M)], round_wind: rnd.state.bakaze === undefined ? null : rnd.state.bakaze,
      riichi, double_riichi: riichi && dbl, ippatsu, open_riichi: openR, open_riichi_deal_in: dealIn,
      rinshan, chankan,
      haitei: tsumo && !rinshan && remaining === 0,
      houtei: !tsumo && !robbed && remaining === 0,
      tenhou: tsumo && who === oya && !calls && !anyDiscards,
      chiihou: tsumo && who !== oya && !calls && !ownDiscards && ownDraws === 1,
      renhou: !tsumo && !calls && !ownDiscards && ownDraws === 0,
      nuki: st.nuki[who].slice(), honba: rnd.state.honba || 0,
    };
    const inds = st.dora_indicators.slice();
    ctx.dora_indicators = inds;
    if (ura !== undefined && ura !== null) ctx.ura_indicators = ura.slice();
    else if (wall && riichi && g.dora.ura) ctx.ura_indicators = uraIndicators(wall, norm, inds.length);
    else ctx.ura_indicators = [];
    return ctx;
  }

  /* round_index 局の events[at]（t＝win）の和了の状況。 */
  function winContext(rec, roundIndex, at, rs, ts, walls) {
    const rnd = findRound(rec, roundIndex);
    const evs = rnd.events;
    const e = evs[at];
    if (!e || e.t !== "win") throw new ValidationError(`events[${at}] は和了ではない`);
    let first = at;
    while (first > 0 && evs[first - 1].t === "win") first--;
    const resWin = ((rnd.result || {}).wins || []).find(w => w.who === e.who);
    return contextAt(rec, roundIndex, first - 1, e.who, e.from, e.tile, rs, ts, walls, resWin && "ura_indicators" in resWin ? resWin.ura_indicators : null);
  }
  function judgeWin(rec, roundIndex, at, rs, ts, walls) { return judge(rs, ts, winContext(rec, roundIndex, at, rs, ts, walls)); }

  function yakuCounter(ys, mergeDora) {
    const c = {};
    for (const y of ys || []) {
      const n = mergeDora && (y.name === "kan_dora" || y.name === "nuki_dora") ? "dora" : y.name;
      if ("yakuman" in y) c[n + "|yakuman"] = (c[n + "|yakuman"] || 0) + y.yakuman;
      else if (y.han) c[n + "|han"] = (c[n + "|han"] || 0) + y.han;
    }
    return Object.keys(c).sort().map(k => [k, c[k]]);
  }
  /* 判定の結果と記録の和了を比べる。同じなら null、違えば文。 */
  function sameAsRecorded(res, win, mergeDora) {
    if (!res.ok) return `判定：${res.reason}`;
    const a = yakuCounter(res.yaku, mergeDora), b = yakuCounter(win.yaku, mergeDora);
    if (!eq(a, b)) return `役が違う：判定 ${JSON.stringify(a)} 記録 ${JSON.stringify(b)}`;
    if ((res.yakuman || 0) !== (win.yakuman || 0)) return `役満の倍数が違う：判定 ${res.yakuman || 0} 記録 ${win.yakuman || 0}`;
    if (!res.yakuman) {
      if (res.han !== win.han) return `翻が違う：判定 ${res.han} 記録 ${win.han}`;
      if (!("additive" in win) && res.fu !== win.fu) return `符が違う：判定 ${res.fu} 記録 ${win.fu}`;   // 足し算の点数の和了は符を使わず、記録の fu は 0
    }
    return null;
  }

  const judgeMod = { judge, judgeWin, winContext, contextAt, yakuTable, doraNext, decompositions, uraIndicators, sameAsRecorded };

  // ==== 対局の検証（record.py：record.md §4 ＋ X4〜X8） ==========================================
  const REC_FORMAT = "nmahjong-record", REC_VERSION = "1.0";
  const EVENT_TYPES = ["deal", "dora", "draw", "discard", "chi", "pon", "kan", "riichi", "nuki", "win", "draw_end", "abort", "chombo"];
  const TOP_KEYS = ["format", "version", "id", "source", "ruleset", "venue", "device", "event", "players", "started_at", "ended_at", "end", "parent", "rounds", "final", "meta"];
  const DORA_LIKE = ["dora", "ura_dora", "aka_dora", "kan_dora", "nuki_dora", "mark_yaku"];
  const isInt = x => Number.isInteger(x);
  const inVocab = (v, name) => (Array.isArray(VOCAB[name]) ? VOCAB[name].includes(v) : v in VOCAB[name]);
  const pyRepr = v => (v === undefined || v === null ? "None" : typeof v === "string" ? "'" + v + "'" : String(v));

  function recordId(rec) { const o = {}; for (const k of Object.keys(rec)) if (k !== "id") o[k] = rec[k]; return NM.sha256Id(o); }
  function recordFilename(rec, rs) { return `${rs.tileset.name}_${NM.idHex64(rec.id)}.record.json`; }

  /* 対局の検証。戻り値は注意（警告）の列。誤りがあれば ValidationError。rs・ts は渡す（JS 版は同梱から探さない）。 */
  function validateRecord(rec, rs, ts, walls) {
    const errs = [], warns = [];
    const err = m => errs.push(m), warn = m => warns.push(m);
    if (rec.format !== REC_FORMAT) err(`format が ${REC_FORMAT} ではない`);
    if (rec.version !== REC_VERSION) err(`version が ${REC_VERSION} ではない`);
    for (const k of Object.keys(rec)) if (!TOP_KEYS.includes(k)) err(`${k}: 未知の項目`);
    try {
      NM.idHex64(rec.id === undefined ? "" : rec.id);
      if (rec.id !== recordId(rec)) err("id が内容のハッシュと一致しない");
    } catch (e) { if (e instanceof ValidationError) err(e.message); else throw e; }
    const src = rec.source;
    if (!isObj(src) || !inVocab(src.kind, "source_kinds") || typeof src.from !== "string") err("source は {kind, from, ref}");
    if (!inVocab(rec.end, "record_end")) err(`end が語彙外: ${pyRepr(rec.end)}`);
    const rref = rec.ruleset;
    let norm = null;
    if (!isObj(rref) || !("id" in rref)) err("ruleset が {name, id} ではない");
    else if (!rs) warn("ルールが見つからないため層またぎ検証は未実施");
    else {
      if (rs.id !== rref.id) err("ruleset.id が渡されたルールと一致しない");
      norm = normalize(rs);
      if (!ts) warn("牌表が見つからないため牌番号の範囲は未照合");
    }
    let M = norm ? norm.players : null;
    const K = ts ? ts.tiles.length : null;
    const pl = rec.players;
    if (!Array.isArray(pl) || !pl.length) err("players が無い");
    else {
      if (M !== null && pl.length !== M) err(`players の長さ ${pl.length} ≠ ruleset.players ${M}`);
      pl.forEach((p, i) => { if (!isObj(p) || p.seat !== i) err(`players[${i}].seat が連番ではない`); });
      M = M || pl.length;
    }
    let rounds = rec.rounds;
    if (!Array.isArray(rounds) || !rounds.length) { err("rounds が空"); rounds = []; }
    let prevScores = norm && !rec.parent ? new Array(M).fill(norm.settlement.start_points) : null;
    rounds.forEach((rd, k) => {
      const p = `rounds[${k}]`;
      if (rd.index !== k) err(`${p}.index が連番ではない`);
      const st = rd.state;
      if (!isObj(st)) { err(`${p}.state が無い`); return; }
      if (!WINDS.includes(st.bakaze)) err(`${p}.state.bakaze が不正`);
      for (const key of ["kyoku", "honba", "kyotaku", "oya"]) if (!isInt(st[key])) err(`${p}.state.${key} が整数ではない`);
      const scores = st.scores;
      if (!Array.isArray(scores) || scores.length !== M) err(`${p}.state.scores の長さ ≠ ${M}`);
      else if (prevScores !== null && prevScores !== undefined && !eq(scores, prevScores)) err(`${p}.state.scores ${JSON.stringify(scores)} ≠ 前局の結果 ${JSON.stringify(prevScores)}`);
      if (norm) {
        if (norm.wall_rules.break.by === "dice" && !("dice" in st)) {
          if (rd.wall) err(`${p}.state.dice が無い（break.by=dice）`);
          else warn(`${p}.state.dice が無い（山なしの取り込みでは不明）`);
        }
        if (norm.game_rules.flow.wareme && !("wareme" in st)) err(`${p}.state.wareme が無い（wareme）`);
      }
      const oya = st.oya === undefined ? 0 : st.oya;
      const evs = rd.events;
      if (!Array.isArray(evs) || !evs.length) { err(`${p}.events が空`); return; }
      checkEvents(err, p, evs, M, K, norm);
      const res = rd.result;
      if (!isObj(res)) { err(`${p}.result が無い`); return; }
      checkResult(err, p, res, st, evs, M, norm, oya, ts);
      prevScores = res.scores;
      const wid = rd.wall ? rd.wall.id : null;
      if (wid === null || wid === undefined) {
        if (evs[0].t === "deal" && !("hands" in evs[0])) err(`${p}: wall が null なら deal.hands が必要`);
        warn(`${p}: 山なし（配牌・ツモ順は未照合）`);
      } else if (walls && wid in walls && norm && ts) checkAgainstWall(err, warn, p, walls[wid], norm, ts, oya, evs, rd.result || {});
      else if (norm && ts) warn(`${p}: wall ${wid.slice(0, 19)}… が渡されていないため未照合`);
    });
    const fin = rec.final;
    if (rec.end !== "in_progress") {
      if (!isObj(fin)) err("final が無い");
      else if (rounds.length && isObj(rounds[rounds.length - 1].result)) {
        const last = rounds[rounds.length - 1].result.scores;
        const fs = fin.scores;
        if (!Array.isArray(fs) || fs.length !== M) err("final.scores の長さが違う");
        else if (norm) {
          const leftover = norm.settlement.start_points * M - sum(last);
          const exp = last.slice();
          if (leftover > 0 && norm.game_rules.flow.riichi.stick_at_end === "to_first") {
            const rk = ranks(last, norm.settlement.tie);
            const tops = range(M).filter(i => rk[i] === 1);
            for (const i of tops) exp[i] += Math.floor(leftover / tops.length);
          }
          if (!eq(fs, exp)) err(`final.scores ${JSON.stringify(fs)} ≠ 最終局の結果（供託の扱い込み）${JSON.stringify(exp)}`);
          const rk = ranks(fs, norm.settlement.tie);
          if (!eq(fin.rank, rk)) err(`final.rank ${JSON.stringify(fin.rank)} ≠ 再計算 ${JSON.stringify(rk)}`);
          if ("settled" in fin) {
            const calc = settle(fs, norm.settlement);
            if (fin.settled.some((a, i) => Math.abs(a - calc[i]) > 1e-6)) err(`final.settled ${JSON.stringify(fin.settled)} ≠ 再計算 ${JSON.stringify(calc)}（X8）`);
          } else err("final.settled が無い");
          if ("chips" in fin) {
            const totC = new Array(M).fill(0);
            for (const r_ of rounds) for (const w_ of ((r_.result || {}).wins || [])) if (Array.isArray(w_.chips) && w_.chips.length === M) w_.chips.forEach((x, i) => { totC[i] += x; });
            if (canon(fin.chips) !== canon(totC)) err(`final.chips ${JSON.stringify(fin.chips)} ≠ 各和了の祝儀の合計 ${JSON.stringify(totC)}`);
          }
        }
      }
    }
    if (errs.length) throw new ValidationError(errs.join("; "));
    return warns;
  }

  function checkEvents(err, p, evs, M, K, norm) {
    if (evs[0].t !== "deal") err(`${p}.events[0] は deal`);
    let kans = 0, riichiPending = null;
    const kansBy = {};
    evs.forEach((e, i) => {
      const t = e.t, q = `${p}.events[${i}]`;
      if (!EVENT_TYPES.includes(t)) { err(`${q}.t が語彙外: ${pyRepr(t)}`); return; }
      for (const key of ["who", "from"]) if (key in e && !(isInt(e[key]) && e[key] >= 0 && e[key] < M)) err(`${q}.${key} が 0〜${M - 1} の外`);
      let tiles = [];
      if ("tile" in e) tiles.push(e.tile);
      if ("tiles" in e) tiles = tiles.concat(e.tiles);
      if (K !== null) for (const x of tiles) if (!(isInt(x) && x >= 0 && x < K)) err(`${q}: 牌番号 ${pyRepr(x)} が 0〜${K - 1} の外`);
      if (t === "riichi") riichiPending = e.who === undefined ? null : e.who;
      else if (t === "discard") {
        if (riichiPending !== null) {
          if (e.who !== riichiPending || !e.riichi) err(`${q}: riichi の直後は同じ who の discard（riichi:true）`);
          riichiPending = null;
        }
      } else if (t === "kan") {
        kans += 1;
        const isK = ["ankan", "minkan", "kakan"].includes(e.kind);
        if (!isK) err(`${q}.kind が不正`);
        if (e.kind === "minkan" && !("from" in e)) err(`${q}: minkan には from`);
        if (norm) {
          const fl = norm.game_rules.flow;
          if (kans > fl.max_kans) err(`${q}: カン ${kans} 回目 > max_kans ${fl.max_kans}（X6）`);
          if (isK && !fl.kan_kinds.includes(e.kind)) err(`${q}: ${e.kind} の無いルール（X6）`);
          kansBy[e.who] = (kansBy[e.who] || 0) + 1;
          if (fl.max_kans_per_player !== null && fl.max_kans_per_player !== undefined && kansBy[e.who] > fl.max_kans_per_player) {
            err(`${q}: seat ${e.who} のカン ${kansBy[e.who]} 回目 > max_kans_per_player ${fl.max_kans_per_player}（X6）`);
          }
        }
      } else if (t === "pon" && norm && !norm.game_rules.flow.pon) err(`${q}: pon 禁止のルール（X6）`);
      else if (t === "chi" && norm && !norm.game_rules.flow.chi) err(`${q}: chi 禁止のルール（X6）`);
      else if (t === "nuki" && norm && !norm.game_rules.nuki.enabled) err(`${q}: 抜きの無いルール（X6）`);
      if ((t === "win" || t === "draw_end") && i !== evs.length - 1) {
        if (!(t === "win" && evs.slice(i).every(x => x.t === "win"))) err(`${q}: ${t} は最後`);
      }
    });
  }

  function checkResult(err, p, res, st, evs, M, norm, oya, ts) {
    const wins = res.wins, draw = res.draw;
    if (!Array.isArray(wins)) { err(`${p}.result.wins が配列ではない`); return; }
    if (!wins.length && !isObj(draw)) err(`${p}.result: wins が空なら draw が必要`);
    if (wins.length && draw) err(`${p}.result: wins と draw の両方がある`);
    let total = new Array(M).fill(0);
    wins.forEach((w, j) => {
      const q = `${p}.result.wins[${j}]`;
      for (const key of ["who", "from", "tile", "hand", "yaku", "fu", "han", "points", "deltas"]) if (!(key in w)) err(`${q}.${key} が無い`);
      const d = w.deltas;
      if (!Array.isArray(d) || d.length !== M) { err(`${q}.deltas の長さ ≠ ${M}`); return; }
      total = total.map((a, i) => a + d[i]);
      if (norm) {
        const ov = norm.game_rules.yaku.overrides || {};
        const baseTbl = YAKU_TABLES[norm.game_rules.yaku.base] || { yaku: {}, yakuman: {} };
        let hanSum = 0;
        for (const y of w.yaku || []) {
          const nm = y.name;
          if (!(nm in VOCAB.yaku) && !(nm in VOCAB.yakuman)) { err(`${q}: 語彙に無い役 ${pyRepr(nm)}`); continue; }
          if (DORA_LIKE.includes(nm)) { hanSum += y.han || 0; continue; }
          const adopted = nm in ov ? ov[nm] : nm in baseTbl.yaku ? baseTbl.yaku[nm] : nm in baseTbl.yakuman ? baseTbl.yakuman[nm] : false;
          if (adopted === false) err(`${q}: 不採用の役 ${nm}（X7）`);
          if (!("yakuman" in y)) hanSum += y.han || 0;
        }
        if (!("yakuman" in w) && hanSum !== w.han) err(`${q}: 翻の合計 ${hanSum} ≠ han ${pyRepr(w.han)}（X7）`);
        const sc_ = norm.game_rules.scoring;
        let tot;
        if (sc_.table === "additive") {
          // 足し算の点数：内訳（additive）から 1 人の払いを出し直す。カラスは内訳の値が設定のどれかであること
          const bd = isObj(w.additive) ? w.additive : {};
          const ka = sc_.additive.karasu;
          const kk = ["menzen", "open"].find(n => ka[n] && bd.karasu === ka[n]) || null;
          if (![0, ka.menzen, ka.open].includes(bd.karasu)) err(`${q}: additive.karasu ${pyRepr(bd.karasu)} が設定に無い（X7）`);
          const [each, parts_] = additivePoints(w.han || 0, w.yakuman || 0, w.who === oya, st.honba || 0, kk, sc_);
          if (canon(bd) !== canon(parts_)) err(`${q}: additive の内訳が式と合わない（X7）`);
          tot = w.who === w.from ? each * (M - 1) : each;
        } else tot = totalPoints(w.fu || 0, w.han || 0, w.yakuman || 0, w.who === oya, w.who === w.from, M, sc_)[0];
        if (tot !== w.points) err(`${q}: points ${pyRepr(w.points)} ≠ 点数表 ${tot}（X7：fu=${pyRepr(w.fu)} han=${pyRepr(w.han)}）`);
        // 祝儀：ルールの規則から数え直す（飛びの祝儀は最初の和了に入る）
        const rules_ = norm.settlement.chips;
        if (rules_.length && ts && "chips" in w && Array.isArray(w.hand)) {
          const ms_ = w.melds || [];
          const wc = winChips(rules_, ts, w.hand.concat(...ms_.map(m => m.tiles || [])), w.yaku || [], w.yakuman || 0, w.who === w.from,
            !ms_.some(m => ["chi", "pon", "minkan", "kakan"].includes(m.kind)), w.tile);
          const exp = chipDeltas(wc, w.who, w.from, M, !!w.reverse);
          if (j === 0) for (const x of res.tobi_chips || []) { exp[x.from] -= x.chips; exp[x.to] += x.chips; }
          if (canon(w.chips) !== canon(exp)) err(`${q}: chips ${JSON.stringify(w.chips)} ≠ 規則から数えた枚数 ${JSON.stringify(exp)}`);
        } else if ("chips" in w && !rules_.length) err(`${q}: ルールに祝儀の規則が無いのに chips がある`);
      }
    });
    if (draw) {
      if (!inVocab(draw.reason, "draw_reasons")) err(`${p}.result.draw.reason が語彙外`);
      const d = draw.deltas;
      if (Array.isArray(d) && d.length === M) total = total.map((a, i) => a + d[i]);
      else err(`${p}.result.draw.deltas の長さ ≠ ${M}`);
    }
    if (norm) {
      const kp = norm.game_rules.scoring.kyotaku_points;
      const s = sum(total);
      const riichis = evs.filter(e => e.t === "riichi").length;
      let okSum = s === 0;
      if (kp && !okSum) for (let n = -riichis; n <= (st.kyotaku || 0) + riichis; n++) if (s === kp * n) { okSum = true; break; }
      if (!okSum) err(`${p}.result: 増減の合計 ${s} が供託で説明できない`);
    }
    const scores = res.scores;
    if (!Array.isArray(scores) || scores.length !== M) err(`${p}.result.scores の長さ ≠ ${M}`);
    else if (Array.isArray(st.scores) && st.scores.length === M) {
      const exp = st.scores.map((a, i) => a + total[i]);
      if (!eq(scores, exp)) err(`${p}.result.scores ${JSON.stringify(scores)} ≠ state.scores＋増減 ${JSON.stringify(exp)}`);
    }
  }

  /* X5：山と wall_rules から配牌・ツモ順・嶺上・ドラ表示を導き、出来事と順に一致するか。 */
  function checkAgainstWall(err, warn, p, wall, norm, ts, oya, evs, res) {
    if (wall.tileset.id !== ts.id) { err(`${p}: wall.tileset.id ≠ ruleset.tileset.id`); return; }
    const order = wall.order, K = order.length, wr = norm.wall_rules;
    const M = norm.players, N = norm.hand_size;
    let liveEnd = K - wr.dead_wall;
    const liveEnd0 = liveEnd;
    let pos = N * M + 1;
    if ("hands" in evs[0]) {
      for (let s = 0; s < M; s++) {
        const who = (oya + s) % M;
        if (!eq(numSort(evs[0].hands[who]), numSort(order.slice(s * N, (s + 1) * N)))) err(`${p}: 配牌 seat ${who} が山と一致しない（X5）`);
      }
    }
    let firstDrawDone = false, kanI = 0, rinI = 0, doraI = 0;
    const rin = wr.rinshan;
    const di = wr.dora_indicator || [];
    evs.forEach((e, i) => {
      const t = e.t, q = `${p}.events[${i}]`;
      let exp;
      if (t === "dora") {
        if (doraI < di.length) exp = order[liveEnd0 + di[doraI]];
        else {
          const kd = wr.kan_dora || [];
          if (kanI >= kd.length) { err(`${q}: カンドラの位置が足りない`); return; }
          exp = order[liveEnd0 + kd[kanI]];
          kanI += 1;
        }
        doraI += 1;
        if (e.tile !== exp) err(`${q}: ドラ表示 ${pyRepr(e.tile)} ≠ 山 ${exp}（X5）`);
      } else if (t === "draw") {
        if (!firstDrawDone) {
          exp = order[N * M];
          firstDrawDone = true;
          if (e.who !== oya) err(`${q}: 最初のツモは親（seat ${oya}）のはず`);
        } else if (e.rinshan) {
          if (rin === "live") { exp = order[pos]; pos += 1; }
          else if (Array.isArray(rin)) {
            let shrink = true;
            if (rinI < rin.length) { exp = order[liveEnd0 + rin[rinI]]; rinI += 1; shrink = !wr.rinshan_reserved; }
            else { exp = order[liveEnd - 1]; warn(`${q}: 嶺上 ${rin.length} 枚を超えたので海底側から`); }
            if (shrink) liveEnd -= 1;
          } else { err(`${q}: 嶺上の位置が足りない`); return; }
        } else {
          if (pos >= liveEnd) { err(`${q}: 山を引き切っている（X5）`); return; }
          exp = order[pos]; pos += 1;
        }
        if (e.tile !== exp) err(`${q}: ツモ ${pyRepr(e.tile)} ≠ 山 ${exp}（X5）`);
      }
    });
    if (pos > liveEnd) err(`${p}: 消費枚数 ${pos} > K−dead_wall ${liveEnd}`);
    if (res && Object.keys(res).length) {
      const n0 = Math.min(doraI, di.length);
      const expUra = (wr.ura_indicator || []).slice(0, n0).map(o => order[liveEnd0 + o]).concat((wr.kan_ura || []).slice(0, kanI).map(o => order[liveEnd0 + o]));
      (res.wins || []).forEach((w, j) => {
        if ("ura_indicators" in w && !eq(w.ura_indicators, expUra)) err(`${p}.result.wins[${j}].ura_indicators ${JSON.stringify(w.ura_indicators)} ≠ 山 ${JSON.stringify(expUra)}（X5）`);
      });
    }
  }

  const recordMod = { validate: validateRecord, computeId: recordId, filename: recordFilename, FORMAT: REC_FORMAT, VERSION: REC_VERSION };

  // ==== 記録係（recorder.py）：出来事を 1 つずつ受け取り、確かめて対局に積む ========================
  const INFO = ["abort", "dora"];
  const END_EVENTS = ["win", "draw_end", "abort", "chombo"];

  class Recorder {
    constructor(rs, ts, opt) {
      opt = opt || {};
      this.rs = rs; this.ts = ts;
      this.norm = normalize(rs);
      this.M = this.norm.players; this.N = this.norm.hand_size;
      this.checkLegal = opt.checkLegal === undefined ? true : opt.checkLegal;
      this.walls = {};
      this.warnings = [];
      this.rec = { format: REC_FORMAT, version: REC_VERSION,
        source: opt.source || { kind: "generated", from: "nmahjong.recorder", ref: null },
        ruleset: { name: rs.name, id: rs.id },
        players: opt.players || range(this.M).map(s => ({ seat: s, name: "seat" + s, external: [] })),
        end: "finished", parent: opt.parent === undefined ? null : opt.parent, rounds: [] };
      this._open = false; this._riichiAt = null; this._pos = 0; this._liveEnd = 0; this._rinI = 0; this._wall = null;
      this.listeners = [];
    }
    _notify() { for (const f of this.listeners) f(this.rec); }

    startRound(state, wall, dora) {
      if (this._open) throw new ValidationError("前の局が終わっていない（end_round が先）");
      for (const k of ["bakaze", "kyoku", "honba", "kyotaku", "oya", "scores"]) if (!(k in state)) throw new ValidationError(`state.${k} が無い`);
      if (state.scores.length !== this.M || !(state.oya >= 0 && state.oya < this.M)) throw new ValidationError("state.scores の長さか oya が人数と合わない");
      const wr = this.norm.wall_rules;
      const evs = [{ t: "deal" }];
      if (dora === undefined) dora = null;
      if (wall) {
        if (wall.tileset.id !== this.ts.id) throw new ValidationError("牌山の牌表がルールの牌表と違う");
        this.walls[wall.id] = wall;
        const order = wall.order;
        this._liveEnd = order.length - wr.dead_wall;
        this._pos = this.N * this.M;
        const exp = wr.dora_indicator && wr.dora_indicator.length ? order[this._liveEnd + wr.dora_indicator[0]] : null;
        if (dora !== null && exp !== null && dora !== exp) throw new ValidationError(`ドラ表示牌 ${dora} が牌山の ${exp} と違う`);
        if (dora === null) dora = exp;
      }
      if (dora !== null) evs.push({ t: "dora", tile: dora });
      this._wall = wall || null;
      this._rinI = 0;
      this._riichiAt = null;
      const rnd = { index: this.rec.rounds.length, wall: wall ? { id: wall.id } : null, state: deepCopy(state), events: evs };
      this.rec.rounds.push(rnd);
      this._open = true;
      return rnd;
    }

    endRound(result) {
      const rnd = this._cur();
      const evs = rnd.events;
      if (!evs.length || !END_EVENTS.includes(evs[evs.length - 1].t)) throw new ValidationError("局を閉じる出来事（win／draw_end／abort／chombo）がまだ積まれていない");
      for (const k of ["wins", "draw", "scores"]) if (!(k in result)) throw new ValidationError(`result.${k} が無い`);
      rnd.result = deepCopy(result);
      this._open = false;
      this._notify();
      return rnd;
    }

    /* 対局を閉じる。final を省くと最後の局の持ち点から順位と精算を計算する。top＝対局の先頭に足す項目（started_at など）。 */
    finish(final, end, top) {
      if (this._open) throw new ValidationError("局が終わっていない（end_round が先）");
      if (!this.rec.rounds.length) throw new ValidationError("局が 1 つも無い");
      const rec = this.rec;
      rec.end = end || "finished";
      Object.assign(rec, top || {});
      if (!final) {
        const st = this.norm.settlement;
        const last = rec.rounds[rec.rounds.length - 1];
        const scores = last.result.scores.slice();
        const left = sum(last.state.scores) + last.state.kyotaku * this.norm.game_rules.scoring.kyotaku_points - sum(scores);
        if (left > 0 && this.norm.game_rules.flow.riichi.stick_at_end === "to_first") scores[ranks(scores, st.tie).indexOf(1)] += left;
        final = { scores, rank: ranks(scores, st.tie), settled: settle(scores, st) };
        if (st.chips.length) {                                // 祝儀の規則があるルール：各和了の祝儀の合計
          final.chips = scores.map((_, s) => sum(rec.rounds.flatMap(r => (r.result.wins || []).filter(w => Array.isArray(w.chips)).map(w => w.chips[s]))));
        }
      }
      rec.final = final;
      rec.id = recordId(rec);
      this.warnings = this.warnings.concat(validateRecord(rec, this.rs, this.ts, this.walls));
      return rec;
    }

    push(ev) {
      const rnd = this._cur();
      const evs = rnd.events;
      const t = ev.t;
      if (!EVENT_TYPES.includes(t) || t === "deal") throw new ValidationError(`出来事の種類が不正: ${pyRepr(t)}`);
      const lastT = evs[evs.length - 1].t;
      if (lastT === "draw_end" || lastT === "chombo" || (lastT === "win" && t !== "win" && !INFO.includes(t))) throw new ValidationError(`局が終わっている（${lastT} のあとに ${t}）`);
      if ("who" in ev && !(isInt(ev.who) && ev.who >= 0 && ev.who < this.M)) throw new ValidationError(`who が範囲外: ${pyRepr(ev.who)}`);
      let at = evs.length - 1;
      while (at > 1 && INFO.includes(evs[at].t)) at--;
      if (INFO.includes(t)) { evs.push(deepCopy(ev)); this._notify(); return; }
      if (t === "draw") this._checkDraw(ev, evs);
      else if (t === "riichi") { this._legalSelf(ev, evs, at, null, "A"); this._riichiAt = at; }
      else if (t === "discard") {
        if (this._riichiAt !== null) {
          const r = evs[this._riichiAt + 1];
          if (r.who !== ev.who) throw new ValidationError("立直を宣言した人と打牌した人が違う");
          const a = { type: "riichi", tile: ev.tile };
          if (r.open) a.open = true;
          this._legal(ev.who, this._riichiAt, "A", a);
          this._riichiAt = null;
        } else this._legalSelf(ev, evs, at, { type: "discard", tile: ev.tile }, "B");
      } else if (t === "kan") {
        const a = { type: "kan", kind: ev.kind, tiles: numSort(ev.tiles || []) };
        if (ev.kind === "minkan") this._legal(ev.who, this._lastDiscardAt(evs), "C", a);
        else this._legalSelf(ev, evs, at, a, "A");
      } else if (t === "chi" || t === "pon") this._legal(ev.who, this._lastDiscardAt(evs), "C", { type: t, tiles: numSort(ev.tiles || []) });
      else if (t === "nuki") this._legalSelf(ev, evs, at, { type: "nuki", tile: ev.tile }, "A");
      else if (t === "win") this._checkWin(ev, evs);
      else if (t === "draw_end") this._checkDrawEnd(ev, evs);
      if (this._riichiAt !== null && t !== "riichi") throw new ValidationError("立直の宣言のあとは打牌が続く");
      evs.push(deepCopy(ev));
      try { replay(rnd, this.norm, this._wall, evs.length - 1); } catch (e) {
        evs.pop();
        if (t === "riichi") this._riichiAt = null;
        throw e;
      }
      this._notify();
    }

    _cur() {
      if (!this._open) throw new ValidationError("局が始まっていない（start_round が先）");
      return this.rec.rounds[this.rec.rounds.length - 1];
    }
    _lastDiscardAt(evs) {
      for (let i = evs.length - 1; i >= 0; i--) {
        if (evs[i].t === "discard") return i;
        if (evs[i].t !== "win" && !INFO.includes(evs[i].t)) break;
      }
      throw new ValidationError("直前が打牌ではない（鳴き・ロンは打牌に対してだけ）");
    }
    _obs(seat, at) { return observe(this.rec, this._cur().index, at, seat, this.rs, this.ts, this.walls); }
    _legal(seat, at, phase, action) {
      if (!this.checkLegal) return;
      const legal = legalActions(this.rs, this.ts, this._obs(seat, at), phase);
      const key = this.key(action);
      if (!legal.some(a => this.key(a) === key)) throw new ValidationError(`seat ${seat} の ${JSON.stringify(action)} は合法手に無い（時点 ${at}、候補 ${legal.length} 件）`);
    }
    /* 候補との照合の鍵。牌の番号ではなく「牌種と印」で比べる。 */
    key(a) {
      const tiles = this.ts.tiles;
      if (["discard", "riichi", "nuki"].includes(a.type) && isInt(a.tile) && tiles[a.tile]) {
        const t = tiles[a.tile];
        return JSON.stringify([a.type, t.kind, t.mark === undefined ? null : t.mark, Boolean(a.open)]);
      }
      if (["chi", "pon", "kan"].includes(a.type) && (a.tiles || []).every(x => tiles[x])) {
        const ks = (a.tiles || []).map(x => tiles[x].kind + "|" + (tiles[x].mark || "")).sort();
        return JSON.stringify([a.type, a.kind === undefined ? null : a.kind, ks]);
      }
      return actionKey(a);
    }
    _legalSelf(ev, evs, at, need, phase) {
      const seat = ev.who;
      const ph = phaseOf(evs, at, seat);
      if (ph !== "A" && ph !== "B") throw new ValidationError(`seat ${seat} の番ではない（直前は ${evs[at].t}）`);
      if (need === null) return;
      if (ph === "B" && phase === "A") throw new ValidationError(`鳴いた直後は打牌だけ（${ev.t} は不可）`);
      this._legal(seat, at, phase, need);
    }
    _checkDraw(ev, evs) {
      let last = evs[0];
      for (let i = evs.length - 1; i >= 0; i--) if (!INFO.includes(evs[i].t)) { last = evs[i]; break; }
      if (last.t === "draw") throw new ValidationError("ツモが 2 回続いている");
      if (!this._wall) return;
      const order = this._wall.order, wr = this.norm.wall_rules;
      let exp, viaPos = true, shrink = 1;
      if (ev.rinshan) {
        const rin = wr.rinshan;
        if (rin === "live") { exp = this._pos < this._liveEnd ? order[this._pos] : null; this._pos += 1; }
        else {
          const liveEnd0 = order.length - wr.dead_wall;
          if (this._rinI < rin.length) { exp = order[liveEnd0 + rin[this._rinI]]; shrink = wr.rinshan_reserved ? 0 : 1; }
          else exp = order[this._liveEnd - 1];
          this._rinI += 1;
          this._liveEnd -= shrink;
          viaPos = false;
        }
      } else { exp = this._pos < this._liveEnd ? order[this._pos] : null; this._pos += 1; }
      if (exp === null || ev.tile !== exp) {
        if (viaPos) this._pos -= 1; else { this._rinI -= 1; this._liveEnd += shrink; }
        throw new ValidationError(exp !== null ? `ツモ牌 ${pyRepr(ev.tile)} が牌山の次の牌 ${exp} と違う` : "牌山にツモれる牌が残っていない");
      }
    }
    _checkWin(ev, evs) {
      if (ev.from === ev.who) {
        let at = evs.length - 1;
        while (at > 1 && INFO.includes(evs[at].t)) at--;
        this._legalSelf(ev, evs, at, { type: "tsumo" }, "A");
        return;
      }
      let last = null, li = -1;
      for (let i = evs.length - 1; i >= 0; i--) if (evs[i].t !== "win" && !INFO.includes(evs[i].t)) { last = evs[i]; li = i; break; }
      if (last && (last.t === "kan" || last.t === "nuki")) {
        // 槍槓：加槓・抜きの牌へのロン。暗槓の牌は、ルールが認める国士無双だけ（canRob）
        const kind = last.t === "kan" ? last.kind : "nuki";
        const shown = last.t === "nuki" ? [last.tile] : (last.tiles || []);
        if (ev.from !== last.who || !shown.includes(ev.tile)) throw new ValidationError(`seat ${ev.who} のロンは、直前のカン・抜き（seat ${last.who}）の牌に対するものではない`);
        if (this.checkLegal && !canRob(this.norm, this.ts, this._obs(ev.who, li), kind, ev.tile)) throw new ValidationError(`seat ${ev.who} の槍槓（${kind} の牌へのロン）は合法手に無い（時点 ${li}）`);
        return;
      }
      this._legal(ev.who, this._lastDiscardAt(evs), "C", { type: "ron" });
    }
    _checkDrawEnd(ev, evs) {
      if (ev.reason === "exhaustive" && this._wall && this._pos < this._liveEnd && evs[evs.length - 1].t !== "draw") {
        throw new ValidationError(`山が ${this._liveEnd - this._pos} 枚残っているのに荒牌流局`);
      }
    }
  }

  const NOT_EXTRA = ["format", "version", "id", "source", "ruleset", "players", "end", "parent", "rounds", "final"];
  function extraTop(rec) { const o = {}; for (const k of Object.keys(rec)) if (!NOT_EXTRA.includes(k)) o[k] = deepCopy(rec[k]); return o; }

  /* 出来上がった対局を 1 手ずつ記録係に流し込む。戻り値の .rec が積み直した対局。 */
  function replayRecord(rec, rs, ts, walls, checkLegal, listener) {
    const r = new Recorder(rs, ts, { players: deepCopy(rec.players), source: deepCopy(rec.source), checkLegal: checkLegal === undefined ? true : checkLegal,
      parent: deepCopy(rec.parent === undefined ? null : rec.parent) });
    if (listener) r.listeners.push(listener);
    for (const rnd of rec.rounds) {
      const wall = rnd.wall ? (walls || {})[rnd.wall.id] : null;
      const evs = rnd.events;
      const d = evs.slice(0, 3).find(e => e.t === "dora");
      const cur = r.startRound(rnd.state, wall, d ? d.tile : null);
      let start = cur.events.length;
      if (!eq(evs.slice(0, start).map(e => e.t), cur.events.map(e => e.t))) { cur.events = [deepCopy(evs[0])]; start = 1; }
      for (const e of evs.slice(start)) r.push(e);
      r.endRound(rnd.result);
    }
    r.finish(deepCopy(rec.final), rec.end, extraTop(rec));
    return r;
  }

  const recorderMod = { Recorder, replayRecord };

  // ==== 進行役（dealer.py）：山を持ち、1 対局を最後まで進める ====================================
  const WIND_ORDER = "ESWN";

  /* このルールの設定のうち、進行役がまだ従えないもの（空なら全部従える）。 */
  function unsupported(rs) {
    const norm = normalize(rs);
    const g = norm.game_rules, fl = g.flow, end = norm.end, sc = g.scoring;
    const out = [];
    if (fl.wareme && norm.players !== 4) out.push("flow.wareme：四人打ち以外のわれめ（開門の家の決め方が四人打ちのものしか無い）");
    if (fl.atozuke === "forbidden") out.push("flow.atozuke＝forbidden：先付け（片和了は可）の決め方の出典が無い。後付けありとして進める。片和了も不可の完全先付けは kanzen_sakizuke");
    const nk = g.nuki || {};
    if (nk.enabled) {
      if (nk.forbid_keep) out.push("nuki.forbid_keep＝true：抜く牌を手に残すことを止める決まりは無い。残せるとして進める");
      if (nk.pao) out.push("nuki.pao＝true：抜きドラの責任払いは数えない");
    }
    for (const c of norm.settlement.chips) if (["kan", "nuki", "call", "yakitori"].includes(c.on)) out.push(`settlement.chips の on＝${c.on}：和了と飛び以外の祝儀は数えない`);
    return out;
  }

  /* 応答が無い・壊れている・打てない手だったときの既定の行動：打牌ならツモ切り（できなければ候補の先頭）、それ以外は見送り。 */
  function defaultAction(obs, legal, phase) {
    if (phase === "B") {
      const ds = legal.filter(a => a.type === "discard");
      const d = ds.find(a => a.tile === obs.drawn);
      return d || ds[0] || { type: "pass" };
    }
    return { type: "pass" };
  }

  class Dealer {
    /* opt.players：席 → 打ち手。打ち手は関数 ({seat, phase, round, at, obs, legal}) => 行動（Promise でもよい）。
       opt.decide(seat, phase, at) => 行動：合法手の一覧を作らずに直接決める（確認用）。
       opt.strict=false：壊れた応答・打てない手を既定の行動に置き換えて続ける（faults に残る）。
       opt.choose(kind, seat, scores) => 真偽：ルールが「選べる」としている所での選択。kind＝"agari_yame"・"tenpai_yame"（最終局で親がトップ。
         止めるなら true。既定は止める）、"agari_yame_not_top"（親がトップでないが止めてもよいルール。既定は続ける）。
       opt.clock() => 秒：時間制限（end.time_limit_sec）に使う時計。既定は Date.now() / 1000。 */
    constructor(rs, ts, opt) {
      opt = opt || {};
      this.rs = rs; this.ts = ts;
      this.norm = normalize(rs);
      this.unsupported = unsupported(rs);
      if (this.unsupported.length && !opt.allowUnsupported) {
        throw new ValidationError("進行役がまだ従えない設定がある：" + this.unsupported.join("／"));
      }
      this.g = this.norm.game_rules; this.fl = this.g.flow; this.sc = this.g.scoring;
      this.M = this.norm.players; this.N = this.norm.hand_size;
      this.rc = new Recorder(rs, ts, { players: opt.playerInfo, source: opt.source || { kind: "generated", from: "nmahjong.dealer", ref: null },
        checkLegal: opt.checkLegal === undefined ? true : opt.checkLegal, parent: opt.parent });
      this.players = opt.players || {};
      this.decide = opt.decide || null;
      this.strict = opt.strict === undefined ? true : opt.strict;
      this.walls = this.rc.walls;
      this.log = [];
      this.faults = [];
      this.requests = 0;
      this._sticks = [];
      this._choose = opt.choose || null;
      this._clock = opt.clock || (() => Date.now() / 1000);
      this._t0 = null;
    }

    /* 1 対局を最後まで進めて、対局（record）を返す。walls：(k, state) => 山 の関数か、山の配列。dice：(k, state) => [目, 目]。 */
    async play(walls, opt) {
      opt = opt || {};
      const maxRounds = opt.maxRounds || 1000;
      let state = { bakaze: "E", kyoku: 1, honba: 0, kyotaku: 0, oya: 0, scores: new Array(this.M).fill(this.norm.settlement.start_points) };
      let k = 0;
      let end = "finished";
      this._t0 = this._clock();
      for (;;) {
        const wall = typeof walls === "function" ? walls(k, state) : walls[k];
        if (opt.dice) state.dice = opt.dice(k, state).slice();
        else if (this.norm.wall_rules.break.by === "dice") {
          const h = parseInt(wall.id.slice(-8), 16);
          state.dice = [h % 6 + 1, Math.floor(h / 6) % 6 + 1];
        }
        if (this.fl.wareme) state.wareme = this.waremeSeat(state);
        const [result, info] = await this.playRound(state, wall);
        const [nxt, why] = this.nextState(state, result, info, k);
        if (nxt === null) { this.log.push(`終了：${why}`); if (why === "時間制限") end = "time_limit"; break; }
        state = nxt;
        k += 1;
        if (k >= maxRounds) throw new ValidationError(`${maxRounds} 局を超えた（終了の条件を確かめる）`);
      }
      return this.rc.finish(null, end, opt.top);
    }

    // ---- 山 ----
    _order() { return this.rc._wall.order; }
    _liveEnd0() { return this._order().length - this.norm.wall_rules.dead_wall; }
    _nextTile() { const rc = this.rc; return rc._pos < rc._liveEnd ? this._order()[rc._pos] : null; }
    _rinshanTile() {
      const rc = this.rc, rin = this.norm.wall_rules.rinshan;
      if (rin === "live") return this._nextTile();
      if (rc._rinI < rin.length) return this._order()[this._liveEnd0() + rin[rc._rinI]];
      return this._order()[rc._liveEnd - 1];
    }
    _doraTile(n) {
      const wr = this.norm.wall_rules;
      const offs = (wr.dora_indicator || []).concat(wr.kan_dora || []);
      return n < offs.length ? this._order()[this._liveEnd0() + offs[n]] : null;
    }

    // ---- 局 ----
    _rnd() { return this.rc.rec.rounds[this.rc.rec.rounds.length - 1]; }
    _evs() { return this._rnd().events; }
    _anchor() { const evs = this._evs(); let a = evs.length - 1; while (a > 1 && INFO.includes(evs[a].t)) a--; return a; }
    _state() { const rnd = this._rnd(); return replay(rnd, this.norm, this.rc._wall, rnd.events.length - 1); }
    _obs(seat, at) { return observe(this.rc.rec, this._rnd().index, at, seat, this.rs, this.ts, this.walls); }
    _winnable(seat, frm, tile) {
      const rnd = this._rnd();
      const ctx = contextAt(this.rc.rec, rnd.index, rnd.events.length - 1, seat, frm, tile, this.rs, this.ts, this.walls, []);
      return Boolean(judge(this.rs, this.ts, ctx).ok);
    }
    /* 打てる手。和了は、役がある（縛りを満たす）ときだけ残す。 */
    legal(seat, phase, at) {
      const obs = this._obs(seat, at);
      const legal = legalActions(this.rs, this.ts, obs, phase).filter(a => {
        if (a.type === "tsumo") return this._winnable(seat, seat, obs.drawn);
        if (a.type === "ron") return this._winnable(seat, obs.last_discard.who, obs.last_discard.tile);
        return true;
      });
      return [obs, legal];
    }
    async _request(seat, phase, at, obs, legal) {
      this.requests += 1;
      const p = this.players[seat];
      let action;
      try {
        if (!p) throw new ValidationError(`seat ${seat} の打ち手が無い`);
        const resp = await p({ seat, phase, round: this._rnd().index, at, obs: deepCopy(obs), legal: deepCopy(legal) });
        if (!isObj(resp) || typeof resp.type !== "string") throw new ValidationError(`応答が行動の形ではない: ${JSON.stringify(resp)}`);
        const key = this.rc.key(resp);
        const hit = legal.find(a => this.rc.key(a) === key);
        if (!hit) throw new ValidationError(`seat ${seat} の応答 ${JSON.stringify(resp)} は打てる手に無い`);
        action = Object.assign({}, hit, resp);           // 牌の番号は応答のものを使う（同じ牌種・印ならどの 1 枚でもよい）
      } catch (e) {
        if (this.strict || !(e instanceof ValidationError)) throw e;
        this.faults.push(`seat ${seat} ${phase} at ${at}: ${e.message}`);
        action = defaultAction(obs, legal, phase);
      }
      return action;
    }
    /* seat に判断を求める。見送りしか無ければ聞かない。 */
    async _ask(seat, phase, at) {
      if (this.decide) return (await this.decide(seat, phase, at)) || { type: "pass" };
      const [obs, legal] = this.legal(seat, phase, at);
      if (!legal.some(a => a.type !== "pass")) return { type: "pass" };
      return this._request(seat, phase, at, obs, legal);
    }
    /* カン・抜きの牌へのロン（槍槓）を他家に聞く。ロンする席を巡目順に返す。 */
    async _askRob(kanner, tile, at, kind) {
      const out = [];
      for (let k = 1; k < this.M; k++) {
        const s = (kanner + k) % this.M;
        let a;
        if (this.decide) a = (await this.decide(s, "C", at)) || { type: "pass" };
        else {
          const obs = this._obs(s, at);
          if (!canRob(this.norm, this.ts, obs, kind || "kakan", tile) || !this._winnable(s, kanner, tile)) continue;
          a = await this._request(s, "C", at, obs, [{ type: "ron" }, { type: "pass" }]);
        }
        if (a.type === "ron") out.push(s);
      }
      return out;
    }
    _reveal(n) {
      for (let i = 0; i < n; i++) {
        const t = this._doraTile(this._evs().filter(e => e.t === "dora").length);
        if (t !== null) this.rc.push({ t: "dora", tile: t });
      }
    }
    /* 行動 → 出来事（1 つか 2 つ）を記録係に積む。見送りは何も積まない。 */
    apply(seat, action, at) {
      const rnd = this._rnd();
      const obs = this._obs(seat, at === undefined || at === null ? rnd.events.length - 1 : at);
      const t = action.type, ld = obs.last_discard;
      const evs = [];
      if (t === "pass") return evs;
      if (t === "discard") evs.push({ t: "discard", who: seat, tile: action.tile, tsumogiri: action.tile === obs.drawn });
      else if (t === "riichi") {
        const r = { t: "riichi", who: seat };
        if (action.open) r.open = true;
        evs.push(r);
        evs.push({ t: "discard", who: seat, tile: action.tile, tsumogiri: action.tile === obs.drawn, riichi: true });
      } else if (t === "chi" || t === "pon") evs.push({ t, who: seat, tiles: numSort(action.tiles), from: ld.who });
      else if (t === "kan") {
        const e = { t: "kan", who: seat, kind: action.kind, tiles: numSort(action.tiles) };
        if (action.kind === "minkan") e.from = ld.who;
        evs.push(e);
      } else if (t === "nuki") evs.push({ t: "nuki", who: seat, tile: action.tile });
      else if (t === "tsumo") evs.push({ t: "win", who: seat, from: seat, tile: obs.drawn });
      else if (t === "ron") evs.push({ t: "win", who: seat, from: ld.who, tile: ld.tile });
      else if (t === "draw_declare") evs.push({ t: "draw_end", reason: action.reason === undefined ? null : action.reason });
      else throw new ValidationError(`積めない行動: ${JSON.stringify(action)}`);
      let done = 0;
      try { for (const e of evs) { this.rc.push(e); done++; } } catch (e) {
        rnd.events.splice(rnd.events.length - done, done);
        this.rc._riichiAt = null;
        throw e;
      }
      return evs;
    }

    /* 1 局を進める。戻り値は [result, info]。 */
    async playRound(state, wall) {
      const rc = this.rc, M = this.M;
      rc.startRound(state, wall);
      const oya = state.oya;
      const d = this.g.dora;
      const timing = d.kan_timing || {};
      this._sticks = [];
      let pending = 0, seat = oya, draw = "normal", afterRinshan = 0;
      const kanDora = kind => {
        if (!d.kan) return;
        const when = timing[kind] || (kind === "minkan" ? "after_discard" : "immediate");
        if (when === "immediate") this._reveal(1);
        else if (when === "after_rinshan") afterRinshan = 1;
        else pending += 1;
      };
      for (;;) {
        if (draw === "normal") {
          const t = this._nextTile();
          if (t === null) return this._endExhaustive(state);
          rc.push({ t: "draw", who: seat, tile: t });
        } else if (draw === "rinshan") {
          const t = this._rinshanTile();
          if (t === null || t === undefined) return this._endExhaustive(state);
          rc.push({ t: "draw", who: seat, tile: t, rinshan: true });
          if (afterRinshan) this._reveal(afterRinshan);
        }
        afterRinshan = 0;
        const at = this._anchor();
        let a = { type: "pass" };
        if (draw !== null) a = await this._ask(seat, "A", at);
        const t = a.type;
        if (t === "tsumo") { this.apply(seat, a, at); return this._endWin(state, [seat]); }
        if (t === "draw_declare") { this.apply(seat, a, at); return this._endAbort(state, a.reason || "nine_terminals", [seat]); }
        if (t === "kan" || t === "nuki") {
          this.apply(seat, a, at);
          const kanAt = this._evs().length - 1;
          const kind = t === "kan" ? a.kind : "nuki";
          if (kind === "kakan" || t === "nuki" || (kind === "ankan" && this.fl.kokushi_ankan_chankan)) {
            const tile = t === "nuki" ? a.tile : this._addedTile(a, kanAt);
            let rons = await this._askRob(seat, tile, kanAt, kind);
            if (rons.length) {
              rons = this._limitRons(rons);
              if (rons === null) { rc.push({ t: "draw_end", reason: "three_ron" }); return this._endAbort(state, "three_ron", []); }
              for (const s of rons) rc.push({ t: "win", who: s, from: seat, tile });
              return this._endWin(state, rons);
            }
          }
          if (pending) { this._reveal(pending); pending = 0; }
          if (t === "kan" && d.kan) {
            const when = timing[kind] || "immediate";
            if (when === "immediate") this._reveal(1);
            else if (when === "after_rinshan") afterRinshan = 1;
            else pending += 1;
          }
          draw = "rinshan";
          continue;
        }
        let riichi;
        if (t === "riichi") {
          if (pending) { this._reveal(pending); pending = 0; }
          this.apply(seat, a, at);
          riichi = true;
        } else {
          a = await this._ask(seat, "B", at);
          if (a.type !== "discard") throw new ValidationError(`seat ${seat} の打牌が得られない: ${JSON.stringify(a)}`);
          if (pending) { this._reveal(pending); pending = 0; }
          this.apply(seat, a, at);
          riichi = false;
        }
        const dat = this._anchor();
        const answers = [];
        for (let k = 1; k < M; k++) {
          const s = (seat + k) % M;
          const r = await this._ask(s, "C", dat);
          if (r.type !== "pass") answers.push([s, r]);
        }
        let rons = answers.filter(([, r]) => r.type === "ron").map(([s]) => s);
        if (riichi && this.fl.riichi.stick_if_ronned) { this._sticks.push(seat); riichi = false; }
        if (rons.length) {
          rons = this._limitRons(rons);
          if (rons === null) { rc.push({ t: "draw_end", reason: "three_ron" }); return this._endAbort(state, "three_ron", []); }
          const tile = this._evs()[dat].tile;
          for (const s of rons) rc.push({ t: "win", who: s, from: seat, tile });
          return this._endWin(state, rons);
        }
        if (riichi) this._sticks.push(seat);
        const ab = this._abortAfterDiscard();
        if (ab) { rc.push({ t: "draw_end", reason: ab[0] }); return this._endAbort(state, ab[0], ab[1]); }
        const call = answers.find(([, r]) => r.type === "pon" || r.type === "kan") || answers.find(([, r]) => r.type === "chi");
        if (call) {
          const [s, r] = call;
          this.apply(s, r, dat);
          seat = s;
          if (r.type === "kan") { kanDora("minkan"); draw = "rinshan"; } else draw = null;
          continue;
        }
        seat = (seat + 1) % M;
        draw = "normal";
      }
    }

    _addedTile(a, kanAt) {
      if (a.kind !== "kakan") return a.tiles[0];
      const rnd = this._rnd();
      const before = replay(rnd, this.norm, this.rc._wall, kanAt - 1);
      const seat = rnd.events[kanAt].who;
      const pon = before.melds[seat].find(m => m.kind === "pon" && isSubset(m.tiles, a.tiles));
      return a.tiles.find(x => !pon.tiles.includes(x));
    }
    /* 同時のロンの扱い。null＝三家和で流局。 */
    _limitRons(rons) {
      const fl = this.fl;
      if (rons.length >= 3) {
        if (fl.triple_ron === "draw") return null;
        if (fl.triple_ron === "head") return rons.slice(0, 1);
        return rons;
      }
      if (rons.length === 2 && !fl.double_ron) return rons.slice(0, 1);
      return rons;
    }
    /* 打牌が通ったあとの途中流局。[理由, 手牌を見せる席] か null。 */
    _abortAfterDiscard() {
      const ry = this.fl.ryukyoku || {};
      const st = this._state();
      const M = this.M;
      if (ry.four_riichi && M === 4 && st.riichi.every(Boolean)) return ["four_riichi", range(M)];
      if (ry.four_winds && M === 4 && st.calls === 0 && !st.nuki.some(x => x.length) && st.discards.every(dd => dd.length === 1)) {
        const ks = new Set(st.discards.map(dd => kindOf(this.ts, dd[0].tile)));
        if (ks.size === 1 && WINDS.includes([...ks][0])) return ["four_winds", []];
      }
      if (ry.four_kans && st.kans === 4) {
        const owners = range(M).filter(s => st.melds[s].some(isKan));
        if (owners.length >= 2) return ["four_kans", []];
      }
      return null;
    }

    // ---- 局の結果 ----
    /* 割れ目（開門の家）の席。出目の合計を親から反時計回りに数える：5・9＝親、2・6・10＝下家、3・7・11＝対面、4・8・12＝上家。サイコロを使わないルールでは親。 */
    waremeSeat(state) { return state.dice ? (state.oya + state.dice[0] + state.dice[1] - 1) % this.M : state.oya; }
    _baseDeltas() { const kp = this.sc.kyotaku_points; const d = new Array(this.M).fill(0); for (const s of this._sticks) d[s] -= kp; return d; }

    _endWin(state, winners) {
      const rc = this.rc, M = this.M, sc = this.sc;
      const rnd = this._rnd(), evs = rnd.events;
      const first = evs.findIndex(e => e.t === "win");
      const oya = state.oya;
      const hp = sc.honba_points, kp = sc.kyotaku_points;
      const wins = [];
      let scores = state.scores.slice();
      winners.forEach((w, j) => {
        const e = evs[first + j];
        const ctx = contextAt(rc.rec, rnd.index, first - 1, w, e.from, e.tile, this.rs, this.ts, this.walls);
        const res = judge(this.rs, this.ts, ctx);
        if (!res.ok) throw new ValidationError(`seat ${w} の和了を判定できない：${res.reason}`);
        const tsumo = ctx.tsumo;
        const additive = sc.table === "additive";
        let total, parts, each = 0, breakdown = null;
        if (additive) {
          // 足し算の点数：本場は式の中で数える。ロンは放銃者が、ツモは残りの全員が、それぞれ同じ点を払う
          const meldsAll = this._meldsOf(w, first);
          const kinds = ctx.hand.concat(...meldsAll.filter(m => m.kind !== "nuki").map(m => m.tiles)).map(t => kindOf(this.ts, t));
          const menzen = !meldsAll.some(m => ["chi", "pon", "minkan", "kakan"].includes(m.kind));
          const karasu = karasuKind(kinds, (ctx.nuki || []).length, menzen, this.g.nuki || {});
          [each, breakdown] = additivePoints(res.han, res.yakuman || 0, w === oya, state.honba, karasu, sc);
          total = tsumo ? each * (M - 1) : each;
          parts = new Array(tsumo ? M - 1 : 1).fill(each);
        } else [total, parts] = totalPoints(res.fu, res.han, res.yakuman || 0, w === oya, tsumo, M, sc);
        let deltas = j === 0 ? this._baseDeltas() : new Array(M).fill(0);
        const beforeHand = deltas.slice();
        let payList = [];
        const split = this.fl.kyotaku_to === "split";       // 複数和了：kamicha＝本場と供託は最初（上家取り）の和了者だけ。split＝本場は各自、供託は等分
        const honba = additive ? 0 : (j === 0 || split) ? state.honba : 0;      // 足し算の点数では、本場は点の式に入っている
        const standard = sc.payment === "standard";
        if (tsumo && additive) {
          const others = range(M - 1).map(k => (w + k + 1) % M);
          payList = others.map(s => [s, each]);
          for (const s of others) { deltas[s] -= each; deltas[w] += each; }
        } else if (tsumo) {
          const others = range(M - 1).map(k => (w + k + 1) % M);
          if (standard) {
            const perH = Math.floor(hp / 3);
            const pay = [];
            if (w === oya) for (const s of others) pay.push([s, parts[0]]);
            else {
              pay.push([oya, parts[0]]);
              others.filter(s => s !== oya).forEach((s, i) => { if (i + 1 < parts.length) pay.push([s, parts[i + 1]]); });
            }
            payList = pay;
            for (const [s, p] of pay) { deltas[s] -= p + perH * honba; deltas[w] += p + perH * honba; }
          } else {
            const s = others[0];
            deltas[s] -= total + hp * honba;
            deltas[w] += total + hp * honba;
          }
        } else {
          const h = standard ? Math.floor(hp / 3) * (M - 1) * honba : hp * honba;
          deltas[e.from] -= total + h;
          deltas[w] += total + h;
        }
        const [liable, share] = this._pao(w, first, res);
        const hasPao = liable !== null && liable !== w;
        if (hasPao) deltas = this._paoDeltas(j, w, e.from, liable, share, total, honba, tsumo);
        const wm = this.fl.wareme && state.wareme !== undefined && state.wareme !== null ? state.wareme : null;
        if (wm !== null) {
          // われめ：割れ目の席の和了は全員の払いが 2 倍、割れ目の席の払いは 2 倍。本場・供託・飛びの罰符は倍にしない
          let hand;
          if (hasPao) hand = this._paoDeltas(1, w, e.from, liable, share, total, 0, tsumo);
          else {
            hand = new Array(M).fill(0);
            if (!tsumo) hand[e.from] = -total;
            else if (standard) for (const [s, p] of payList) hand[s] = -p;
            else hand[(w + 1) % M] = -total;
          }
          for (let s = 0; s < M; s++) if (s !== w && hand[s] < 0 && (w === wm || s === wm)) { deltas[s] += hand[s]; deltas[w] -= hand[s]; }
        }
        // 逆ポッチ：和了は成立するが、点（本場を含む）は和了者が払う側になる。供託はふつうどおり和了者が取る
        if (res.reverse) deltas = deltas.map((d, i) => beforeHand[i] - (d - beforeHand[i]));
        const sticks = state.kyotaku + this._sticks.length;
        if (split) deltas[w] += kp * (Math.floor(sticks / winners.length) + (j === 0 ? sticks % winners.length : 0));   // 割り切れない分は上家
        else if (j === 0) deltas[w] += kp * sticks;
        const win = { who: w, from: e.from, tile: e.tile, hand: numSort(ctx.hand), melds: this._meldsOf(w, first),
          yaku: res.yaku, fu: res.fu, han: res.han, points: total, deltas };
        if (res.yakuman) win.yakuman = res.yakuman;
        if (additive) { win.fu = 0; win.additive = breakdown; }
        if ((ctx.riichi || ctx.open_riichi) && this.g.dora.ura) win.ura_indicators = ctx.ura_indicators.slice();
        if (hasPao) win.pao = liable;
        if (res.reverse) win.reverse = true;
        const chipRules = this.norm.settlement.chips;
        if (chipRules.length) {
          // 祝儀：和了者の手牌と副露（抜いた牌を含む）で数える。ロンは放銃者、ツモは全員（payer＝loser）。逆ポッチは払う側
          const ms = this._meldsOf(w, first);
          const wc = winChips(chipRules, this.ts, ctx.hand.concat(...ms.map(m => m.tiles)), res.yaku, res.yakuman || 0, tsumo,
            !ms.some(m => ["chi", "pon", "minkan", "kakan"].includes(m.kind)), e.tile);
          win.chips = chipDeltas(wc, w, e.from, M, !!res.reverse);
        }
        wins.push(win);
        scores = scores.map((a, i) => a + deltas[i]);
      });
      const result = { wins, draw: null, scores };
      const pen = this._tobiPenalty(scores, winners[0], range(M).filter(x => !winners.includes(x)));
      if (pen.length) {
        for (const p of pen) {                               // 飛ばした和了（上家取りの和了者）の増減に入れる
          wins[0].deltas[p.from] -= p.points; wins[0].deltas[p.to] += p.points;
          scores[p.from] -= p.points; scores[p.to] += p.points;
        }
        result.tobi_penalty = pen;
      }
      const tobiCount = sum(this.norm.settlement.chips.filter(c => c.on === "tobi").map(c => c.count));
      const tc = tobiCount ? range(M).filter(s => !winners.includes(s) && this._busted(scores[s])).map(s => ({ from: s, to: winners[0], chips: tobiCount })) : [];
      if (tc.length) {
        for (const x of tc) { wins[0].chips[x.from] -= x.chips; wins[0].chips[x.to] += x.chips; }   // 飛びの祝儀：飛んだ人が、飛ばした和了者に払う
        result.tobi_chips = tc;
      }
      rc.endRound(result);
      return [result, { kind: "win", winners, dealer_won: winners.includes(oya) }];
    }

    _busted(x) {
      const tb = this.norm.end.tobi || {};
      const at = tb.at || 0;
      return Boolean(tb.enabled) && (x < at || (x === at && Boolean(tb.exact_zero_is_tobi)));
    }

    /* 飛びの罰符（end.tobi.penalty_points）。飛んだ席が、飛ばした席 to に払う。to＝null のときは払わない。 */
    _tobiPenalty(scores, to, payers) {
      const tb = this.norm.end.tobi || {};
      const P = tb.penalty_points || 0;
      if (!P || to === null || to === undefined || (tb.penalty_to || "none") === "none") return [];
      return payers.filter(s => s !== to && this._busted(scores[s])).map(s => ({ from: s, to, points: P }));
    }

    /* 包（責任払い）。[責任のある席, 役満の倍数のうち包にあたる分の割合] か [null, 0]。 */
    _pao(w, upto, res) {
      const names = this.g.pao.yakuman || [];
      const ym = {};
      for (const y of res.yaku) if ("yakuman" in y) ym[y.name] = y.yakuman;
      if (!Object.keys(ym).length || !names.length) return [null, 0];
      const melds = this._meldsOf(w, upto).filter(m => m.kind !== "nuki");
      const kind = m => kindOf(this.ts, m.tiles[0]);
      const opened = m => m.kind === "pon" || m.kind === "minkan" || m.kind === "kakan";
      let liable = null, mult = 0;
      for (const [name, group, need] of [["daisangen", DRAGONS, 3], ["daisuushii", WINDS, 4]]) {
        if (name in ym && names.includes(name)) {
          const ms = melds.filter(m => group.includes(kind(m)));
          if (ms.length === need && ms.every(opened) && ms[ms.length - 1].from !== w) { liable = ms[ms.length - 1].from; mult += ym[name]; }
        }
      }
      if ("suukantsu" in ym && names.includes("suukantsu")) {
        const ks = melds.filter(isKan);
        if (ks.length === 4 && ks[3].kind === "minkan" && ks[3].from !== w) { liable = ks[3].from; mult += ym.suukantsu; }
      }
      if (liable === null) return [null, 0];
      return [liable, mult / sum(Object.values(ym))];
    }
    _paoDeltas(j, w, frm, liable, share, total, honba, tsumo) {
      const M = this.M, sc = this.sc, pao = this.g.pao;
      const hp = sc.honba_points;
      const d = j === 0 ? this._baseDeltas() : new Array(M).fill(0);
      const hon = (sc.payment === "standard" ? Math.floor(hp / 3) * (M - 1) : hp) * honba;
      if (tsumo) d[liable] -= total + hon;
      else {
        const ron = pao.ron || "split";
        const part = ron === "split_all" ? total : Math.trunc(total * share), rest = total - part;
        if (ron === "split" || ron === "split_all") { const half = Math.floor(part / 2); d[liable] -= half; d[frm] -= part - half + rest; }
        else { d[liable] -= part; d[frm] -= rest; }
        d[(pao.honba_kyotaku || "discarder") === "discarder" ? frm : liable] -= hon;
      }
      d[w] += total + hon;
      return d;
    }
    /* 和了者の副露を、出来事の順に（抜きも 1 つとして入れる）。加槓はポンを置き換える。 */
    _meldsOf(seat, upto) {
      const out = [];
      for (const e of this._evs().slice(0, upto)) {
        if (e.who !== seat) continue;
        if (e.t === "chi" || e.t === "pon") out.push({ kind: e.t, tiles: e.tiles.slice(), from: e.from });
        else if (e.t === "kan") {
          if (e.kind === "kakan") { const m = out.find(x => x.kind === "pon" && isSubset(x.tiles, e.tiles)); m.kind = "kakan"; m.tiles = e.tiles.slice(); }
          else out.push({ kind: e.kind, tiles: e.tiles.slice(), from: e.from === undefined ? seat : e.from });
        } else if (e.t === "nuki") out.push({ kind: "nuki", tiles: [e.tile], from: seat });
      }
      return out;
    }

    tenpai(st, seat) { return tenpaiWaits(this.ts, st.hands[seat], st.melds[seat].length, this.N).size > 0; }

    _endExhaustive(state) {
      const rc = this.rc, M = this.M, sc = this.sc;
      const st = this._state();
      const nm = this.g.nagashi_mangan || {};
      const ten = range(M).map(s => this.tenpai(st, s));
      const deltas = this._baseDeltas();
      let reason = "exhaustive";
      const nagashi = [];
      if (nm.enabled) {
        for (let s = 0; s < M; s++) {
          const ds = st.discards[s];
          if (ds.length && ds.every(x => isYao(kindOf(this.ts, x.tile)) && !x.called)) nagashi.push(s);
        }
      }
      const oya = state.oya;
      const as_ = nm.as || "tenpai_settlement";
      if (nagashi.length) {
        // as：tenpai_settlement・draw_mangan＝流局の扱いで満貫のツモの額、yakuman＝流局の扱いで役満のツモの額、
        //     win＝和了の扱い（満貫のツモの額に、本場と供託も取る。連荘は親が流し満貫のときだけ）
        reason = "nagashi_mangan";
        nagashi.forEach((w, j) => {
          // 足し算の点数：満貫は 5 翻ぶん、役満は役満の点を、残りの全員がそれぞれ払う
          const parts = sc.table === "additive"
            ? new Array(M - 1).fill(additivePoints(as_ === "yakuman" ? 0 : 5, as_ === "yakuman" ? 1 : 0, w === oya, state.honba, null, sc)[0])
            : totalPoints(30, 5, as_ === "yakuman" ? 1 : 0, w === oya, true, M, sc)[1];
          const others = range(M - 1).map(k => (w + k + 1) % M);
          const pay = [];
          if (w === oya) for (const s of others) pay.push([s, parts[0]]);
          else {
            pay.push([oya, parts[0]]);
            others.filter(s => s !== oya).forEach((s, i) => { if (i + 1 < parts.length) pay.push([s, parts[i + 1]]); });
          }
          const hon = (as_ === "win" && j === 0 && sc.payment === "standard") ? Math.floor(sc.honba_points / 3) * state.honba : 0;
          for (const [s, p] of pay) { deltas[s] -= p + hon; deltas[w] += p + hon; }
          if (as_ === "win" && j === 0) deltas[w] += sc.kyotaku_points * (state.kyotaku + this._sticks.length);
        });
      }
      if (!nagashi.length || (nm.noten_penalty && as_ !== "win")) {
        const total = sc.noten_penalty;
        const n = ten.filter(Boolean).length;
        if (total && n > 0 && n < M) {
          const unit = M <= 4 ? Math.floor(total / 3) : Math.floor(total / (M - 1));
          let gain, loss;
          if (M === 4) { gain = Math.floor(total / n); loss = Math.floor(total / (M - n)); }
          else if (M === 3) { gain = n === 1 ? Math.floor(2 * unit / n) : unit; loss = n === 1 ? unit : 2 * unit; }
          else { gain = total; loss = total; }
          for (let s = 0; s < M; s++) deltas[s] += ten[s] ? gain : -loss;
        }
      }
      rc.push({ t: "draw_end", reason });
      const scores = state.scores.map((a, i) => a + deltas[i]);
      // 飛びの罰符：ノーテン罰符（流し満貫の払い）で飛んだとき、聴牌者（流し満貫の人）のうち、飛んだ席から見て最初の席へ
      const tb = this.norm.end.tobi || {};
      const pen = [];
      if (tb.penalty_to === "tenpai_players" && tb.on_noten_penalty !== false) {
        const takers = nagashi.length ? nagashi : range(M).filter(s => ten[s]);
        for (let s = 0; s < M; s++) {
          if (takers.includes(s) || deltas[s] >= 0) continue;
          let to = null;
          for (let k = 1; k < M; k++) if (takers.includes((s + k) % M)) { to = (s + k) % M; break; }
          for (const p of this._tobiPenalty(scores, to, [s])) pen.push(p);
        }
        for (const p of pen) {
          deltas[p.from] -= p.points; deltas[p.to] += p.points;
          scores[p.from] -= p.points; scores[p.to] += p.points;
        }
      }
      const draw = { reason, tenpai: ten, hands: range(M).map(s => (ten[s] ? numSort(st.hands[s]) : null)), deltas };
      const result = { wins: [], draw, scores };
      if (pen.length) result.tobi_penalty = pen;
      rc.endRound(result);
      const info = { kind: "draw", reason, dealer_tenpai: ten[oya], any_tenpai: ten.some(Boolean), nagashi };
      if (nagashi.length && as_ === "win") info.nagashi_win = true;
      return [result, info];
    }

    /* 途中流局。show＝手牌を見せる席（九種九牌の宣言者、四家立直の全員）。 */
    _endAbort(state, reason, show) {
      const M = this.M;
      const st = this._state();
      const deltas = this._baseDeltas();
      const ten = range(M).map(s => show.includes(s));
      const draw = { reason, tenpai: ten, hands: range(M).map(s => (ten[s] ? numSort(st.hands[s]) : null)), deltas };
      const result = { wins: [], draw, scores: state.scores.map((a, i) => a + deltas[i]) };
      this.rc.endRound(result);
      return [result, { kind: "abort", reason }];
    }

    /* 局の結果から次の局の state を作る。対局が終わるなら [null, 理由]。 */
    nextState(state, result, info, k) {
      const norm = this.norm, fl = this.fl, M = this.M;
      const end = norm.end;
      const oya = state.oya;
      const scores = result.scores.slice();
      const rule = Object.assign({}, fl.renchan, (fl.renchan.by_bakaze || {})[state.bakaze] || {});
      let renchan, honba, kyotaku;
      if (info.kind === "win") {
        renchan = Boolean(info.dealer_won && rule.dealer_win !== false);
        honba = renchan ? state.honba + 1 : 0;
        kyotaku = 0;
      } else if (info.kind === "abort") {
        renchan = fl.renchan_on_abort !== false;
        honba = state.honba + 1;
        kyotaku = state.kyotaku + this._sticks.length;
      } else if (info.nagashi_win) {                         // 流し満貫を和了の扱いにするルール：親が流し満貫なら連荘、供託は取られている
        renchan = info.nagashi.includes(oya) && rule.dealer_win !== false;
        honba = renchan ? state.honba + 1 : 0;
        kyotaku = 0;
      } else {
        const dt = info.dealer_tenpai;
        renchan = Boolean(rule.draw || (dt && rule.dealer_tenpai !== false) || (!info.any_tenpai && rule.all_noten) || (!dt && rule.dealer_noten));
        if (info.nagashi && info.nagashi.length && (this.g.nagashi_mangan || {}).renchan_if_dealer_tenpai === false) renchan = false;   // 流し満貫の局は親が流れるルール
        honba = state.honba + 1;
        kyotaku = state.kyotaku + this._sticks.length;
      }
      const tobi = end.tobi || {};
      if (tobi.enabled) {
        const at = tobi.at || 0;
        const byNoten = info.kind === "draw" && tobi.on_noten_penalty === false;   // ノーテン罰符の払いでは飛ばないルール
        if (!byNoten && scores.some(x => x < at || (x === at && tobi.exact_zero_is_tobi))) return [null, "飛び"];
      }
      const cold = end.cold_points;
      if (cold !== null && cold !== undefined && Math.max(...scores) >= cold) return [null, "コールド"];
      const limit = end.time_limit_sec;
      if (limit !== null && limit !== undefined && this._t0 !== null && this._clock() - this._t0 >= limit) return [null, "時間制限"];   // その局を終えて終了
      const length = norm.length;
      const windsN = { one: 0, east: 1, east_south: 2, full: 4 }[length];
      const total = norm.rounds_total;
      const bi = WIND_ORDER.indexOf(state.bakaze);
      const lastRegular = length === "one" || (windsN !== undefined && windsN > 0 && bi === windsN - 1 && state.kyoku === M)
        || (length === "custom" && total !== null && total !== undefined && bi * M + state.kyoku >= total);
      const inExtension = windsN !== undefined && windsN > 0 && bi >= windsN;
      const ext = end.extension || {};
      const top = Math.max(...scores);
      const dealerTop = scores[oya] === top && scores.filter(x => x === top).length === 1;
      const reached = !ext.enabled || top >= (ext.until_points || 0);
      const mh = end.max_honba;
      if (mh !== null && mh !== undefined && honba > mh) return [null, "本場の上限"];
      if (length === "one") return [null, "1 局"];
      if (inExtension && reached && !(renchan && ext.renchan_first)) return [null, "延長：規定の点に届いた"];   // renchan_first：親の連荘を優先
      if (lastRegular || inExtension) {
        if (renchan) {
          const ay = end.agari_yame || {}, ty = end.tenpai_yame || {};
          // forced＝トップなら必ず止める。forced でなければ choose に聞く（既定は止める）。
          // others_may_continue＝トップでない親も、止めるか続けるかを選べる（既定は続ける）
          const ask = (kind, dflt) => (this._choose === null ? dflt : Boolean(this._choose(kind, oya, scores.slice())));
          if (info.kind === "win" && ay.enabled && reached) {
            if (dealerTop && (ay.forced || ask("agari_yame", true))) return [null, "和了止め"];
            const middle = scores.some(x => x > scores[oya]) && scores.some(x => x < scores[oya]);   // トップでもラスでもない
            if (!dealerTop && middle && ay.others_may_continue && ask("agari_yame_not_top", false)) return [null, "和了止め"];
          }
          if (info.kind === "draw" && ty.enabled && dealerTop && reached && (info.dealer_tenpai || ty.require_tenpai === false)) {
            if (ty.forced || ask("tenpai_yame", true)) return [null, "聴牌止め"];
          }
        } else {
          if (lastRegular && reached) return [null, "規定の局数"];
          if (inExtension && state.kyoku === M) {
            const playedExt = bi - windsN + 1;
            if (ext.once || playedExt * M >= (ext.max_rounds === undefined ? M : ext.max_rounds) || bi >= 3) return [null, "延長の上限"];
          }
          if (lastRegular && !ext.enabled) return [null, "規定の局数"];
        }
      }
      if (fl.next_dealer === "winner") {
        // 和了した人が次の親（場と局は進まない）。親が和了すれば本場が増え、子が和了すれば 0 に戻る。流局は上の連荘の決まりどおり
        if (total !== null && total !== undefined && (k || 0) + 1 >= total) return [null, "規定の局数"];
        if (info.kind === "win") {
          const no = info.winners[0];
          return [{ bakaze: state.bakaze, kyoku: state.kyoku, honba: no === oya ? state.honba + 1 : 0, kyotaku, oya: no, scores }, null];
        }
        // 流局：本場は「親が続けて和了した回数」なので増やさない。親が替わるなら 0 に戻す
        return [{ bakaze: state.bakaze, kyoku: state.kyoku, honba: renchan ? state.honba : 0, kyotaku, oya: renchan ? oya : (oya + 1) % M, scores }, null];
      }
      let nb = state.bakaze, nk = state.kyoku, no = oya;
      if (!renchan) {
        no = (oya + 1) % M;
        nk = state.kyoku + 1;
        if (nk > M) { nk = 1; nb = WIND_ORDER[(bi + 1) % 4]; }
      }
      return [{ bakaze: nb, kyoku: nk, honba, kyotaku, oya: no, scores }, null];
    }
  }

  /* 出来上がった対局を、同じ山・同じ判断で進行役に進め直させる（確認用）。throughPlayers＝判断を打ち手の窓口ごし（合法手と照合）に求める。 */
  async function replayWithDealer(rec, rs, ts, walls, throughPlayers) {
    const M = normalize(rs).players;
    const rounds = rec.rounds;
    let d;
    const common = { playerInfo: deepCopy(rec.players), source: deepCopy(rec.source), parent: deepCopy(rec.parent === undefined ? null : rec.parent) };
    if (throughPlayers) {
      const players = {};
      for (let s = 0; s < M; s++) players[s] = msg => actualAction(rec, msg.round, msg.at, msg.seat, msg.phase) || { type: "pass" };
      d = new Dealer(rs, ts, Object.assign({ players, checkLegal: true }, common));
    } else {
      d = new Dealer(rs, ts, Object.assign({ decide: (seat, phase, at) => actualAction(rec, d.rc.rec.rounds.length - 1, at, seat, phase), checkLegal: false }, common));
    }
    const push0 = d.rc.push.bind(d.rc);
    const sync = () => {
      const cur = d.rc.rec.rounds[d.rc.rec.rounds.length - 1];
      const src = cur.index < rounds.length ? rounds[cur.index].events : [];
      while (cur.events.length < src.length && src[cur.events.length].t === "abort" && src[cur.events.length].resume) push0(deepCopy(src[cur.events.length]));
    };
    d.rc.push = ev => { sync(); push0(ev); sync(); };
    const wallOfRound = (k, state) => {
      if (k >= rounds.length) throw new ValidationError(`進行役が ${k + 1} 局目に進んだが、記録は ${rounds.length} 局で終わっている（次の局 ${JSON.stringify(state)}）`);
      return walls[rounds[k].wall.id];
    };
    const hasDice = "dice" in rounds[0].state;
    await d.play(wallOfRound, { dice: hasDice ? k => rounds[k].state.dice : null, top: extraTop(rec) });
    return d;
  }

  /* 2 つの対局の進行と結果を比べる。同じなら null、違えば最初の違いの文。並び順だけの違い（和了の手牌・副露・役）と役満の符は見ない。 */
  function differences(a, b, mergeDora) {
    const nw = w => {
      w = Object.assign({}, w);
      w.melds = (w.melds || []).slice().sort((x, y) => (JSON.stringify(x.tiles) < JSON.stringify(y.tiles) ? -1 : 1));
      w.hand = numSort(w.hand);
      w.yaku = yakuCounter(w.yaku, mergeDora);
      if (w.yakuman) w.fu = null;
      return w;
    };
    const n = Math.min(a.rounds.length, b.rounds.length);
    for (let k = 0; k < n; k++) {
      const ra = a.rounds[k], rb = b.rounds[k];
      if (!eq(ra.state, rb.state)) return `round ${k} の始まり（state）が違う：${JSON.stringify(ra.state)} ／ ${JSON.stringify(rb.state)}`;
      if (!eq(ra.events, rb.events)) {
        let i = 0;
        while (i < ra.events.length && i < rb.events.length && eq(ra.events[i], rb.events[i])) i++;
        return `round ${k} の出来事 ${i} 番目が違う：${JSON.stringify(ra.events[i])} ／ ${JSON.stringify(rb.events[i])}`;
      }
      const x = ra.result || {}, y = rb.result || {};
      const wa = (x.wins || []).map(nw), wb = (y.wins || []).map(nw);
      if (wa.length !== wb.length) return `round ${k} の和了の数が違う：${wa.length} ／ ${wb.length}`;
      for (let j = 0; j < wa.length; j++) {
        const keys = [...new Set(Object.keys(wa[j]).concat(Object.keys(wb[j])))].sort();
        for (const key of keys) if (!eq(wa[j][key], wb[j][key])) return `round ${k} の和了（seat ${wa[j].who}）の ${key} が違う：${JSON.stringify(wa[j][key])} ／ ${JSON.stringify(wb[j][key])}`;
      }
      if (!eq(x.draw === undefined ? null : x.draw, y.draw === undefined ? null : y.draw)) return `round ${k} の流局が違う：${JSON.stringify(x.draw)} ／ ${JSON.stringify(y.draw)}`;
      if (!eq(x.scores, y.scores)) return `round ${k} の結果の持ち点が違う：${JSON.stringify(x.scores)} ／ ${JSON.stringify(y.scores)}`;
    }
    if (a.rounds.length !== b.rounds.length) return `局の数が違う：${a.rounds.length} ／ ${b.rounds.length}`;
    for (const key of ["final", "end"]) if (!eq(a[key], b[key])) return `${key} が違う：${JSON.stringify(a[key])} ／ ${JSON.stringify(b[key])}`;
    return null;
  }

  // ---- 同梱の打ち手（bots.py と同じ打ち方。進行役の players に渡す関数） ----
  const bots = {
    /* 何もしない：ツモ切り、見送り */
    tsumogiri(msg) { return defaultAction(msg.obs, msg.legal, msg.phase); },
    /* 和了れるなら和了、立直できるなら立直、打牌は孤立した牌から。鳴かない（make(ts) で作る） */
    simple(ts) {
      const isolation = (kind, kinds) => {
        const same = kinds.filter(k => k === kind).length - 1;
        if (kind.length !== 2) return same * 4 + 1;
        const n = Number(kind[0]), s = kind[1];
        const cnt = d => (n + d >= 1 && n + d <= 9 ? kinds.filter(k => k === (n + d) + s).length : 0);
        return same * 4 + (cnt(-1) + cnt(1)) * 2 + cnt(-2) + cnt(2) + (n >= 2 && n <= 8 ? 2 : 1);
      };
      return msg => {
        const acts = msg.legal;
        const win = acts.find(a => a.type === "tsumo" || a.type === "ron");
        if (win) return win;
        const r = acts.find(a => a.type === "riichi");
        if (r) return r;
        const ds = acts.filter(a => a.type === "discard");
        if (ds.length) {
          const kinds = ds.map(a => ts.tiles[a.tile].kind);
          let best = null, bestV = null;
          for (let i = ds.length - 1; i >= 0; i--) { const v = isolation(kinds[i], kinds); if (bestV === null || v < bestV) { best = ds[i]; bestV = v; } }
          return best;
        }
        return { type: "pass" };
      };
    },
  };

  const dealerMod = { Dealer, unsupported, defaultAction, replayWithDealer, differences, bots };

  // ==== 評価（evaluate.py）：まとめて付ける／行動が届くたびに付ける ================================
  const ANN_FORMAT = "nmahjong-annotation", ANN_VERSION = "1.0";
  const EVALUATORS = ["nm-waits"];
  function annotationId(ann) { const o = {}; for (const k of Object.keys(ann)) if (k !== "id") o[k] = ann[k]; return NM.sha256Id(o); }
  function annotationFilename(ann) { return `${NM.idHex64(ann.record.id)}_${ann.evaluator.name}.annotation.json`; }
  function evaluatorMeta(evaluator, runAt) {
    const ev = { name: "nm-waits", version: "0.1", visibility: "actor",
      metrics: [{ name: "waits", scope: "candidate", kind: "count", higher_is_better: true, primary: true, unit: "種" },
        { name: "remaining", scope: "point", kind: "count", unit: "枚" }],
      params: { verdict: { o: 0, d: 1 } } };
    if (runAt) ev.run_at = runAt;
    return ev;
  }

  /* events[at] の判断点の評価。戻り値：point／null（評価の対象でない）／false（まだ決まっていない：続きの出来事が要る）。 */
  function pointAt(rec, rnd, at, rs, ts, walls, norm, seats) {
    const N = norm.hand_size;
    const evs = rnd.events;
    const e = evs[at];
    if (e.t !== "draw") return null;
    const seat = e.who;
    if (seats && seats.length && !seats.includes(seat)) return null;
    const nxt = evs.slice(at + 1).filter(x => x.t !== "dora" && x.t !== "abort");
    if (!nxt.length) return false;
    if (nxt[0].t === "riichi" && nxt.length < 2) return false;
    const a0 = actualAction(rec, rnd.index, at, seat, "A");
    if (!a0 || a0.type !== "pass") return null;
    const actual = actualAction(rec, rnd.index, at, seat, "B");
    if (!actual || actual.type !== "discard") return null;
    const obs = observe(rec, rnd.index, at, seat, rs, ts, walls);
    const legal = legalActions(rs, ts, obs, "B");
    if (!legal.length) return null;
    const melds = obs.melds[seat].length;
    const cands = legal.map(a => {
      const rest = obs.hand.slice();
      rest.splice(rest.indexOf(a.tile), 1);
      const w = norm.game_rules.agari_form === "standard" ? waits(ts, rest, melds, N).size : 0;
      return { type: "discard", tile: a.tile, values: { waits: w } };
    });
    const vals = cands.map(c => c.values.waits);
    const best = vals.indexOf(Math.max(...vals));
    const ai = cands.findIndex(c => actionKey(c) === actionKey(actual));
    const loss = vals[best] - vals[ai];
    const verdict = loss <= 0 ? "o" : loss <= 1 ? "d" : "x";
    return { round: rnd.index, at, phase: "B", actor: seat, actual, candidates: cands, estimates: { remaining: obs.remaining }, best, loss, verdict, note: null };
  }

  /* 出来上がった対局に、まとめて評価を付ける。 */
  function annotate(rec, rs, ts, walls, opt) {
    opt = opt || {};
    const evaluator = opt.evaluator || "nm-waits";
    if (!EVALUATORS.includes(evaluator)) throw new Error(`評価器 ${evaluator} は同梱していない`);
    const norm = normalize(rs);
    const points = [];
    for (const rnd of rec.rounds) for (let at = 0; at < rnd.events.length; at++) {
      const p = pointAt(rec, rnd, at, rs, ts, walls, norm, opt.seats);
      if (p) points.push(p);
    }
    const ann = { format: ANN_FORMAT, version: ANN_VERSION, record: { id: rec.id }, evaluator: evaluatorMeta(evaluator, opt.runAt), points };
    ann.id = annotationId(ann);
    return ann;
  }

  /* 行動が届くたびに評価を付ける。記録係につなぐ（attach）か、出来事を積むたびに update(rec, walls) を呼ぶ。
     opt.onPoint(point)：評価が 1 つ付くたびに呼ばれる。まとめて付けた評価（annotate）と同じ結果になる。 */
  class LiveAnnotator {
    constructor(rs, ts, opt) {
      opt = opt || {};
      this.rs = rs; this.ts = ts;
      this.evaluator = opt.evaluator || "nm-waits";
      if (!EVALUATORS.includes(this.evaluator)) throw new Error(`評価器 ${this.evaluator} は同梱していない`);
      this.seats = opt.seats || null; this.runAt = opt.runAt || null; this.onPoint = opt.onPoint || null;
      this.norm = normalize(rs);
      this.points = [];
      this._round = 0; this._at = 0; this._walls = null;
    }
    attach(recorder) {
      this._walls = recorder.walls;
      recorder.listeners.push(rec => this.update(rec, recorder.walls));
      return this;
    }
    update(rec, walls) {
      const fresh = [];
      const rounds = rec.rounds;
      while (this._round < rounds.length) {
        const rnd = rounds[this._round];
        const evs = rnd.events;
        const closed = rnd.result !== undefined && rnd.result !== null;
        while (this._at < evs.length) {
          const p = pointAt(rec, rnd, this._at, this.rs, this.ts, walls, this.norm, this.seats);
          if (p === false && !closed) break;
          if (p) fresh.push(p);
          this._at += 1;
        }
        if (this._at < evs.length || !closed) break;
        this._round += 1;
        this._at = 0;
      }
      this.points = this.points.concat(fresh);
      if (this.onPoint) for (const p of fresh) this.onPoint(p);
      return fresh;
    }
    finish(rec, walls) {
      this.update(rec, walls || this._walls);
      const ann = { format: ANN_FORMAT, version: ANN_VERSION, record: { id: rec.id }, evaluator: evaluatorMeta(this.evaluator, this.runAt), points: this.points };
      ann.id = annotationId(ann);
      return ann;
    }
  }

  /* 確認用：対局を出来事 1 つずつ記録係に流し込みながら評価を付ける。 */
  function liveReplay(rec, rs, ts, walls, onPoint) {
    const live = new LiveAnnotator(rs, ts, { onPoint });
    const r = replayRecord(rec, rs, ts, walls, false, cur => live.update(cur, walls));
    return live.finish(r.rec, walls);
  }

  const evaluateMod = { annotate, LiveAnnotator, liveReplay, pointAt, annotationId, annotationFilename };

  // ==== 対戦場（arena.py）：打ち手同士を何対局も回して成績表を出す ================================
  function eloUpdate(rating, names, rk, k) {
    k = k || 16;
    const M = names.length;
    const delta = {};
    for (const n of names) delta[n] = 0;
    for (let i = 0; i < M; i++) for (let j = i + 1; j < M; j++) {
      const a = names[i], b = names[j];
      if (a === b) continue;
      const ea = 1 / (1 + Math.pow(10, (rating[b] - rating[a]) / 400));
      const sa = rk[i] < rk[j] ? 1 : rk[i] > rk[j] ? 0 : 0.5;
      delta[a] += k / (M - 1) * (sa - ea);
      delta[b] -= k / (M - 1) * (sa - ea);
    }
    for (const n of Object.keys(delta)) rating[n] += delta[n];
  }
  function combinations(arr, m) {
    const out = [];
    const rec2 = (start, acc) => {
      if (acc.length === m) { out.push(acc.slice()); return; }
      for (let i = start; i < arr.length; i++) { acc.push(arr[i]); rec2(i + 1, acc); acc.pop(); }
    };
    rec2(0, []);
    return out;
  }
  const pyRound = (x, n) => { const f = Math.pow(10, n); return Math.round(x * f) / f; };

  /* entrants：名前 → 打ち手を作る関数（対局ごとに呼ぶ。戻り値は進行役の打ち手＝関数）。
     opt：{games, seed, mirror, strict, allowUnsupported, onGame(rec, walls, names)}。戻り値は成績表つきの結果。 */
  async function arenaRun(rs, ts, entrants, opt) {
    opt = opt || {};
    const games = opt.games === undefined ? 10 : opt.games, seed = opt.seed === undefined ? "arena" : opt.seed;
    const mirror = opt.mirror === undefined ? true : opt.mirror;
    const M = normalize(rs).players;
    const names = Object.keys(entrants);
    if (names.length < M) throw new Error(`出場者が ${M} 人に足りない（同じ打ち手を別の名前で並べてよい）`);
    const combos = combinations(names, M);
    const stat = {}, rating = {};
    for (const n of names) {
      stat[n] = { games: 0, rank_sum: 0, ranks: new Array(M).fill(0), score_sum: 0, settled_sum: 0, rounds: 0, wins: 0, deal_ins: 0, riichi: 0, faults: 0 };
      rating[n] = 1500;
    }
    let totalGames = 0, totalRounds = 0;
    for (let g = 0; g < games; g++) {
      const base = combos[g % combos.length];
      for (let rot = 0; rot < (mirror ? M : 1); rot++) {
        const sh = mirror ? rot : g % M;
        const seats = base.slice(sh).concat(base.slice(0, sh));
        const players = {};
        for (let s = 0; s < M; s++) players[s] = entrants[seats[s]]();
        const d = new Dealer(rs, ts, { players, strict: Boolean(opt.strict), allowUnsupported: Boolean(opt.allowUnsupported),
          playerInfo: range(M).map(s => ({ seat: s, name: seats[s], external: [] })) });
        const rec = await d.play(k => NM.wall.build(ts, `${seed}-${g}-${k}`));
        totalGames += 1;
        totalRounds += rec.rounds.length;
        const fin = rec.final;
        for (let s = 0; s < M; s++) {
          const st = stat[seats[s]];
          st.games += 1; st.rank_sum += fin.rank[s]; st.ranks[fin.rank[s] - 1] += 1;
          st.score_sum += fin.scores[s]; st.settled_sum += fin.settled[s]; st.rounds += rec.rounds.length;
        }
        for (const rnd of rec.rounds) {
          for (const w of rnd.result.wins) { stat[seats[w.who]].wins += 1; if (w.from !== w.who) stat[seats[w.from]].deal_ins += 1; }
          for (const e of rnd.events) if (e.t === "riichi") stat[seats[e.who]].riichi += 1;
        }
        for (const f of d.faults) stat[seats[Number(f.split("seat ")[1].split(" ")[0])]].faults += 1;
        eloUpdate(rating, seats, fin.rank);
        if (opt.onGame) await opt.onGame(rec, d.walls, seats);
      }
    }
    const table = names.map(n => {
      const st = stat[n], gm = Math.max(st.games, 1), rd = Math.max(st.rounds, 1);
      return { name: n, games: st.games, avg_rank: pyRound(st.rank_sum / gm, 3), ranks: st.ranks, avg_score: pyRound(st.score_sum / gm, 1),
        avg_settled: pyRound(st.settled_sum / gm, 2), win_rate: pyRound(st.wins / rd, 4), deal_in_rate: pyRound(st.deal_ins / rd, 4),
        riichi_rate: pyRound(st.riichi / rd, 4), rating: pyRound(rating[n], 1), faults: st.faults };
    });
    table.sort((a, b) => (a.avg_rank - b.avg_rank) || (b.avg_settled - a.avg_settled) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    return { ruleset: { name: rs.name === undefined ? null : rs.name, id: rs.id === undefined ? null : rs.id }, seed, mirror, games: totalGames, rounds: totalRounds, table };
  }

  const arenaMod = { run: arenaRun };

  return { scoring, observe: observeMod, judge: judgeMod, record: recordMod, recorder: recorderMod, dealer: dealerMod, evaluate: evaluateMod, arena: arenaMod,
    normalize, ValidationError };
});
