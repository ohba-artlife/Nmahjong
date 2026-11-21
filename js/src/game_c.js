
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
