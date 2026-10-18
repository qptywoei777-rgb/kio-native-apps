import json
from pathlib import Path, PureWindowsPath
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reuse_six_language_catalogs as reuse
import apply_catalog_reuse as apply
import check_localization_candidate as candidate


def row(app, text='Lưu {name}', context='', key='Save {name}'):
    return {'app': app, 'language': 'vi', 'context': context, 'source': key,
            'translation': text, 'forms': [text], 'kind': 'plain',
            'provenance': {'app': app, 'file': 'vi.tsv', 'sha256': 'a' * 64}}


def app(name, rows=(), keys=(('', 'Save {name}', 'plain'),)):
    return {'app': name, 'available': True, 'rows': list(rows), 'keys': set(keys),
            'files': {}, 'issues': []}


class CatalogReuseSafety(unittest.TestCase):
    def test_app_scoped_meaning_cannot_become_a_generic_exact_spelling_donor(self):
        scoped=row('grid',text='Khối dữ liệu',key='Cube')
        scoped['donorScope']='app'
        keys=(('', 'Cube', 'plain'),)
        plan=reuse.build_plan([app('photo',keys=keys),app('grid',[scoped],keys=keys)])
        self.assertEqual(plan['proposalCount'],0)
        self.assertEqual(plan['rejectedCount'],0,'An app-specific translation is valid in its own context')

    def test_windows_candidate_path_matches_the_published_posix_manifest(self):
        root=PureWindowsPath('D:/a/kio-native-apps/kio-native-apps')
        path=root/'patches/localization-candidates/sound.patch'
        self.assertEqual(candidate.relative_patch_path(path,root),'patches/localization-candidates/sound.patch')
        self.assertFalse(candidate.allowed('sound','Cargo.lock'))
        self.assertFalse(candidate.allowed('sound','crates/engine/src/lib.rs'))
        self.assertTrue(candidate.allowed('sound','crates/ui-egui/src/i18n/mod.rs'))

    def test_conflicting_donors_do_not_use_majority_vote(self):
        apps = [app('photo'), app('vector', [row('vector')]),
                app('film', [row('film')]), app('word', [row('word', 'Ghi {name}')])]
        plan = reuse.build_plan(apps)
        self.assertEqual(plan['proposalCount'], 0)
        self.assertEqual(plan['conflictCount'], 1)

    def test_exact_context_and_variable_occurrences_are_required(self):
        plan = reuse.build_plan([app('photo'), app('vector', [row('vector', context='menu')])])
        self.assertEqual(plan['proposalCount'], 0)
        plan = reuse.build_plan([app('photo'), app('vector', [row('vector', 'Lưu {name} {name}')])])
        self.assertEqual(plan['proposalCount'], 0)
        self.assertEqual(plan['rejected'][0]['reason'], 'placeholderMismatch')

    def test_english_copy_is_not_a_translation_without_exact_exception(self):
        plan = reuse.build_plan([app('photo'), app('vector', [row('vector', 'Save {name}')])])
        self.assertEqual(plan['proposalCount'], 0)
        self.assertEqual(plan['rejected'][0]['reason'], 'unchangedEnglishWithoutException')

    def test_existing_translation_is_never_replaced_by_majority(self):
        plan = reuse.build_plan([app('photo', [row('photo', 'Ghi {name}')]),
                                app('vector', [row('vector')])])
        self.assertEqual(plan['proposalCount'], 0)

    def test_simplified_and_traditional_are_independent(self):
        self.assertEqual(reuse.placeholders('50% Gray, % of all commits, % dọc'), {})
        self.assertEqual(reuse.language('zh-hant'), 'zh-TW')
        self.assertEqual(reuse.language('zh-cn'), 'zh-CN')
        self.assertNotEqual(reuse.language('zh-hant'), reuse.language('zh-hans'))

    def fixture(self, root):
        for name, source in [('photo', '\tCancel\tHủy\n'),
                             ('vector', '\tSave {name}\tLưu {name}\n')]:
            folder = root / '.work/full-native' / name / 'source/crates/ui-egui/src/i18n'
            folder.mkdir(parents=True)
            (folder / 'vi.tsv').write_text(source, encoding='utf-8')
            (folder.parent / 'lib.rs').write_text('tr("Save {name}");', encoding='utf-8')
        apps = [reuse.read_app(name, apply.source_for(root, name)) for name in ('photo', 'vector')]
        return reuse.build_plan(apps)

    def test_apply_backs_up_all_originals_and_is_additive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.fixture(root)
            result = apply.apply(root, plan, [], [], root / 'receipt')
            self.assertEqual(result['appliedEntries'], 1)
            self.assertEqual(result['status'], 'applied')
            p = apply.source_for(root, 'photo') / 'crates/ui-egui/src/i18n/vi.tsv'
            self.assertTrue(p.read_text(encoding='utf-8').startswith('\tCancel\tHủy\n'))
            self.assertIn('\tSave {name}\tLưu {name}', p.read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'already exists'):
                apply.apply(root, plan, [], [], root / 'receipt')

    def test_stale_input_or_tampered_plan_fails_before_any_mutation(self):
        for kind in ('input', 'plan'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); plan = self.fixture(root)
                path = apply.source_for(root, 'vector') / 'crates/ui-egui/src/i18n/vi.tsv'
                if kind == 'input':
                    path.write_text('\tSave {name}\tGhi {name}\n', encoding='utf-8')
                else:
                    plan['proposals'][0]['translation'] = 'unreviewed'
                with self.assertRaises(ValueError):
                    apply.apply(root, plan, [], [], root / 'receipt')
                self.assertFalse((root / 'receipt').exists())

    def test_legacy_windows_encoding_does_not_corrupt_catalogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self.fixture(root)
            original_open = Path.open
            def legacy_open(path, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
                if 'b' not in mode and encoding in (None, 'locale'):
                    encoding = 'cp1252'
                return original_open(path, mode, buffering, encoding, errors, newline)
            with patch.object(Path, 'open', legacy_open):
                result = apply.apply(root, plan, [], [], root / 'receipt')
            self.assertEqual(result['status'], 'applied')

    def test_no_new_runtime_language_is_silently_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            target = apply.source_for(root, 'photo') / 'crates/ui-egui/src/i18n/vi.tsv'
            target.unlink()
            apps = [reuse.read_app(name, apply.source_for(root, name)) for name in ('photo', 'vector')]
            plan = reuse.build_plan(apps)
            changes, skipped = apply.prepare_changes(root, plan, [], [])
            self.assertFalse(changes)
            self.assertEqual(skipped['runtimeLanguageOrFormatReviewRequired'], 1)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
