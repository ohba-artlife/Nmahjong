
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
