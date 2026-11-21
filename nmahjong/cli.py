"""nmahjong CLI（docs/install.md にコマンドの一覧）。"""
import argparse
import os
import sys

import json

from . import __version__, files, tileset as TS, wall as W, ruleset as R, record as REC
from .canon import ValidationError


def _tileset_arg(spec: str, search_dirs):
    """'mpsz' または 'mpsz@sha256:…' または ファイルパス。"""
    if os.path.isfile(spec):
        ts = files.load(spec)
        TS.validate(ts)
        return ts
    name, _, tid = spec.partition("@")
    return TS.find(name=name or None, id=tid or None, search_dirs=search_dirs)


def cmd_build(a):
    ts = _tileset_arg(a.tileset, a.search)
    if a.tags:
        # 実卓：タグ id の列（1 行 1 タグ、またはカンマ区切り）＋対応表 → observed
        if not a.tagmap:
            raise ValidationError("--tags には --tagmap が必要")
        tm = files.load(a.tagmap)
        with open(a.tags, encoding="utf-8") as f:
            txt = f.read()
        tags = [x.strip() for x in txt.replace(",", "\n").splitlines() if x.strip()]
        device = None
        if a.device:
            device = {"id": a.device}
            if a.device_at:
                device["at"] = a.device_at
        w = W.build_from_tags(ts, tm, tags, device=device, meta={"created_by": "nmahjong-cli"})
    else:
        if not a.seed:
            raise ValidationError("--seed（生成）か --tags（実卓）のどちらかが必要")
        w = W.build(ts, a.seed, meta={"created_at": a.seed, "created_by": "nmahjong-cli"})
    if a.out:
        print(files.save(w, a.out, W.filename(w)))
    else:
        sys.stdout.write(files.dumps(w, pretty=not a.compact))
    return 0


def cmd_validate(a):
    rc = 0
    for path in a.files:
        try:
            obj = files.load(path)
            kind = files.detect_format(obj)
            if kind == "tileset":
                warns = TS.validate(obj)
            elif kind == "wall":
                ts = None
                try:
                    ts = TS.find(id=obj["tileset"]["id"], search_dirs=a.search + [os.path.dirname(os.path.abspath(path))])
                except (ValidationError, KeyError, TypeError):
                    pass
                warns = W.validate(obj, ts)
                if ts is None:
                    warns = warns + ["牌表が見つからないため K と tileset.id は未照合"]
            elif kind == "ruleset":
                _, warns = R.validate(obj, search_dirs=a.search + [os.path.dirname(os.path.abspath(path))])
            elif kind == "record":
                dirs = a.search + [os.path.dirname(os.path.abspath(path))]
                walls = {}
                for d in dirs:
                    for fn in os.listdir(d):
                        if fn.endswith(".wall.json"):
                            try:
                                wobj = files.load(os.path.join(d, fn))
                                walls[wobj["id"]] = wobj
                            except Exception:
                                pass
                warns = REC.validate(obj, walls=walls, search_dirs=dirs)
            elif kind == "annotation":
                from . import annotation as AN
                dirs = a.search + [os.path.dirname(os.path.abspath(path))]
                rec, rs, ts, walls = _find_record(obj["record"]["id"], dirs) if isinstance(obj.get("record"), dict) else (None, None, None, None)
                warns = AN.validate(obj, rec, rs, ts, walls)
                if rec is None:
                    warns = warns + ["対局ファイルが見つからないため層またぎ（8〜10）は未照合"]
            else:
                raise ValidationError("format が nmahjong-* ではない")
            print(f"{path}: OK" + (" / 警告: " + "; ".join(warns) if warns else ""))
        except ValidationError as e:
            print(f"{path}: NG {e}")
            rc = 1
        except Exception as e:  # JSON 壊れ等
            print(f"{path}: NG 読み込み失敗 {type(e).__name__}: {e}")
            rc = 1
    return rc


def _find_record(rec_id: str, dirs):
    """dirs から record（id 一致）とその ruleset・tileset・walls を集める。"""
    rec = None
    walls = {}
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            fp = os.path.join(d, fn)
            try:
                if fn.endswith(".record.json") and rec is None:
                    o = files.load(fp)
                    if o.get("id") == rec_id:
                        rec = o
                elif fn.endswith(".wall.json"):
                    o = files.load(fp)
                    walls[o["id"]] = o
            except Exception:
                pass
    if rec is None:
        return None, None, None, None
    rs = R.find(id=rec["ruleset"]["id"], search_dirs=dirs)
    ts = TS.find(id=rs["tileset"]["id"], search_dirs=dirs)
    return rec, rs, ts, walls


def _load_record_ctx(path: str, search):
    rec = files.load(path)
    if files.detect_format(rec) != "record":
        raise ValidationError("record ファイルではない")
    dirs = search + [os.path.dirname(os.path.abspath(path))]
    _, rs, ts, walls = _find_record(rec["id"], dirs)
    if rs is None:
        rs = R.find(id=rec["ruleset"]["id"], search_dirs=dirs)
        ts = TS.find(id=rs["tileset"]["id"], search_dirs=dirs)
        walls = {}
        for d in dirs:
            for fn in os.listdir(d):
                if fn.endswith(".wall.json"):
                    try:
                        o = files.load(os.path.join(d, fn)); walls[o["id"]] = o
                    except Exception:
                        pass
    return rec, rs, ts, walls


def cmd_observe(a):
    from . import observe as O
    rec, rs, ts, walls = _load_record_ctx(a.record, a.search)
    obs = O.observe(rec, a.round, a.at, a.seat, rs, ts, walls, full=a.full)
    if a.names:
        lab = lambda t: TS.tile_label(ts, t)  # noqa: E731
        obs = dict(obs, hand=[lab(t) for t in obs["hand"]], discards=[[lab(t) for t in d] for d in obs["discards"]],
                   dora_indicators=[lab(t) for t in obs["dora_indicators"]],
                   melds=[[dict(m, tiles=[lab(t) for t in m["tiles"]]) for m in ms] for ms in obs["melds"]],
                   hands=[[lab(t) for t in h] for h in obs["hands"]] if "hands" in obs else None)
        obs = {k: v for k, v in obs.items() if v is not None}
    print(files.dumps(obs, pretty=True))
    return 0


def cmd_judge(a):
    """対局の和了を 1 つずつ判定し、記録の役・符・翻と比べる。違いがあれば終了コード 1。"""
    from . import judge as J
    rec, rs, ts, walls = _load_record_ctx(a.record, a.search)
    lab = lambda t: TS.tile_label(ts, t)  # noqa: E731
    n = bad = 0
    for rnd in rec["rounds"]:
        if a.round is not None and rnd["index"] != a.round:
            continue
        for w in (rnd.get("result") or {}).get("wins") or []:
            i = next(k for k, e in enumerate(rnd["events"]) if e["t"] == "win" and e["who"] == w["who"])
            ctx = J.win_context(rec, rnd["index"], i, rs, ts, walls)
            res = J.judge(rs, ts, ctx)
            diff = J.same_as_recorded(res, w, merge_dora=a.merge_dora)
            n += 1
            bad += diff is not None
            st = rnd["state"]
            hand = "".join(lab(t) for t in sorted(ctx["hand"]))
            melds = " ".join(m["kind"] + "(" + "".join(lab(t) for t in m["tiles"]) + ")" for m in ctx["melds"])
            print(f"round {rnd['index']} {st['bakaze']}{st['kyoku']} seat {w['who']} {'ツモ' if ctx['tsumo'] else 'ロン'} {lab(ctx['tile'])}  {hand} {melds}")
            if res.get("ok"):
                ys = " ".join(f"{R.VOCAB['yaku'].get(y['name']) or R.VOCAB['yakuman'].get(y['name'], y['name'])}{'（役満）' if 'yakuman' in y else y['han']}" for y in res["yaku"])
                print(f"   判定 {ys} ／ " + (f"役満 ×{res['yakuman']}" if res.get("yakuman") else f"{res['fu']} 符 {res['han']} 翻") + f" ／ 待ち {res['wait']}")
            print("   記録と同じ" if diff is None else f"   記録と違う：{diff}")
    print(f"和了 {n} / 記録と同じ {n - bad} / 違う {bad}", file=sys.stderr)
    return 1 if bad else 0


def cmd_play(a):
    """進行役に 1 対局を進めさせる。打ち手は同梱の bot（tsumogiri／simple）か、別プログラム（--player 席=コマンド）。"""
    import shlex
    from . import bots as B, dealer as D, gateway as GW
    rs = R.find(name=a.ruleset, search_dirs=a.search) if not os.path.isfile(a.ruleset) else files.load(a.ruleset)
    ts = TS.find(id=rs["tileset"]["id"], search_dirs=a.search)
    M = R.normalize(rs)["players"]
    players = {s: GW.FunctionPlayer(B.BOTS[a.bot], wants_events=False) for s in range(M)}
    for spec in a.player or []:
        seat, _, cmd = spec.partition("=")
        players[int(seat)] = GW.ProcessPlayer(shlex.split(cmd))
    d = D.Dealer(rs, ts, players=players, strict=not a.loose, allow_unsupported=a.allow_unsupported,
                 player_info=[{"seat": s, "name": (a.bot if isinstance(players[s], GW.FunctionPlayer) else "program"), "external": []} for s in range(M)])
    for u in d.unsupported:
        print(f"まだ従えない設定：{u}", file=sys.stderr)
    live = None
    if a.annotate:
        from . import evaluate as EV
        show = (lambda p: print(f"  評価 round {p['round']} seat {p['actor']} {TS.tile_label(ts, p['actual']['tile'])} 切り → {p['verdict']}（損 {p['loss']}）")) if a.verbose else None
        live = EV.LiveAnnotator(rs, ts, on_point=show).attach(d.rc)
    try:
        rec = d.play(lambda k, st: W.build(ts, f"{a.seed}-{k}"))
    finally:
        d.gw.close()
    for rd in rec["rounds"]:
        st, res = rd["state"], rd["result"]
        what = "／".join(f"seat {w['who']} 和了 {w['points']}" for w in res["wins"]) or f"流局（{res['draw']['reason']}）"
        print(f"{st['bakaze']}{st['kyoku']} {st['honba']} 本場 親 {st['oya']}  {what}  → {res['scores']}")
    print(f"{d.log[-1] if d.log else ''}  最終 {rec['final']['scores']} 順位 {rec['final']['rank']} 精算 {rec['final']['settled']}")
    if d.gw.faults:
        print(f"打ち手の応答を既定の行動に置き換えた回数 {len(d.gw.faults)}", file=sys.stderr)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        files.save(rec, a.out, REC.filename(rec, rs))
        for w in d.walls.values():
            files.save(w, a.out, W.filename(w))
        print(f"{a.out} に対局 1・牌山 {len(d.walls)} を書いた（id {rec['id']}）")
    if live is not None:
        from . import annotation as AN
        ann = live.finish(rec)
        per = [{v: sum(1 for p in ann["points"] if p["verdict"] == v and p["actor"] == s) for v in "odx"} for s in range(M)]
        print("評価（nm-waits。打牌ごとに付けた）：" + "  ".join(f"seat {s} ○{x['o']} △{x['d']} ×{x['x']}" for s, x in enumerate(per)))
        if a.out:
            files.save(ann, a.out, AN.filename(ann))
    return 0


def _entrant(spec: str):
    """'名前=simple'（同梱の打ち手）か '名前=コマンド'（別プログラム）。"""
    import shlex
    from . import bots as B, gateway as GW
    name, _, what = spec.partition("=")
    if not what:
        name, what = spec, spec
    if what in B.BOTS:
        return name, (lambda: GW.FunctionPlayer(B.BOTS[what], wants_events=False))
    return name, (lambda: GW.ProcessPlayer(shlex.split(what)))


def cmd_arena(a):
    """対戦場：打ち手同士を何対局も戦わせて集計する。"""
    from . import arena as AR
    rs = R.find(name=a.ruleset, search_dirs=a.search) if not os.path.isfile(a.ruleset) else files.load(a.ruleset)
    ts = TS.find(id=rs["tileset"]["id"], search_dirs=a.search)
    entrants = dict(_entrant(x) for x in a.entrant)
    if len(entrants) != len(a.entrant):
        raise ValidationError("出場者の名前が重なっている（名前=打ち手 の名前を変える）")

    def save(rec, walls, names):
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            files.save(rec, a.out, REC.filename(rec, rs))
            for w in walls.values():
                files.save(w, a.out, W.filename(w))
    res = AR.run(rs, ts, entrants, games=a.games, seed=a.seed, mirror=not a.no_mirror, strict=a.strict,
                 allow_unsupported=a.allow_unsupported, on_game=save)
    print(f"ルール {rs['name']}  対局 {res['games']}  局 {res['rounds']}  種 {res['seed']}" + ("" if res["mirror"] else "  席替えなし"))
    print(AR.format_table(res))
    if a.out:
        with open(os.path.join(a.out, "arena.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f"{a.out} に対局と arena.json を書いた")
    return 0


def cmd_legal(a):
    from . import observe as O, mjai as MJ
    rec, rs, ts, walls = _load_record_ctx(a.record, a.search)
    obs = O.observe(rec, a.round, a.at, a.seat, rs, ts, walls)
    acts = O.legal_actions(rs, ts, obs, a.phase)
    if a.mjai:
        print(files.dumps(MJ.request_action(obs, acts, ts, f"{a.round}-{a.at}-{a.seat}"), pretty=True))
        return 0
    for x in acts:
        parts = [x["type"]]
        if "kind" in x:
            parts.append(x["kind"])
        if "tile" in x:
            parts.append(f"{x['tile']}({TS.tile_label(ts, x['tile'])})")
        if "tiles" in x:
            parts.append(" ".join(f"{t}({TS.tile_label(ts, t)})" for t in x["tiles"]))
        if x.get("open"):
            parts.append("open")
        if "reason" in x:
            parts.append(x["reason"])
        print(" ".join(parts))
    actual = O.actual_action(rec, a.round, a.at, a.seat, a.phase)
    print(f"-- 実際: {actual}")
    return 0


def cmd_annotate(a):
    from . import evaluate as E, annotation as AN
    rec, rs, ts, walls = _load_record_ctx(a.record, a.search)
    ann = E.annotate(rec, rs, ts, walls, evaluator=a.evaluator)
    warns = AN.validate(ann, rec, rs, ts, walls)
    if a.out:
        print(files.save(ann, a.out, AN.filename(ann), pretty=False))
    else:
        print(files.dumps(ann, pretty=False))
    print(f"points={len(ann['points'])}" + (" / 警告: " + "; ".join(warns) if warns else ""), file=sys.stderr)
    return 0


def cmd_export(a):
    from .tenhou import json6 as J
    rec, rs, ts, walls = _load_record_ctx(a.record, a.search)
    print(files.dumps(J.export_json(rec, rs, ts, walls), pretty=False), end="")
    return 0


def cmd_mjai(a):
    from . import mjai as MJ
    rec, rs, ts, walls = _load_record_ctx(a.record, a.search)
    for ev in MJ.to_mjai(rec, rs, ts, walls, seat=a.seat):
        print(files.dumps(ev, pretty=False), end="")
    return 0


def cmd_show(a):
    obj = files.load(a.file)
    kind = files.detect_format(obj)
    style = "z" if a.z else "mjai"
    if kind == "tileset":
        print(f"tileset {obj['name']} K={len(obj['tiles'])} id={obj['id']}")
        for t in obj["tiles"]:
            print(f"{t['id']:4d} {TS.tile_label(obj, t['id'], style):6s} {t.get('mark','')} {t.get('name','')}".rstrip())
        return 0
    if kind == "wall":
        ts = TS.find(id=obj["tileset"]["id"], search_dirs=a.search + [os.path.dirname(os.path.abspath(a.file))])
        print(f"wall {obj['tileset']['name']} source={obj['source']} K={len(obj['order'])} id={obj['id']}")
        labels = [TS.tile_label(ts, i, style) for i in obj["order"]]
        for i in range(0, len(labels), 17):
            print(f"{i:4d}: " + " ".join(labels[i:i + 17]))
        return 0
    if kind == "ruleset":
        norm = R.normalize(obj)
        sys.stdout.write(files.dumps(norm))
        return 0
    if kind == "record":
        dirs = a.search + [os.path.dirname(os.path.abspath(a.file))]
        rs = R.find(id=obj["ruleset"]["id"], search_dirs=dirs)
        ts = TS.find(id=rs["tileset"]["id"], search_dirs=dirs)
        lab = lambda x: TS.tile_label(ts, x, style)
        print(f"record {obj['source'].get('from')} {obj['source'].get('ref') or ''} ruleset={rs['name']} rounds={len(obj['rounds'])} end={obj['end']}")
        for rd in obj["rounds"]:
            st = rd["state"]
            print(f"-- {st['bakaze']}{st['kyoku']} {st['honba']}本場 供託{st['kyotaku']} 親={st['oya']} {st['scores']}")
            line = []
            for e in rd["events"]:
                t = e["t"]
                if t == "draw": line.append(f"{e['who']}:{'+' if e.get('rinshan') else ''}{lab(e['tile'])}")
                elif t == "discard": line.append(f"{e['who']}:-{lab(e['tile'])}{'*' if e.get('riichi') else ''}")
                elif t in ("chi", "pon", "kan"): line.append(f"{e['who']}:{t}({''.join(lab(x) for x in e['tiles'])})")
                elif t == "dora": line.append(f"dora({lab(e['tile'])})")
                elif t == "win": line.append(f"WIN {e['who']}<-{e['from']} {lab(e['tile'])}")
                elif t == "draw_end": line.append(f"DRAW {e['reason']}")
            print("   " + " ".join(line))
            for w in rd["result"].get("wins", []):
                print(f"   和了 {w['who']} {w['fu']}符{w['han']}翻 {w['points']} {[y['name'] for y in w['yaku']]} deltas={w['deltas']}")
        print(f"final {obj.get('final')}")
        return 0
    print(f"show は {kind} に未対応")
    return 1


def cmd_import(a):
    from .tenhou import importer as I, json6 as J
    rc = 0
    for path in a.files:
        ref = os.path.basename(path).split(".")[0]
        try:
            if a.source == "tenhou-json":
                with open(path, encoding="utf-8") as f:
                    rec = J.import_json(f.read(), source_ref=ref)
                walls = []
            else:
                rec, walls = I.import_mjlog(path, source_ref=ref)
            rs = R.find(id=rec["ruleset"]["id"])
            ts = TS.find(id=rs["tileset"]["id"])
            warns = REC.validate(rec, rs, ts, {w["id"]: w for w in walls})
            if a.out:
                for w in walls:
                    files.save(w, a.out, W.filename(w), pretty=False)
                print(files.save(rec, a.out, REC.filename(rec, rs)))
            print(f"{path}: OK rounds={len(rec['rounds'])} walls={len(walls)}" + (" / 警告: " + "; ".join(warns) if warns else ""))
        except ValidationError as e:
            print(f"{path}: NG {e}")
            rc = 1
    return rc


def _parse_value(v: str):
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return v


def cmd_ruleset(a):
    if a.sub == "list":
        for rs in R.bundled():
            unk = len(rs.get("unknown", []))
            note = (rs.get("meta") or {}).get("note", "")
            print(f"{rs['name']:24s} M={rs['players']} N={rs['hand_size']:2d} {rs['tileset']['name']:9s} 欠落{unk:2d} {rs['id'][:19]}… {note[:60]}")
        return 0
    if a.sub == "show":
        rs = R.find(name=a.name.partition("@")[0], id=a.name.partition("@")[2] or None, search_dirs=a.search)
        sys.stdout.write(files.dumps(R.normalize(rs)))
        return 0
    if a.sub == "validate":
        return cmd_validate(argparse.Namespace(files=a.files, search=a.search))
    if a.sub == "diff":
        ra = _ruleset_arg(a.a, a.search); rb = _ruleset_arg(a.b, a.search)
        rows = R.diff(ra, rb)
        for k, va, vb in rows:
            print(f"{k}: {json.dumps(va, ensure_ascii=False)} → {json.dumps(vb, ensure_ascii=False)}")
        print(f"{len(rows)} 項目が違う")
        return 0
    if a.sub == "new":
        base = _ruleset_arg(a.from_, a.search) if a.from_ else None
        sets = {}
        for kv in a.set or []:
            k, _, v = kv.partition("=")
            if not k or not _:
                print(f"NG --set は key=value: {kv!r}", file=sys.stderr); return 1
            sets[k] = _parse_value(v)
        if a.tileset:
            sets["tileset"] = TS.ref(_tileset_arg(a.tileset, a.search))
        if base is None and "tileset" not in sets:
            print("NG --from が無いときは --tileset が必要", file=sys.stderr); return 1
        if base is None:
            for k, dv in (("players", 4), ("hand_size", 13), ("length", "east_south"), ("winds", ["E", "S", "W", "N"]), ("wall_rules", None)):
                sets.setdefault(k, dv)
            if sets["wall_rules"] is None:
                sets["wall_rules"] = {"deal": "N_each_then_1_to_dealer", "dead_wall": 14, "dora_indicator": [8], "ura_indicator": [9],
                                      "kan_dora": [6, 4, 2, 0], "kan_ura": [7, 5, 3, 1], "rinshan": [12, 13, 10, 11], "break": {"by": "dice"}}
        rs = R.new_from(base, a.name, sets)
        rs.pop("unknown", None)   # 新しく作ったものは「不明」を引き継がない
        rs["id"] = R.compute_id(rs)
        _, warns = R.validate(rs, search_dirs=a.search)
        if a.out:
            print(files.save(rs, a.out, R.filename(rs)))
        else:
            sys.stdout.write(files.dumps(rs))
        for w in warns:
            print("警告: " + w, file=sys.stderr)
        return 0
    return 1


def _ruleset_arg(spec: str, search_dirs):
    if os.path.isfile(spec):
        return files.load(spec)
    name, _, rid = spec.partition("@")
    return R.find(name=name or None, id=rid or None, search_dirs=search_dirs)


def cmd_tileset(a):
    if a.sub == "list":
        for key, kw in TS.bundled_definitions().items():
            ts = TS.build(**kw)
            marks = sorted({t["mark"] for t in ts["tiles"] if "mark" in t})
            print(f"{key:14s} name={ts['name']:8s} K={len(ts['tiles']):3d} marks={','.join(marks) or '-'} {ts['id']}")
        return 0
    if a.sub == "show":
        ts = TS.find(name=a.name.partition('@')[0], id=a.name.partition('@')[2] or None)
        sys.stdout.write(files.dumps(ts))
        return 0
    if a.sub == "new":
        colors = "".join(c for c in "mpsz" if c in a.colors)
        exclude = [k for k in (a.exclude or "").split(",") if k]
        marks = {}
        for spec in a.mark or []:
            kind, _, val = spec.partition("=")
            marks[kind] = [m for m in val.split(",") if m]
        ex_spec = [x for x in (a.extra or "").split(",") if x]
        extras = [x.partition("=")[0] for x in ex_spec]
        name = colors + (f"-x{len(set(exclude)) * 4}" if exclude else "") + (f"-e{len(extras)}" if extras else "")
        for k in list(marks) + exclude:
            if k not in TS.full_kinds(colors):
                raise ValidationError(f"牌種 {k} は選んだ色に無い")
        for k, v in marks.items():
            if len(v) > TS.COPIES:
                raise ValidationError(f"{k} の印は {TS.COPIES} 枚まで")
        base_n = sum(TS.COPIES for k in TS.full_kinds(colors) if k not in set(exclude))
        ex_marks = {base_n + i: x.partition("=")[2] for i, x in enumerate(ex_spec) if x.partition("=")[2]}
        if any(not n for n in extras):
            raise ValidationError("エクストラ牌の名前が空")
        ts = TS.build(name, exclude_kinds=exclude, mark_by_kind=marks or None, extras=extras, marks=ex_marks or None)
        TS.validate(ts)
        if a.out:
            print(files.save(ts, a.out, TS.filename(ts)))
        print(f"name={ts['name']} K={len(ts['tiles'])} {ts['id']}")
        return 0
    if a.sub == "export":
        for ts in TS.bundled():
            print(files.save(ts, a.out, TS.filename(ts)))
        return 0
    return 1


def main(argv=None):
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="nmahjong", description="N 枚麻雀のデータ形式 — 参照実装")
    p.add_argument("--version", action="version", version=f"nmahjong {__version__}")
    p.add_argument("--search", action="append", default=[], help="牌表などを探すフォルダ（複数可）")
    sp = p.add_subparsers(dest="cmd", required=True)

    b = sp.add_parser("build", help="牌山を生成（fy-sha256-v1）")
    b.add_argument("--tileset", required=True, help="名前 / 名前@id / ファイル")
    b.add_argument("--seed", help="種。秒まで入れた ISO 8601 日時（時差付き）を推奨")
    b.add_argument("--tags", help="実卓：卓が読んだタグ id の列のファイル（1 行 1 つ／カンマ区切り、消費順）")
    b.add_argument("--tagmap", help="実卓：タグ → 牌番号の対応表（nmahjong-tagmap）")
    b.add_argument("--device", help="実卓：卓の id（wall.device.id）")
    b.add_argument("--device-at", dest="device_at", help="実卓：読んだ時刻（ISO 8601）")
    b.add_argument("--out", help="書き出し先フォルダ（省略時は標準出力）")
    b.add_argument("--compact", action="store_true")
    b.set_defaults(fn=cmd_build)

    v = sp.add_parser("validate", help="ファイルを検証（format で種類を判定）")
    v.add_argument("files", nargs="+")
    v.set_defaults(fn=cmd_validate)

    s = sp.add_parser("show", help="番号を牌名にして表示")
    s.add_argument("file")
    s.add_argument("--z", action="store_true", help="1z〜7z・0m 表記")
    s.set_defaults(fn=cmd_show)

    t = sp.add_parser("tileset", help="同梱の牌表")
    tsub = t.add_subparsers(dest="sub", required=True)
    tsub.add_parser("list")
    ts_show = tsub.add_parser("show")
    ts_show.add_argument("name")
    ts_new = tsub.add_parser("new", help="牌表を作る。例 tileset new --colors mps --mark 5m=red --mark 5p=red --out DIR")
    ts_new.add_argument("--colors", required=True, help="色の組。m p s z（例 mps、mpsz、m）")
    ts_new.add_argument("--mark", action="append", help="牌種=印,印…（1 枚目から順に付ける）。例 5m=red、5p=red,gold。複数可")
    ts_new.add_argument("--exclude", help="除く牌種（各 4 枚）。例 2m,3m,4m,5m,6m,7m,8m")
    ts_new.add_argument("--extra", help="エクストラ牌。名前、または 名前=印（印はルールの marks で機能を付ける）。例 梅,蘭,菊,竹　／　梅=flower,蘭=flower")
    ts_new.add_argument("--out")
    ts_exp = tsub.add_parser("export")
    ts_exp.add_argument("--out", required=True)
    t.set_defaults(fn=cmd_tileset)

    r = sp.add_parser("ruleset", help="ルール：list / show / new / diff / validate")
    rsub = r.add_subparsers(dest="sub", required=True)
    rsub.add_parser("list")
    r_show = rsub.add_parser("show"); r_show.add_argument("name")
    r_val = rsub.add_parser("validate"); r_val.add_argument("files", nargs="+")
    r_diff = rsub.add_parser("diff"); r_diff.add_argument("a"); r_diff.add_argument("b")
    r_new = rsub.add_parser("new", help="雛形＋差分で作る。値は JSON（例 --set settlement.uma=[20,10,-10,-20]）")
    r_new.add_argument("--from", dest="from_", help="雛形の name / name@id / ファイル")
    r_new.add_argument("--name", required=True)
    r_new.add_argument("--set", action="append", help="path=value（JSON）")
    r_new.add_argument("--tileset", help="牌表（--from が無いとき必須）")
    r_new.add_argument("--out")
    r.set_defaults(fn=cmd_ruleset)

    im = sp.add_parser("import", help="取り込み：import tenhou FILE… [--out DIR]")
    im.add_argument("source", choices=["tenhou", "tenhou-json"],
                    help="tenhou＝mjlog XML（山を再現）／tenhou-json＝tenhou.net/6 の JSON（山なし）")
    im.add_argument("files", nargs="+")
    im.add_argument("--out")
    im.set_defaults(fn=cmd_import)

    ob = sp.add_parser("observe", help="局面：observe RECORD --round R --at AT --seat S [--full] [--names]")
    ob.add_argument("record"); ob.add_argument("--round", type=int, required=True); ob.add_argument("--at", type=int, required=True)
    ob.add_argument("--seat", type=int, required=True); ob.add_argument("--full", action="store_true", help="全員の手牌（神視点）")
    ob.add_argument("--names", action="store_true", help="牌を文字で")
    ob.set_defaults(fn=cmd_observe)

    lg = sp.add_parser("legal", help="合法手：legal RECORD --round R --at AT --seat S [--phase A|B|C] [--mjai]")
    lg.add_argument("record"); lg.add_argument("--round", type=int, required=True); lg.add_argument("--at", type=int, required=True)
    lg.add_argument("--seat", type=int, required=True); lg.add_argument("--phase", choices=["A", "B", "C"])
    lg.add_argument("--mjai", action="store_true", help="request_action の形で出す")
    lg.set_defaults(fn=cmd_legal)

    jg = sp.add_parser("judge", help="和了の役・符を判定して記録と比べる：judge RECORD [--round R] [--merge-dora]")
    jg.add_argument("record"); jg.add_argument("--round", type=int)
    jg.add_argument("--merge-dora", action="store_true", help="カンドラ・抜きドラを「ドラ」にまとめて比べる（天鳳の書き方）")
    jg.set_defaults(fn=cmd_judge)

    pl = sp.add_parser("play", help="進行役に 1 対局を進めさせる：play RULESET [--seed S] [--bot simple|tsumogiri] [--player 席=コマンド] [--out DIR]")
    pl.add_argument("ruleset"); pl.add_argument("--seed", default="play"); pl.add_argument("--bot", default="simple", choices=["simple", "tsumogiri"])
    pl.add_argument("--player", action="append", help="その席を別プログラムにする。例 --player '1=python3 -m nmahjong.bots simple'")
    pl.add_argument("--out"); pl.add_argument("--loose", action="store_true", help="打ち手の壊れた応答を既定の行動に置き換えて続ける")
    pl.add_argument("--allow-unsupported", action="store_true", help="まだ従えない設定があるルールでも、代わりの扱いで進める")
    pl.add_argument("--annotate", action="store_true", help="打牌が届くたびに評価を付ける（nm-waits）。--out があれば評価ファイルも書く")
    pl.add_argument("--verbose", action="store_true", help="--annotate のとき、評価を 1 つずつ表示")
    pl.set_defaults(fn=cmd_play)

    ar = sp.add_parser("arena", help="対戦場：arena RULESET --entrant 名前=simple --entrant 名前='コマンド' [--games N] [--seed S] [--out DIR]")
    ar.add_argument("ruleset"); ar.add_argument("--entrant", action="append", required=True, help="名前=simple|tsumogiri か 名前=別プログラムのコマンド。人数ぶん以上")
    ar.add_argument("--games", type=int, default=5, help="組の数。1 組＝同じ山を席をずらして人数ぶん打つ"); ar.add_argument("--seed", default="arena")
    ar.add_argument("--no-mirror", action="store_true", help="席をずらして打ち直さない（1 組 1 対局）"); ar.add_argument("--out")
    ar.add_argument("--strict", action="store_true", help="打ち手の壊れた応答で止める（既定は既定の行動に置き換えて続ける）")
    ar.add_argument("--allow-unsupported", action="store_true")
    ar.set_defaults(fn=cmd_arena)

    an = sp.add_parser("annotate", help="同梱評価器で評価ファイルを作る：annotate RECORD [--evaluator nm-waits] [--out DIR]")
    an.add_argument("record"); an.add_argument("--evaluator", default="nm-waits"); an.add_argument("--out")
    an.set_defaults(fn=cmd_annotate)

    ex = sp.add_parser("export", help="record → 天鳳 JSON（tenhou.net/6 形式）：export tenhou-json RECORD")
    ex.add_argument("source", choices=["tenhou-json"]); ex.add_argument("record")
    ex.set_defaults(fn=cmd_export)

    mj = sp.add_parser("mjai", help="record → mjai イベント列（JSON Lines）：mjai RECORD [--seat S]")
    mj.add_argument("record"); mj.add_argument("--seat", type=int)
    mj.set_defaults(fn=cmd_mjai)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except ValidationError as e:
        print(f"NG {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
