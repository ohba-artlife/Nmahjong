# Nmahjong

English: [README.md](README.md)

N 枚麻雀のためのデータ形式（牌表・ルール・牌山・対局・評価）と、参照実装（Python）・第二実装（JavaScript）。

## 位置づけ

保存形式（牌表・ルール・牌山・対局・評価の 5 層）＋それを作る・確かめる・進めるプログラム。麻雀を打つ画面と、強い AI そのものは持たない。

- 打ち終わった対局（天鳳など）を取り込み、山・点数・精算を確かめる。ルールと牌山を作る
- 打っている最中の対局をその場で作る：記録係、打ち手の接続口、進行役、和了の役と符の判定、評価、対戦場
- 図と詳しい説明は `docs/overview.md`、文書の一覧は `docs/README.md`

## 目的
麻雀を「牌の集合」「手牌の枚数 N」「人数 M（1 以上）」で一般化し、1 枚麻雀から 13 枚麻雀、三人麻雀、花牌入りまでを **1 つの器** で表す。
牌表・ルール・牌山・対局・評価をそれぞれ独立したデータとして定義し、生成した山も、実卓から読み取った山も、取り込んだ山も、同じ形で保存・検証・再現できるようにする。

## 全体像（5 層）
```
前  牌表（tileset）   何の牌が何枚あり、何番が何か。印（赤・ポッチ）は事実として持つ          1.0
    ルール（ruleset） 山の消費規則・麻雀のルール・終了・精算。同梱 46 本（団体・ネット・店など）   1.0
始  牌山（wall）      番号の順列。生成／観測／観測＋生成。どこまでが事実かを必ず書く            1.0
    対局（record）    出所・利用者・局・出来事・結果。ルールと牌山を id で参照。1 対局 = 1 ファイル 1.0
後  評価（annotation）判断点ごとの候補と値。値の名前は評価器が宣言。対局を id で参照          1.0
```
- 牌は **番号** で扱う。番号の意味は牌表だけが持つ
- 全色・各 4 枚（`mpsz`）のとき、番号は天鳳の 0〜135 と一致する
- id は中身のハッシュ（SHA-256）。同じ中身なら誰が作っても同じ id
- 取り込みは天鳳（mjlog XML・tenhou.net/6 JSON）。雀魂は v2。書き出しは検証・連携用の天鳳 JSON と mjai だけ
- AI への局面の提示は mjai 互換（独自形式は作らない）。合法手の列挙 `legal_actions(ruleset, 局面)` を持つ

## 同梱するもの
- 同梱ルール 46 本（団体・天鳳・雀魂・TV・雀荘・三麻・N 枚麻雀。一覧は `docs/spec/ruleset.md` §7）と、ルール生成器（CLI `ruleset new` と画面 `tools/rulegen.html`）
- 役表・点数表・語彙表・天鳳の役対応表
- テストベクタ（牌山の生成）、JSON スキーマ

## 前提・環境
- 参照実装：Python 3.11 以上、標準ライブラリのみ（3.11・3.12・3.13 で試験）
- 第二実装：JavaScript（ブラウザ・Node）。同じテストベクタを通す
- 器は JSON

## 使い方（最短手順）
```bash
pip install -e .
python -m nmahjong build    --tileset mpsz --seed 2026-11-11T10:00:00+09:00 > out.wall.json
python -m nmahjong validate out.wall.json
python -m nmahjong show     out.wall.json
python -m nmahjong ruleset  list
python -m nmahjong ruleset  new --from mleague --set settlement.uma=[20,10,-10,-20] --name my-rule
python -m nmahjong import   tenhou 2026111023gm-00a9-0000-1a2b3c4d.mjlog --out ./out     # 山を再現して X5 まで検証
python -m nmahjong import   tenhou-json log.json --out ./out                              # tenhou.net/6 の JSON（山なし）
python -m nmahjong legal    ./out/*.record.json --round 0 --at 68 --seat 3 --phase A       # 合法手と実際の行動
python -m nmahjong annotate ./out/*.record.json --out ./out                               # 同梱評価器で評価ファイル
python -m nmahjong mjai     ./out/*.record.json --seat 0                                  # mjai イベント列（他家を伏せる）
```
ルール生成の画面：`tools/rulegen.html` をブラウザで開く（サーバー不要。同梱ルールを雛形に選んで項目を変える → id と差分 → ダウンロード）。

## 入出力（概要）
| データ | ファイル名 | 主な中身 |
|---|---|---|
| 牌表 | `{name}_{id64}.tileset.json` | name, id, tiles[]（id, kind, mark, name） |
| ルール | `{name}_{id64}.ruleset.json` | tileset, players, hand_size, wall_rules, game_rules, end, settlement |
| 牌山 | `{tileset}_{id64}.wall.json` | tileset, source, generation / observed+fill, device, order[], id |
| 対局 | `{tileset}_{id64}.record.json` | source, ruleset, players, rounds[]（wall, state, events, result）, final |
| 評価 | `{record_id64}_{evaluator}.annotation.json` | record, evaluator（metrics 宣言）, points[] |

id64 ＝ SHA-256 の 16 進 64 桁をそのまま。牌表の名前：`{色}[-x枚数][-e枚数]`（例 `mpsz`、`mpsz-x28`）。参照は `{name, id}` で id が正。
文字表記（表示・読み込み・AI 接続）は mjai 形式（`1m`〜`9s`、`5mr`、`E S W N P F C`）。`1z`〜`7z`・`0m` も読み込める。

## 状態（版 1.0.0、2026-11-22）
- 仕様：5 層とも 1.0
- 参照実装（Python）：5 層の読み書き・id・検証、和了の役と符の判定、点数・精算、局面・合法手、記録係、打ち手の接続口（mjai 互換）、進行役、評価、対戦場、天鳳の取り込み（XML は山を再現、JSON は山なし）
- 第二実装（JavaScript）：id・検証・判定・記録係・進行役・評価。同じテストベクタと試験データで Python と結果が一致
- 同梱：牌表 10、ルール 46
- 確かめたこと（件数と中身は `docs/conformance.md`）：天鳳の対局 1,005（山の再現、役・符・点数、精算）、N 枚麻雀の別実装の対局 11,000 以上、Python と JavaScript の突き合わせ、天鳳が公表しているルールの文との 1 項目ずつの突き合わせ
- まだ無いもの：雀魂の取り込み。進行役が従えない設定は `docs/programs/dealer.md` §4

## ことば
文書は英語で書いてある。日本語があるのはこのページ（`README_JA.md`）だけで、このページから指している文書は英語。プログラムの出すメッセージ、ソースコードの中の説明、同梱ルールの中の説明は日本語。

## 参加・報告・引用
- 不具合、麻雀の記載としておかしい所、同梱ルールの直し：Issues（書き方は `CONTRIBUTING.md`）
- セキュリティの問題：公開の Issue に書かず、`SECURITY.md` の方法で
- 行動のきまり：`CODE_OF_CONDUCT.md`
- 引用のしかた：`CITATION.cff`
- 変更の記録：`CHANGELOG.md`

## ライセンス
- 実装（Python・JavaScript・tools・tests・同梱データ）：MIT（`LICENSE`）
- 仕様文書（*.md）：CC BY 4.0（`LICENSE-SPEC`）
- 著作権者：ohba-artlife

## 関連文書
- `docs/README.md` 文書の一覧
- `docs/overview.md` 全体像（5 層、層またぎ検証、局面と接続口、同梱データ、取り込み）
- `docs/install.md` 導入とコマンドの一覧
- `docs/spec/` 各層の仕様書（`tileset.md` `ruleset.md` `wall.md` `record.md` `annotation.md`）
- `docs/rules/nm-defaults.md` N 枚麻雀の既定ルール（同梱の nm-*）の中身
- `docs/programs/` プログラムの説明（記録係と接続口、進行役、判定、評価と対戦場、JavaScript 版）
- `docs/design/` 設計の根拠（日本の主要ルールの調査、局面の提示、評価の値）
