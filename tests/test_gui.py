import unittest
import tkinter as tk

from booruget.gui import ABOUT_LINKS, BooruGetGUI


class GUISafetyTests(unittest.TestCase):
    def test_does_not_shadow_tkinter_internal_options(self):
        self.assertNotIn("_options", BooruGetGUI.__dict__)
        self.assertIs(BooruGetGUI._options, tk.Misc._options)

    def test_about_links(self):
        self.assertEqual(ABOUT_LINKS["website"], "https://ntdmn.xyz/")
        self.assertEqual(
            ABOUT_LINKS["github"],
            "https://github.com/netdaemon91",
        )
        self.assertEqual(
            ABOUT_LINKS["project"],
            "https://github.com/netdaemon91/BooruGet",
        )
        self.assertEqual(
            ABOUT_LINKS["original_project"],
            "https://github.com/fhrach4/BooruGet",
        )

    def test_language_and_about_handlers_exist(self):
        self.assertTrue(callable(BooruGetGUI._toggle_language))
        self.assertTrue(callable(BooruGetGUI._apply_language))
        self.assertTrue(callable(BooruGetGUI._show_about))


if __name__ == "__main__":
    unittest.main()
