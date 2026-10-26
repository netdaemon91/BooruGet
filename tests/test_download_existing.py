import tempfile
import unittest
from pathlib import Path

from booruget.downloader import DownloadRunner
from booruget.models import Credentials, Post, SearchOptions


class DownloadExistingResultsTests(unittest.TestCase):
    def test_download_posts_does_not_search_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            options = SearchOptions(
                tags="snapshot",
                output_dir=tmp,
                workers=2,
                dry_run=True,
            )
            events = []
            runner = DownloadRunner(
                options,
                Credentials(),
                log=lambda _value: None,
                event_callback=lambda event, payload: events.append(
                    (event, payload)
                ),
            )
            downloaded = []

            def fake_download(post, destination):
                downloaded.append((post.post_id, Path(destination)))
                return "downloaded"

            runner._download_one = fake_download
            posts = [
                Post(
                    "danbooru", "1", "a",
                    "https://example/a.jpg", "jpg",
                    100, 100, "g", "snapshot",
                ),
                Post(
                    "gelbooru", "2", "b",
                    "https://example/b.jpg", "jpg",
                    100, 100, "general", "snapshot",
                ),
            ]

            stats = runner.download_posts(posts)

            self.assertEqual(stats.seen, 2)
            self.assertEqual(stats.accepted, 2)
            self.assertEqual(stats.downloaded, 2)
            self.assertEqual(
                {post_id for post_id, _ in downloaded},
                {"1", "2"},
            )
            self.assertFalse(
                any(event == "searching" for event, _ in events)
            )
            self.assertEqual(
                sum(event == "download_queued" for event, _ in events),
                2,
            )


if __name__ == "__main__":
    unittest.main()
