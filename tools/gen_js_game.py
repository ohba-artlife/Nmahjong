"""js/src/game_*.js をつないで js/nmahjong-game.js を作る（4 層・5 層の JS 版）。直すのは src のほう。"""
import glob
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parts = sorted(glob.glob(os.path.join(ROOT, "js", "src", "game_*.js")))
out = os.path.join(ROOT, "js", "nmahjong-game.js")
with open(out, "w", encoding="utf-8") as f:
    for p in parts:
        with open(p, encoding="utf-8") as src:
            f.write(src.read())
print(f"js/nmahjong-game.js（{len(parts)} 個の部品、{os.path.getsize(out)} バイト）")
