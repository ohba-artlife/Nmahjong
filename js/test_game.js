/* 試験 T14：JS 版の 4 層・5 層（nmahjong-game.js）が Python 実装と同じ結果になることを確かめる。node test_game.js
   試験データは tools/gen_js_testdata.py が Python 実装から作る（js/testdata）。 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const NM = require("./nmahjong.js");
const B = require("./bundled.js");
const G = require("./nmahjong-game.js");

const games = fs.readFileSync(path.join(__dirname, "testdata", "games.jsonl"), "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l));
const selfplay = JSON.parse(fs.readFileSync(path.join(__dirname, "testdata", "selfplay.json"), "utf8"));
const canon = v => NM.canonicalString(JSON.parse(JSON.stringify(v, (k, x) => (x instanceof Set ? [...x].sort() : x))));
const same = (a, b, msg) => assert.strictEqual(canon(a), canon(b), msg);
const wm = d => { const o = {}; for (const w of d.walls) o[w.id] = w; return o; };
const find = name => { const rs = B.rulesets.find(x => x.name === name); return [rs, B.tilesets.find(x => x.id === rs.tileset.id)]; };

let n = 0;
async function t(name, fn) { const c = await fn(); n++; console.log("ok", name + (c ? `（${c}）` : "")); }

(async () => {
  await t("T14-1 点数と精算：対局の検証（点数表・順位・精算の再計算を含む）が Python と同じ注意を返す", () => {
    for (const d of games) same(G.record.validate(d.rec, d.rso, d.tso, wm(d)), d.warns, d.rs);
    const sc = G.normalize(find("tenhou-4p-hanchan-red")[0]).game_rules.scoring;
    assert.deepStrictEqual(G.scoring.totalPoints(30, 4, 0, false, false, 4, sc), [7700, [7700]]);
    assert.deepStrictEqual(G.scoring.totalPoints(30, 4, 0, true, true, 4, sc), [11700, [3900, 3900, 3900]]);
    assert.deepStrictEqual(G.scoring.totalPoints(20, 2, 0, false, true, 4, sc), [1500, [700, 400, 400]]);
    assert.deepStrictEqual(G.scoring.totalPoints(0, 0, 1, false, false, 4, sc), [32000, [32000]]);
    return `対局 ${games.length}`;
  });

  await t("T14-2 局面・合法手・実際の行動が Python と同じ", () => {
    let c = 0;
    for (const d of games) for (const [ri, at, seat, ph, obs, legal, actual] of d.legal) {
      same(G.observe.observe(d.rec, ri, at, seat, d.rso, d.tso, wm(d)), obs, `${d.rs} r${ri} at${at} s${seat}`);
      same(G.observe.legalActions(d.rso, d.tso, obs, ph), legal, `${d.rs} r${ri} at${at} s${seat} ${ph}`);
      same(G.observe.actualAction(d.rec, ri, at, seat, ph), actual);
      c++;
    }
    return `判断点 ${c}`;
  });

  await t("T14-3 和了の状況・役と符が Python と同じ", () => {
    let c = 0;
    for (const d of games) for (const [ri, at, ctx, res] of d.judged) {
      same(G.judge.winContext(d.rec, ri, at, d.rso, d.tso, wm(d)), ctx, `${d.rs} r${ri}`);
      same(G.judge.judge(d.rso, d.tso, ctx), res, `${d.rs} r${ri}`);
      const win = d.rec.rounds[ri].result.wins.find(w => w.who === ctx.who);
      assert.strictEqual(G.judge.sameAsRecorded(res, win, false), null);
      c++;
    }
    return `和了 ${c}`;
  });

  await t("T14-4 記録係：出来事を 1 つずつ流し込むと同じ id。壊した対局・打てない手を断る", () => {
    for (const d of games) assert.strictEqual(G.recorder.replayRecord(d.rec, d.rso, d.tso, wm(d)).rec.id, d.rec.id, d.rs);
    const d = games[0];
    const bad = JSON.parse(JSON.stringify(d.rec));
    bad.rounds[0].result.scores[0] += 100;
    assert.throws(() => G.record.validate(bad, d.rso, d.tso, wm(d)), /id が内容のハッシュと一致しない/);
    const r = new G.recorder.Recorder(d.rso, d.tso);
    const rnd = d.rec.rounds[0];
    const cur = r.startRound(rnd.state, wm(d)[rnd.wall.id]);
    const first = rnd.events[cur.events.length];
    assert.throws(() => r.push(Object.assign({}, first, { tile: (first.tile + 1) % d.tso.tiles.length })), /牌山の次の牌/);
    r.push(first);
    assert.throws(() => r.push({ t: "discard", who: first.who, tile: -1 }), G.ValidationError);
    assert.throws(() => r.push({ t: "draw", who: first.who, tile: 0 }), /ツモが 2 回/);
  });

  await t("T14-4b 槍槓も合法手と照合する。暗槓の牌へのロンは、認めるルールの国士無双だけ", () => {
    const d = games.find(x => x.rs === "jantama-4p");
    const rnd = d.rec.rounds[0], kan = rnd.events[3], win = rnd.events[4];
    assert.deepStrictEqual([kan.t, kan.kind, win.t, win.who, win.from], ["kan", "ankan", "win", 1, 0]);
    const r0 = G.recorder.replayRecord(d.rec, d.rso, d.tso, wm(d));
    assert.deepStrictEqual(r0.warnings, []);
    const obs = G.observe.observe(d.rec, 0, 3, 1, d.rso, d.tso, wm(d));
    const jpml = G.normalize(d.rso), tenhou = G.normalize(find("tenhou-4p-hanchan-red")[0]);
    assert.strictEqual(G.observe.canRob(jpml, d.tso, obs, "ankan", win.tile), true);
    assert.strictEqual(G.observe.canRob(tenhou, d.tso, obs, "ankan", win.tile), false);     // ルールが認めていない
    assert.strictEqual(G.observe.canRob(tenhou, d.tso, obs, "kakan", win.tile), true);      // 加槓の牌ならできる
    assert.strictEqual(G.observe.canRob(jpml, d.tso, obs, "minkan", win.tile), false);
    const other = Object.assign({}, obs, { seat: 2, hand: G.observe.observe(d.rec, 0, 3, 2, d.rso, d.tso, wm(d)).hand });
    assert.strictEqual(G.observe.canRob(jpml, d.tso, other, "ankan", win.tile), false);     // 国士無双でない席
    // 記録係：認めないルールで同じ出来事を積むと、ロンを断る
    const no = JSON.parse(JSON.stringify(d.rso));
    no.game_rules.flow.kokushi_ankan_chankan = false;
    const r = new G.recorder.Recorder(no, d.tso);
    const cur = r.startRound(rnd.state, wm(d)[rnd.wall.id], rnd.events[1].tile);
    for (const e of rnd.events.slice(cur.events.length, 4)) r.push(e);
    assert.throws(() => r.push(win), /槍槓/);
  });

  await t("T14-5 進行役：同じ山・同じ判断で進め直すと元と同じ（直接／合法手と照合しながら）", async () => {
    let c = 0;
    for (const d of games) {
      if (d.rec.parent) continue;
      for (const through of [false, true]) {
        const dl = await G.dealer.replayWithDealer(d.rec, d.rso, d.tso, wm(d), through);
        assert.strictEqual(G.dealer.differences(dl.rc.rec, d.rec, false), null, d.rs);
      }
      c++;
    }
    return `対局 ${c}`;
  });

  await t("T14-6 進行役＋同梱の打ち手：Python の進行役と同じ種で同じ対局（同じ id）になる。1・4・7・10・13 枚、四麻、三麻、東天紅、祝儀のある店", async () => {
    for (const c of selfplay) {
      const [rs, ts] = find(c.rs);
      const players = {};
      for (let s = 0; s < rs.players; s++) players[s] = (c.bot === "simple" || (c.bot === "mix" && s % 2 === 0)) ? G.dealer.bots.simple(ts) : G.dealer.bots.tsumogiri;
      const d = new G.dealer.Dealer(rs, ts, { players });
      const rec = await d.play(k => NM.wall.build(ts, `${c.seed}-${k}`));
      assert.strictEqual(rec.id, c.id, `${c.rs} ${c.bot}`);
      assert.strictEqual(d.log[d.log.length - 1], c.end);
      assert.deepStrictEqual(G.record.validate(rec, rs, ts, d.walls), []);
    }
    return `対局 ${selfplay.length}`;
  });

  await t("T14-7 進行役：壊れた打ち手・あとから答える打ち手・従えない設定", async () => {
    const [rs, ts] = find("nm-2p-4-mps");
    const walls = k => NM.wall.build(ts, `bad-${k}`);
    const broken = () => ({ type: "pon" });
    await assert.rejects(() => new G.dealer.Dealer(rs, ts, { players: { 0: broken, 1: G.dealer.bots.simple(ts) } }).play(walls), G.ValidationError);
    const d = new G.dealer.Dealer(rs, ts, { players: { 0: broken, 1: G.dealer.bots.simple(ts) }, strict: false });
    const rec = await d.play(walls);
    assert.ok(d.faults.length > 0);
    assert.deepStrictEqual(G.record.validate(rec, rs, ts, d.walls), []);
    const slow = msg => new Promise(res => setTimeout(() => res(G.dealer.bots.tsumogiri(msg)), 0));      // 人の操作のように、あとから答える
    const d2 = new G.dealer.Dealer(rs, ts, { players: { 0: slow, 1: slow } });
    const d3 = new G.dealer.Dealer(rs, ts, { players: { 0: G.dealer.bots.tsumogiri, 1: G.dealer.bots.tsumogiri } });
    assert.strictEqual((await d2.play(walls)).id, (await d3.play(walls)).id);
    for (const r of B.rulesets) assert.deepStrictEqual(G.dealer.unsupported(r), [], r.name);        // 同梱ルールには、従えない設定はもう無い
    const [t3, wts] = find("tenhou-3p");
    const w = JSON.parse(JSON.stringify(t3));
    w.game_rules = Object.assign({}, w.game_rules, { flow: Object.assign({}, (w.game_rules || {}).flow, { wareme: true }) });   // 三人打ちのわれめ
    assert.ok(G.dealer.unsupported(w).some(x => x.includes("wareme")));
    assert.throws(() => new G.dealer.Dealer(w, wts, {}), /まだ従えない設定/);
    new G.dealer.Dealer(w, wts, { allowUnsupported: true });
    assert.deepStrictEqual(G.dealer.unsupported(find("tenhou-4p-hanchan-red")[0]), []);
  });

  await t("T14-8 評価：まとめて付けた評価・行動が届くたびに付けた評価が Python と同じ id", () => {
    let c = 0;
    for (const d of games) {
      const a = G.evaluate.annotate(d.rec, d.rso, d.tso, wm(d));
      assert.strictEqual(a.id, d.ann, d.rs);
      let early = 0;
      const l = G.evaluate.liveReplay(d.rec, d.rso, d.tso, wm(d), () => { early++; });
      assert.strictEqual(l.id, d.ann, d.rs);
      assert.strictEqual(early, a.points.length);
      c += a.points.length;
    }
    return `評価 ${c} 点`;
  });

  await t("T14-9 対戦場：同じ種なら同じ成績表。和了を狙う打ち手がツモ切りより上", async () => {
    const [rs, ts] = find("nm-2p-4-mps");
    const ent = { simple: () => G.dealer.bots.simple(ts), tsumogiri: () => G.dealer.bots.tsumogiri };
    const a = await G.arena.run(rs, ts, ent, { games: 3, seed: "t" });
    const b = await G.arena.run(rs, ts, ent, { games: 3, seed: "t" });
    assert.deepStrictEqual(a, b);
    assert.strictEqual(a.games, 6);
    assert.strictEqual(a.table[0].name, "simple");
    assert.ok(Math.abs(a.table.reduce((s, r) => s + r.avg_settled * r.games, 0)) < 1e-6);
    await assert.rejects(() => G.arena.run(rs, ts, { only: ent.simple }, { games: 1 }));
  });

  await t("T14-10 対局の終わり方と、聴牌の数え方が Python と同じ", () => {
    const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "testdata", "cases.json"), "utf8"));
    for (const c of cases.next_state) {
      const [rs, ts] = find(c.rs);
      const d = new G.dealer.Dealer(rs, ts, { decide: () => null, allowUnsupported: true });
      d._sticks = [];
      const [nxt, why] = d.nextState(c.state, { scores: c.state.scores }, c.info);
      assert.deepStrictEqual([nxt, why === undefined ? null : why], [c.next, c.why], `${c.rs} ${JSON.stringify(c.state)} ${JSON.stringify(c.info)}`);
    }
    const ts = find("tenhou-4p-hanchan-red")[1];
    for (const c of cases.tenpai_waits) {
      assert.deepStrictEqual([...G.observe.waits(ts, c.hand, c.melds, 13)].sort(), c.waits);
      assert.deepStrictEqual([...G.observe.tenpaiWaits(ts, c.hand, c.melds, 13)].sort(), c.tenpai_waits);
    }
    return `終わり方 ${cases.next_state.length}、聴牌 ${cases.tenpai_waits.length}`;
  });

  await t("T14-11 ルールで選べる払い方・終わり方（複数和了の供託、飛びの罰符、流し満貫の扱い、三人打ちのツモ、1000 点単位、止めるかの選択、われめ、オープン立直への放銃、足し算の点数、和了した人が次の親、祝儀、白ポッチ・逆ポッチ、完全先付け、小車輪・大車輪、子のツモの払いの表）が Python と同じ", async () => {
    const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "testdata", "cases.json"), "utf8"));
    for (const c of cases.rounds) {
      const ts = B.tilesets.find(x => x.id === c.rso.tileset.id);
      const answers = c.answers.slice();
      const d = new G.dealer.Dealer(c.rso, ts, { decide: () => answers.shift() });
      const [result, info] = await d.playRound(JSON.parse(JSON.stringify(c.state)), c.wall);
      assert.strictEqual(answers.length, 0);
      same(result, c.result, JSON.stringify(c.result));
      same(info, c.info);
      const [nxt, why] = d.nextState(c.state, result, info);
      same([nxt, why === undefined ? null : why], [c.next, c.why]);
    }
    for (const [mode, unit, fu, han, dealer, tsumo, want] of cases.points) {
      const sc = Object.assign({}, cases.sc3, { tsumo_loss: mode, round_to: unit });
      assert.deepStrictEqual(G.scoring.totalPoints(fu, han, 0, dealer, tsumo, 3, sc), want, `${mode} ${unit} ${fu} ${han} ${dealer} ${tsumo}`);
    }
    for (const c of cases.table_points) {                   // 子のツモの払いの表（関西の三人打ち）
      same(G.scoring.totalPoints(c.args[0], c.args[1], c.args[2], c.args[3], c.args[4], 3, c.sc), c.want, JSON.stringify(c.args));
    }
    for (const c of cases.additive) {                       // 足し算の点数（東天紅の式）
      const [each, parts] = G.scoring.additivePoints(c.args[0], c.args[1], c.args[2], c.args[3], c.args[4], c.sc);
      same([each, parts], c.want, JSON.stringify(c.args));
    }
    for (const c of cases.choices) {
      const [rs, ts] = find(c.rs);
      const d = new G.dealer.Dealer(rs, ts, { decide: () => null, choose: c.answer === null ? undefined : () => c.answer });
      d._sticks = [];
      const st = { bakaze: "S", kyoku: 4, honba: 0, kyotaku: 0, oya: 3, scores: c.scores };
      const info = c.kind === "win" ? { kind: "win", dealer_won: true, winners: [3] } : { kind: "draw", reason: "exhaustive", dealer_tenpai: true, any_tenpai: true, nagashi: [] };
      const [nxt, why] = d.nextState(st, { scores: c.scores }, info);
      assert.strictEqual(nxt === null ? why : "続く", c.why, JSON.stringify(c));
    }
    // 時間制限：その局を終えて終了
    const [rs, ts] = find("kenko");
    let now = 0;
    const d = new G.dealer.Dealer(rs, ts, { players: { 0: G.dealer.bots.tsumogiri, 1: G.dealer.bots.tsumogiri, 2: G.dealer.bots.tsumogiri, 3: G.dealer.bots.tsumogiri }, clock: () => now });
    const rec = await d.play((k) => { if (k === 2) now = 3600; return NM.wall.build(ts, `time-${k}`); });
    assert.deepStrictEqual([rec.rounds.length, rec.end, d.log[d.log.length - 1]], [3, "time_limit", "終了：時間制限"]);
    return `局 ${cases.rounds.length}、点数 ${cases.points.length}、選択 ${cases.choices.length}`;
  });

  console.log(`${n} tests OK`);
})().catch(e => { console.error(e); process.exit(1); });
