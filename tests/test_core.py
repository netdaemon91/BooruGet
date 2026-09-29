import unittest

from booruget.downloader import safe_folder_name
from booruget.filters import normalize_rating, PostFilter
from booruget.models import Post, SearchOptions


class CoreTests(unittest.TestCase):
    def test_rating_normalization(self):
        self.assertEqual(normalize_rating("danbooru", "g"), "general")
        self.assertEqual(normalize_rating("danbooru", "s"), "sensitive")
        self.assertEqual(normalize_rating("gelbooru", "s"), "general")
        self.assertEqual(normalize_rating("gelbooru", "explicit"), "explicit")

    def test_safe_folder_name_windows(self):
        self.assertEqual(safe_folder_name('foo:bar/baz*qux'), 'foo_bar_baz_qux')

    def test_default_filter_general_only(self):
        opt = SearchOptions(tags="landscape")
        f = PostFilter(opt)
        general = Post("danbooru", "1", "a", "https://x/a.jpg", "jpg", 100, 100, "g", "landscape")
        sensitive = Post("danbooru", "2", "b", "https://x/b.jpg", "jpg", 100, 100, "s", "landscape")
        self.assertTrue(f.accepts(general)[0])
        self.assertFalse(f.accepts(sensitive)[0])

    def test_resolution_filter(self):
        opt = SearchOptions(tags="x", any_size=False, target_width=1920, target_height=1080, size_error=0.05)
        f = PostFilter(opt)
        okay = Post("danbooru", "1", "a", "https://x/a.jpg", "jpg", 1920, 1080, "g", "x")
        portrait = Post("danbooru", "2", "b", "https://x/b.jpg", "jpg", 2000, 2000, "g", "x")
        self.assertTrue(f.accepts(okay)[0])
        self.assertFalse(f.accepts(portrait)[0])


if __name__ == "__main__":
    unittest.main()
