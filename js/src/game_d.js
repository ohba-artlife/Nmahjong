
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
