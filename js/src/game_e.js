
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
