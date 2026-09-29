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


def response(payload, status=200):
    value = requests.Response()
    value.status_code = status
    value._content = json.dumps(payload).encode("utf-8")
    value.headers["Content-Type"] = "application/json"
    return value


def html_response(text, status=200):
    value = requests.Response()
    value.status_code = status
    value._content = text.encode("utf-8")
    value.headers["Content-Type"] = "text/html; charset=utf-8"
    value.encoding = "utf-8"
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

    def test_gelbooru_anonymous_api_401_falls_back_to_public_html(self):
        provider = GelbooruProvider(Credentials())
        provider.public_detail_delay_seconds = 0
        replies = iter([
            response({"error": "auth"}, status=401),
            html_response('<a href="index.php?page=post&amp;s=view&amp;id=77"><img src="https://img.example/thumbnail_0123456789abcdef0123456789abcdef.jpg" title="sunset score:1 rating:general"/></a>'),
            html_response('<meta property="og:image" content="https://img.example/original.jpg"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="800">'),
        ])
        provider.session.get = lambda *args, **kwargs: next(replies)
        post = next(provider.iter_posts("sunset", max_pages=1))
        self.assertEqual(post.post_id, "77")
        self.assertEqual(post.file_url, "https://img.example/original.jpg")
        self.assertEqual(post.rating, "general")
        self.assertEqual(post.tags, "sunset")
        self.assertEqual((post.width, post.height), (1200, 800))

    def test_gelbooru_auth_refusal_string_uses_public_fallback(self):
        provider = GelbooruProvider(Credentials())
        provider.public_detail_delay_seconds = 0
        replies = iter([
            response("Missing authentication. API key and user ID required."),
            html_response('<a href="index.php?page=post&amp;s=view&amp;id=88"><img src="https://img.example/thumb.jpg" title="clouds rating:safe"/></a>'),
            html_response('<meta property="og:image" content="https://img.example/clouds.png">'),
        ])
        provider.session.get = lambda *args, **kwargs: next(replies)
        post = next(provider.iter_posts("clouds", max_pages=1))
        self.assertEqual(post.post_id, "88")
        self.assertEqual(post.file_url, "https://img.example/clouds.png")

    def test_danbooru_credentials_remain_optional(self):
        provider = DanbooruProvider(Credentials())
        calls = []
        def fake_get(*args, **kwargs):
            calls.append(kwargs)
            return response([{"id":9,"md5":"abc","file_url":"/data/test.jpg","file_ext":"jpg","image_width":640,"image_height":480,"rating":"g","tag_string":"test"}])
        provider.session.get = fake_get
        next(provider.iter_posts("test", max_pages=1))
        self.assertIsNone(calls[0]["auth"])


if __name__ == "__main__":
    unittest.main()
