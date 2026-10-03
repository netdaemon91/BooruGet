import unittest

from booruget.cli import _selected_providers, build_parser
from booruget.downloader import resolve_provider_ids
from booruget.models import SearchOptions


class MultiBooruTests(unittest.TestCase):
    def test_legacy_search_options_keep_old_defaults(self):
        options = SearchOptions(tags="landscape")
        self.assertEqual(
            resolve_provider_ids(options),
            ["danbooru", "gelbooru"],
        )

    def test_explicit_provider_ids_override_legacy_flags(self):
        options = SearchOptions(
            tags="landscape",
            use_danbooru=False,
            use_gelbooru=False,
            provider_ids={"yandere", "safebooru"},
        )
        self.assertEqual(
            resolve_provider_ids(options),
            ["safebooru", "yandere"],
        )

    def test_cli_provider_selection(self):
        args = build_parser().parse_args([
            "--providers",
            "konachan",
            "sakugabooru",
            "--",
            "tag",
        ])
        self.assertEqual(
            _selected_providers(args),
            {"konachan", "sakugabooru"},
        )

    def test_cli_all_providers(self):
        args = build_parser().parse_args([
            "--all-providers",
            "tag",
        ])
        self.assertEqual(len(_selected_providers(args)), 10)


if __name__ == "__main__":
    unittest.main()
