"""Contract tests for the offline documentation renderer, not Omnis."""
import importlib.util
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RenderDocsTests(unittest.TestCase):
    def renderer(self):
        path = ROOT / "scripts" / "render_docs.py"
        self.assertTrue(path.is_file(), "offline documentation renderer is missing")
        spec = importlib.util.spec_from_file_location("render_docs", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_offline_shell_and_semantics(self):
        result = self.renderer().render("# Plan\n\n## First gate\n\nText.", "Plan", "Plan.md")
        self.assertIn('lang="ro"', result)
        self.assertIn('id="content"', result)
        self.assertIn('href="#first-gate"', result)
        self.assertNotIn('<script src="http', result)
        self.assertNotIn('<link href="http', result)

    def test_reader_does_not_override_document_implementation_status(self):
        result = self.renderer().render('# P0.4\n\nPartially implemented.', 'Status', 'Status.md')
        self.assertIn('Specificat · starea implementării în document', result)
        self.assertNotIn('Specificat · aplicație neimplementată', result)

    def test_tables_have_local_scroll_regions(self):
        result = self.renderer().render("# X\n\n| A | B |\n|---|---|\n| a | b |", "X", "X.md")
        self.assertIn('class="table-wrap"', result)
        self.assertIn('tabindex="0"', result)

    def test_code_stays_inert(self):
        result = self.renderer().render('# X\n\n```html\n<script>alert(1)</script>\n```', "X", "X.md")
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('<script>alert(1)', result)

    def test_metadata_is_escaped(self):
        result = self.renderer().render('# X', '<unsafe>', 'x".md')
        self.assertIn('&lt;unsafe&gt;', result)
        self.assertIn('x&quot;.md', result)
        self.assertNotIn('<title><unsafe>', result)

    def test_heading_links_use_escaped_text_only_in_both_tocs(self):
        result = self.renderer().render(
            '## [API & &lt;safe&gt;](https://example.invalid) **bold** `code`',
            "Plan", "Plan.md",
        )
        navs = re.findall(r'<nav aria-label="Cuprins">(.*?)</nav>', result, re.S)
        self.assertEqual(len(navs), 2)
        for nav in navs:
            self.assertEqual(nav.count('<a '), 1, "TOC links must not contain nested anchors")
            self.assertIn('>API &amp; &lt;safe&gt; bold code</a>', nav)
            self.assertNotRegex(nav, r'<(?:strong|code|em)\b')
        self.assertIn('<a href="https://example.invalid">', result)

    def test_plan_and_architecture_both_configured(self):
        names = [p[0] for p in self.renderer().DOCUMENTS]
        self.assertIn('Omnis_Implementation_Plan', names)
        self.assertIn('Omnis_MVP_Architecture', names)

    def test_static_csp_is_defense_in_depth_not_markdown_sanitization(self):
        renderer = self.renderer()
        result = renderer.render('# X\n\n<script>unsafe()</script>', 'X', 'X.md')
        self.assertIn("default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'", result)
        self.assertIn('http-equiv="Content-Security-Policy"', result)
        self.assertNotIn('script-src', result)
        self.assertIn('<script>unsafe()</script>', result, "raw trusted Markdown is not sanitized")
        self.assertIn('not a sanitizer', renderer.__doc__ or '')

    def test_render_is_deterministic_and_digest_tracks_exact_source(self):
        renderer = self.renderer()
        text = '# Șablon\n\n## Repeated\n\n## Repeated\n'
        expected = renderer.render(text, 'Șablon', 'X.md')
        renderer.render('## Other', 'Other', 'Other.md')
        self.assertEqual(expected, renderer.render(text, 'Șablon', 'X.md'))
        self.assertIn(hashlib.sha256(text.encode('utf-8')).hexdigest(), expected)
        self.assertIn('href="#repeated_1"', expected)
        self.assertNotEqual(expected, renderer.render(text + '\n', 'Șablon', 'X.md'))

    def cli_fixture(self):
        # Never render over the working documents: the parent may edit them.
        temp = tempfile.TemporaryDirectory(prefix='omnis-renderer-')
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'scripts').mkdir()
        docs = root / 'documents'
        docs.mkdir()
        script = root / 'scripts' / 'render_docs.py'
        shutil.copyfile(ROOT / 'scripts' / 'render_docs.py', script)
        for name, _ in self.renderer().DOCUMENTS:
            (docs / (name + '.md')).write_text('# Fixture\n\n## Gate\n\nTrusted text.', encoding='utf-8')
        return script, docs

    def cli(self, script, *args):
        return subprocess.run([sys.executable, '-B', str(script), *args], capture_output=True, text=True, check=False)

    def test_cli_render_and_check_are_deterministic_and_check_is_read_only(self):
        script, docs = self.cli_fixture()
        run = self.cli(script)
        self.assertEqual(run.returncode, 0, run.stderr)
        expected = {p.name: p.read_bytes() for p in docs.glob('*.html')}
        self.assertEqual(len(expected), len(self.renderer().DOCUMENTS))
        self.assertEqual(self.cli(script).returncode, 0)
        self.assertEqual(expected, {p.name: p.read_bytes() for p in docs.glob('*.html')})
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in docs.iterdir()}
        check = self.cli(script, '--check')
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(set(check.stdout.splitlines()), {'OK ' + name for name in expected})
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in docs.iterdir()})

    def test_cli_check_reports_stale_and_missing_outputs_without_writing(self):
        script, docs = self.cli_fixture()
        self.assertEqual(self.cli(script).returncode, 0)
        outputs = sorted(docs.glob('*.html'))
        outputs[0].write_text('stale fixture', encoding='utf-8')
        outputs[1].unlink()
        check = self.cli(script, '--check')
        self.assertEqual(check.returncode, 1)
        for output in outputs[:2]:
            self.assertIn('STALE ' + output.name, check.stdout)
        self.assertEqual(outputs[0].read_text(encoding='utf-8'), 'stale fixture')
        self.assertFalse(outputs[1].exists())

    def test_cli_missing_source_fails_without_inventing_output(self):
        script, docs = self.cli_fixture()
        source = sorted(docs.glob('*.md'))[0]
        source.unlink()
        for args in [(), ('--check',)]:
            with self.subTest(args=args):
                run = self.cli(script, *args)
                self.assertEqual(run.returncode, 1)
                self.assertIn('MISSING source: ' + source.name, run.stdout)
                self.assertFalse(source.with_suffix('.html').exists())


if __name__ == "__main__":
    unittest.main()
