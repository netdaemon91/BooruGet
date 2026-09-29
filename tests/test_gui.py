import unittest
import tkinter as tk

from booruget.gui import BooruGetGUI


class GUISafetyTests(unittest.TestCase):
    def test_does_not_shadow_tkinter_internal_options(self):
        self.assertNotIn("_options", BooruGetGUI.__dict__)
        self.assertIs(BooruGetGUI._options, tk.Misc._options)


if __name__ == "__main__":
    unittest.main()
