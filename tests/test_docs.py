"""文書の参照：公開している文書・プログラムの中に書いた文書名（〜.md）とファイルの場所が、実際にあること。
internal/（公開しない）の文書を指していないこと。"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "internal", "__pycache__", "node_modules"}
SKIP_FILES = {"CHANGELOG.md", os.path.join("js", "nmahjong-game.js"), os.path.join("js", "bundled.js")}   # 履歴・生成物
NOT_PUBLIC = {"SCHEDULE.md", "TEST.md", "DESIGN.md", "INSTALL.md"}
EXTERNAL = {"faq.md"}                                     # 外部サイトの URL の中の名前
MD = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w-]+\.md)\b")
# 日本語の文書（〜_JA.md）が一式あるかどうか。公開版にあるのは、表紙の README_JA.md だけ
HAS_JA = os.path.exists(os.path.join(ROOT, "docs", "README" + "_JA.md"))
PATH = re.compile(r"(?<![\w/.-])((?:nmahjong|tests|tools|js|examples|docs)/[\w./*-]+)")


def public_files():
    for d, ds, fs in os.walk(ROOT):
        ds[:] = [x for x in ds if x not in SKIP_DIRS]
        for f in fs:
            p = os.path.relpath(os.path.join(d, f), ROOT)
            if f.rsplit(".", 1)[-1] in ("py", "js", "md", "html", "toml") and p not in SKIP_FILES:
                yield p


class TestDocReferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = sorted(p for p in public_files() if p != os.path.join("tests", "test_docs.py"))
        cls.md = {"CHANGELOG.md": ["CHANGELOG.md"]}
        for p in cls.files:
            if p.endswith(".md"):
                cls.md.setdefault(os.path.basename(p), []).append(p)

    def test_DOC1_layout(self):
        for p in ("README.md", "docs/README.md", "docs/overview.md", "docs/install.md", "docs/spec/tileset.md", "docs/spec/ruleset.md",
                  "docs/spec/wall.md", "docs/spec/record.md", "docs/spec/annotation.md", "docs/rules/nm-defaults.md"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, p)), p)
        root_md = sorted(f for f in os.listdir(ROOT) if f.endswith(".md"))
        self.assertFalse(set(root_md) & NOT_PUBLIC, "公開しない文書がルートにある")

    def test_DOC2_md_names_exist(self):
        """書いてある文書名が、公開側にある（場所つきならその場所に、名前だけならどこかに 1 つ）。"""
        bad = []
        for p in self.files:
            with open(os.path.join(ROOT, p), encoding="utf-8") as f:
                text = re.sub(r"https?://\S+", "", f.read())
            here = os.path.dirname(p)
            for ref in set(MD.findall(text)):
                name = os.path.basename(ref)
                if name in EXTERNAL or name.startswith("README"):
                    continue
                if name.endswith("_JA.md") and not HAS_JA:
                    continue                                  # 日本語の文書が無い版では、その名前は調べない
                if name in NOT_PUBLIC:
                    bad.append(f"{p}: {ref}（公開しない文書）")
                elif "/" in ref:
                    if not (os.path.exists(os.path.join(ROOT, ref)) or os.path.exists(os.path.join(ROOT, here, ref))
                            or os.path.exists(os.path.join(ROOT, "docs", ref))):
                        bad.append(f"{p}: {ref}（その場所に無い）")
                elif len(self.md.get(name, [])) != 1:
                    bad.append(f"{p}: {ref}（{len(self.md.get(name, []))} 個ある）")
        self.assertEqual(bad, [])

    def test_DOC3_paths_exist(self):
        """文書に書いてあるファイルの場所（nmahjong/…、tests/…、tools/…、js/…、examples/…、docs/…）が実際にある。"""
        import glob
        bad = []
        for p in self.files:
            if not p.endswith(".md"):
                continue
            with open(os.path.join(ROOT, p), encoding="utf-8") as f:
                text = re.sub(r"https?://\S+", "", f.read())
            for ref in set(PATH.findall(text)):
                ref = ref.rstrip(".-/")
                if "…" in ref or "{" in ref:
                    continue
                if not (glob.glob(os.path.join(ROOT, ref)) or glob.glob(os.path.join(ROOT, ref + "*"))):
                    bad.append(f"{p}: {ref}")
        self.assertEqual(bad, [])

    def test_DOC4_markdown_links(self):
        """Markdown のリンク [..](相対パス) の先がある。"""
        bad = []
        for p in self.files:
            if not p.endswith(".md"):
                continue
            with open(os.path.join(ROOT, p), encoding="utf-8") as f:
                text = f.read()
            for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
                if re.match(r"[a-z]+:", target):
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(ROOT, os.path.dirname(p), target))):
                    bad.append(f"{p}: {target}")
        self.assertEqual(bad, [])


    def test_DOC5_english_and_japanese_pairs(self):
        """日本語の文書が一式ある版：英語の X.md には日本語の X_JA.md があり、互いにリンクしている。
        日本語の文書が無い版：日本語は表紙の README_JA.md だけで、README.md と互いにリンクしている。"""
        def text(p):
            with open(os.path.join(ROOT, p), encoding="utf-8") as f:
                return f.read()
        md = [p for p in self.files + ["CHANGELOG.md"] if p.endswith(".md")]
        bad = []
        if not HAS_JA:
            self.assertEqual(sorted(p for p in md if p.endswith("_JA.md")), ["README_JA.md"])
            self.assertIn("](README_JA.md)", text("README.md"))
            self.assertIn("](README.md)", text("README_JA.md"))
            for p in md:
                if p != "README.md" and p != "README_JA.md" and "_JA.md" in text(p):
                    bad.append(f"{p}: 無い日本語版を指している")
            self.assertEqual(bad, [])
            return
        for p in md:
            if p.endswith("_JA.md") or p.startswith(".github"):
                continue
            ja = p[:-3] + "_JA.md"
            if not os.path.exists(os.path.join(ROOT, ja)):
                bad.append(f"{p}: 日本語版が無い")
                continue
            if f"]({os.path.basename(ja)})" not in text(p):
                bad.append(f"{p}: 日本語版へのリンクが無い")
            if f"]({os.path.basename(p)})" not in text(ja):
                bad.append(f"{ja}: 英語版へのリンクが無い")
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
