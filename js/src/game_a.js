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
