"""Guard authored translations without treating a catalog as complete GUI QA."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import seed_editor_catalogs as seed
import audit_localization as audit


class AuthoredCatalogs(unittest.TestCase):
    def test_all_authored_rows_preserve_arguments_and_five_translations(self):
        for path in (ROOT / 'patches/localization-shared').glob('*-interface.tsv'):
            rows = seed.authored_rows(path)
            self.assertTrue(rows)
            for key, translations in rows.items():
                self.assertEqual(set(translations), {'vi', 'ko', 'ja', 'zh-TW', 'zh-CN'})
                for language, value in translations.items():
                    self.assertEqual(audit.placeholders(key), audit.placeholders(value), (path.name, key, language))

    def test_deck_exceptions_cannot_hide_other_languages_or_apps(self):
        self.assertIn(('', 'Video'), audit.reviewed_exceptions('deck', 'vi'))
        self.assertNotIn(('', 'Video'), audit.reviewed_exceptions('deck', 'ja'))
        self.assertNotIn(('', 'Video'), audit.reviewed_exceptions('sound', 'ja'))
        self.assertNotIn(('', 'RRGGBB'), audit.reviewed_exceptions('sound', 'vi'))
        self.assertNotIn(('', 'Save'), audit.reviewed_exceptions('deck', 'vi'))

    def test_filename_is_not_a_translation_key(self):
        data = ROOT / 'patches/localization-shared'
        keys = json.loads((data / 'deck-source-keys.json').read_text(encoding='utf-8'))
        self.assertNotIn('Pasted image.png', keys['keys'])
        self.assertNotIn('Pasted image.png', seed.authored_rows(data / 'deck-interface.tsv'))
        self.assertTrue(keys['excludedTechnicalKeys'][0]['reason'])

    def test_presentation_and_audio_bounce_are_separate_editorial_choices(self):
        data = ROOT / 'patches/localization-shared'
        deck = seed.authored_rows(data / 'deck-interface.tsv')
        self.assertEqual(deck['Bounce']['ja'], 'バウンド')
        self.assertEqual(deck['Delete Rows']['zh-TW'], '刪除列')
        self.assertEqual(deck['Delete Rows']['zh-CN'], '删除行')
        sound = seed.authored_rows(data / 'sound-interface.tsv')
        self.assertNotEqual(deck['Bounce']['ja'], sound['Bounce']['ja'])


if __name__ == '__main__':
    unittest.main()
