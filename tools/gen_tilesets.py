"""同梱牌表を nmahjong/data/tilesets/ に生成する（定義は tileset.bundled_definitions）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nmahjong import tileset as TS, files  # noqa: E402

out = os.path.join(os.path.dirname(__file__), "..", "nmahjong", "data", "tilesets")
for key, kw in TS.bundled_definitions().items():
    ts = TS.build(**kw)
    TS.validate(ts)
    print(key, files.save(ts, out, TS.filename(ts)))
