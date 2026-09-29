import json
import unittest

import requests

from booruget.models import Credentials
from booruget.providers import DanbooruProvider, GelbooruProvider


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def response(payload):
    value = requests.Response()
    value.status_code = 200
    value._content = json.dumps(payload).encode("utf-8")
    value.headers["Content-Type"] = "application/json"
    return value


class ProviderParsingTests(unittest.TestCase):
    def test_gelbooru_current_object_shape(self):
        provider = GelbooruProvider(Credentials())
        posts, total = provider._parse_response(FakeResponse({
            "@attributes": {"count": 1, "offset": 0, "limit": 100},
            "post": [{"id": 123, "file_url": "https://example/a.jpg"}],
        }))
        self.assertEqual(total, 1)
        self.assertEqual(posts[0]["id"], 123)

    def test_gelbooru_list_shape(self):
        provider = GelbooruProvider(Credentials())
        posts, total = provider._parse_response(FakeResponse([{"id": 1}]))
        self.assertIsNone(total)
        self.assertEqual(posts[0]["id"], 1)

    def test_danbooru_post_links_for_gui_preview(self):
        provider = DanbooruProvider(Credentials())
        provider.session.get = lambda *args, **kwargs: response([{
            "id": 42,
            "md5": "abc",
            "file_url": "/data/original.jpg",
            "preview_file_url": "/data/preview.jpg",
            "file_ext": "jpg",
            "image_width": 1200,
            "image_height": 800,
            "rating": "g",
            "tag_string": "landscape",
        }])
        post = next(provider.iter_posts("landscape", max_pages=1))
        self.assertEqual(post.preview_url, "https://danbooru.donmai.us/data/preview.jpg")
        self.assertEqual(post.post_url, "https://danbooru.donmai.us/posts/42")

    def test_gelbooru_post_links_for_gui_preview(self):
        provider = GelbooruProvider(Credentials())
        provider.session.get = lambda *args, **kwargs: response({
            "@attributes": {"count": 1},
            "post": [{
                "id": 77,
                "md5": "def",
                "file_url": "https://img.example/original.jpg",
                "preview_url": "https://img.example/preview.jpg",
                "width": 1000,
                "height": 700,
                "rating": "general",
                "tags": "sunset",
            }],
        })
        post = next(provider.iter_posts("sunset", max_pages=1))
        self.assertEqual(post.preview_url, "https://img.example/preview.jpg")
        self.assertIn("id=77", post.post_url)


if __name__ == "__main__":
    unittest.main()
