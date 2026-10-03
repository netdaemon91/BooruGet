import json
import unittest

import requests

from booruget.models import Credentials
from booruget.providers import (
    PROVIDER_MAP,
    PROVIDER_SPECS,
    DanbooruProvider,
    GelbooruProvider,
    GelbooruV02Provider,
    MoebooruProvider,
    create_provider,
)


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
    def test_registry_contains_initial_multibooru_set(self):
        self.assertEqual(
            [spec.id for spec in PROVIDER_SPECS],
            [
                "danbooru",
                "gelbooru",
                "safebooru",
                "rule34",
                "yandere",
                "konachan",
                "sakugabooru",
                "e621",
                "derpibooru",
                "paheal",
            ],
        )

    def test_registry_families(self):
        self.assertEqual(PROVIDER_MAP["safebooru"].family, "gelbooru_v02")
        self.assertEqual(PROVIDER_MAP["rule34"].family, "gelbooru_v02")
        self.assertEqual(PROVIDER_MAP["yandere"].family, "moebooru")
        self.assertEqual(PROVIDER_MAP["konachan"].family, "moebooru")
        self.assertEqual(PROVIDER_MAP["sakugabooru"].family, "moebooru")

    def test_factory_uses_shared_engines(self):
        self.assertIsInstance(
            create_provider("danbooru", Credentials()),
            DanbooruProvider,
        )
        self.assertIsInstance(
            create_provider("safebooru", Credentials()),
            GelbooruV02Provider,
        )
        self.assertIsInstance(
            create_provider("yandere", Credentials()),
            MoebooruProvider,
        )

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
        posts, total = provider._parse_response(
            FakeResponse([{"id": 1}])
        )
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
        self.assertEqual(
            post.preview_url,
            "https://danbooru.donmai.us/data/preview.jpg",
        )
        self.assertEqual(
            post.post_url,
            "https://danbooru.donmai.us/posts/42",
        )

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
        self.assertEqual(
            post.preview_url,
            "https://img.example/preview.jpg",
        )
        self.assertIn("id=77", post.post_url)

    def test_gelbooru_anonymous_api_401_falls_back_to_public_html(self):
        provider = GelbooruProvider(Credentials())
        provider.public_detail_delay_seconds = 0
        replies = iter([
            response({"error": "auth"}, status=401),
            html_response(
                '<a href="index.php?page=post&amp;s=view&amp;id=77">'
                '<img src="https://img.example/thumbnail_'
                '0123456789abcdef0123456789abcdef.jpg" '
                'title="sunset score:1 rating:general"/></a>'
            ),
            html_response(
                '<meta property="og:image" '
                'content="https://img.example/original.jpg">'
                '<meta property="og:image:width" content="1200">'
                '<meta property="og:image:height" content="800">'
            ),
        ])
        provider.session.get = lambda *args, **kwargs: next(replies)
        post = next(provider.iter_posts("sunset", max_pages=1))
        self.assertEqual(post.post_id, "77")
        self.assertEqual(
            post.file_url,
            "https://img.example/original.jpg",
        )
        self.assertEqual(post.rating, "general")
        self.assertEqual(post.tags, "sunset")
        self.assertEqual((post.width, post.height), (1200, 800))

    def test_gelbooru_auth_refusal_string_uses_public_fallback(self):
        provider = GelbooruProvider(Credentials())
        provider.public_detail_delay_seconds = 0
        replies = iter([
            response(
                "Missing authentication. API key and user ID required."
            ),
            html_response(
                '<a href="index.php?page=post&amp;s=view&amp;id=88">'
                '<img src="https://img.example/thumb.jpg" '
                'title="clouds rating:safe"/></a>'
            ),
            html_response(
                '<meta property="og:image" '
                'content="https://img.example/clouds.png">'
            ),
        ])
        provider.session.get = lambda *args, **kwargs: next(replies)
        post = next(provider.iter_posts("clouds", max_pages=1))
        self.assertEqual(post.post_id, "88")
        self.assertEqual(
            post.file_url,
            "https://img.example/clouds.png",
        )

    def test_danbooru_credentials_remain_optional(self):
        provider = DanbooruProvider(Credentials())
        calls = []

        def fake_get(*args, **kwargs):
            calls.append(kwargs)
            return response([{
                "id": 9,
                "md5": "abc",
                "file_url": "/data/test.jpg",
                "file_ext": "jpg",
                "image_width": 640,
                "image_height": 480,
                "rating": "g",
                "tag_string": "test",
            }])

        provider.session.get = fake_get
        next(provider.iter_posts("test", max_pages=1))
        self.assertIsNone(calls[0]["auth"])

    def test_safebooru_uses_gelbooru_v02_shape(self):
        provider = create_provider("safebooru", Credentials())
        self.assertIsInstance(provider, GelbooruV02Provider)
        provider.session.get = lambda *args, **kwargs: response({
            "@attributes": {"count": 1},
            "post": [{
                "id": 55,
                "md5": "123",
                "file_url": "https://safebooru.org/images/test.jpg",
                "preview_url": "https://safebooru.org/thumbnails/test.jpg",
                "width": 800,
                "height": 600,
                "rating": "s",
                "tags": "blue_sky",
            }],
        })
        post = next(provider.iter_posts("blue_sky", max_pages=1))
        self.assertEqual(post.provider, "safebooru")
        self.assertEqual(post.rating, "s")
        self.assertIn("safebooru.org", post.post_url)

    def test_rule34_rewrites_image_host_to_wimg(self):
        provider = create_provider("rule34", Credentials())
        post = provider._post_from_api({
            "id": 99,
            "md5": "123",
            "file_url": (
                "https://api-cdn.rule34.xxx/images/"
                "aa/bb/1234567890abcdef1234567890abcdef.jpg"
            ),
            "width": 100,
            "height": 100,
            "rating": "e",
            "tags": "test",
        })
        self.assertIsNotNone(post)
        self.assertEqual(
            post.file_url,
            "https://wimg.rule34.xxx/images/"
            "aa/bb/1234567890abcdef1234567890abcdef.jpg",
        )

    def test_moebooru_provider_parses_post_json(self):
        provider = create_provider("yandere", Credentials())
        provider.session.get = lambda *args, **kwargs: response([{
            "id": 1234,
            "md5": "abcdef",
            "file_url": "https://files.yande.re/image.jpg",
            "preview_url": "https://files.yande.re/preview.jpg",
            "width": 1920,
            "height": 1080,
            "rating": "s",
            "tags": "landscape sunset",
        }])
        post = next(provider.iter_posts("landscape", max_pages=1))
        self.assertEqual(post.provider, "yandere")
        self.assertEqual(post.post_id, "1234")
        self.assertEqual(post.width, 1920)
        self.assertEqual(post.rating, "s")
        self.assertEqual(
            post.post_url,
            "https://yande.re/post/show/1234",
        )


if __name__ == "__main__":
    unittest.main()
