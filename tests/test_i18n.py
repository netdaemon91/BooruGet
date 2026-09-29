import unittest

from booruget.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    TEXT,
    normalize_language,
    tr,
)


class I18nTests(unittest.TestCase):
    def test_languages_have_identical_keys(self):
        key_sets = [set(TEXT[language]) for language in LANGUAGES]
        self.assertTrue(key_sets)
        for keys in key_sets[1:]:
            self.assertEqual(keys, key_sets[0])

    def test_language_normalization(self):
        self.assertEqual(normalize_language("de"), "de")
        self.assertEqual(normalize_language("EN"), "en")
        self.assertEqual(normalize_language("xx"), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language(None), DEFAULT_LANGUAGE)

    def test_translations_format_values(self):
        self.assertEqual(
            tr("de", "status.searching", provider="Danbooru"),
            "Suche: Danbooru",
        )
        self.assertEqual(
            tr("en", "status.searching", provider="Danbooru"),
            "Searching: Danbooru",
        )

    def test_core_gui_labels_are_translated(self):
        self.assertEqual(tr("de", "about.button"), "Über")
        self.assertEqual(tr("en", "about.button"), "About")
        self.assertEqual(tr("de", "button.start_download"), "Download starten")
        self.assertEqual(tr("en", "button.start_download"), "Start download")


if __name__ == "__main__":
    unittest.main()
