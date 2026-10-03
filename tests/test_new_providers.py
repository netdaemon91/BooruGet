import unittest
from unittest.mock import Mock

from booruget.models import Credentials
from booruget.providers import create_provider, ProviderError
from test_providers import response


class NewProviderTests(unittest.TestCase):
    def test_e621_nested_file_tags_and_safe_rating(self):
        provider = create_provider("e621", Credentials())
        provider.session.get = Mock(return_value=response({"posts": [{
            "id": 42, "file": {"url": "https://example.org/a.png", "md5": "abc",
                                "ext": "png", "width": 100, "height": 200},
            "tags": {"general": ["landscape"], "artist": ["someone"]},
            "rating": "s", "preview": {"url": "https://example.org/thumb.jpg"},
        }]}))
        posts = list(provider.iter_posts("landscape", max_pages=1))
        self.assertEqual(posts[0].tags, "landscape someone")
        self.assertEqual(posts[0].post_url, "https://e621.net/posts/42")
        self.assertEqual(posts[0].width, 100)
        self.assertIsNone(provider._post_from_api({"file": {"url": None}}))

    def test_philomena_tags_ratings_and_pagination(self):
        provider = create_provider("derpibooru", Credentials())
        provider.per_page = 1
        provider.delay_seconds = 0
        image = {"id": 1, "tags": ["safe", "artist: some name"], "format": "png",
                 "representations": {"full": "https://example.org/a.png"}}
        provider.session.get = Mock(side_effect=[response({"images": [image], "total": 2}),
                                                 response({"images": [dict(image, id=2)], "total": 2})])
        posts = list(provider.iter_posts("safe, landscape"))
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].rating, "general")
        self.assertEqual(posts[0].tags, "safe artist:_some_name")
        self.assertEqual(provider.session.get.call_args.kwargs["params"]["page"], 2)
        self.assertEqual(provider.session.get.call_args.kwargs["params"]["q"], "safe, landscape")
        self.assertIsNone(provider._post_from_api({"hidden_from_users": True}))
        self.assertEqual(provider._post_from_api(dict(image, tags=["explicit", "safe"])).rating, "explicit")

    def test_philomena_refusal_is_not_an_empty_search(self):
        provider = create_provider("derpibooru", Credentials())
        provider.session.get = Mock(return_value=response({"error": "invalid query"}))
        with self.assertRaises(ProviderError):
            list(provider.iter_posts("invalid"))


class PahealTests(unittest.TestCase):
    def test_real_xml_and_extensionless_cdn_urls(self):
        provider = create_provider("paheal", Credentials())
        xml = '<posts count="2" offset="0"><post id="1924424" md5="dacf852dc916f78b2a6c83779e5f0eb8" file_name="tumblr_oa6rgjmcr21qfbon7o1_1280.jpg" file_url="https://r34i.paheal-cdn.net/da/cf/dacf852dc916f78b2a6c83779e5f0eb8" height="1690" width="1200" preview_url="https://r34t.paheal.net/da/cf/dacf852dc916f78b2a6c83779e5f0eb8" rating="?" tags="inanimate landscape view" /></posts>'
        from test_providers import html_response
        provider.session.get = Mock(return_value=html_response(xml))
        post = list(provider.iter_posts("landscape", max_pages=1))[0]
        self.assertEqual(post.file_ext, "jpg")
        self.assertEqual(post.width, 1200)
        self.assertEqual(post.post_url, "https://rule34.paheal.net/post/view/1924424")
        self.assertEqual(post.rating, "explicit")
        from booruget.filters import PostFilter
        from booruget.models import SearchOptions
        self.assertFalse(PostFilter(SearchOptions(tags="landscape")).accepts(post)[0])
        self.assertTrue(PostFilter(SearchOptions(tags="landscape", allow_nsfw=True)).accepts(post)[0])
        # The CDN has no suffix, so non-JPEG files must use file_name as well.
        provider.session.get = Mock(return_value=html_response(xml.replace('.jpg', '.png')))
        self.assertEqual(list(provider.iter_posts("landscape", max_pages=1))[0].file_ext, "png")

    def test_html_replacement_page_is_an_error(self):
        from test_providers import html_response
        provider = create_provider("paheal", Credentials())
        provider.session.get = Mock(return_value=html_response('<html>Site Unavailable</html>'))
        with self.assertRaises(ProviderError):
            list(provider.iter_posts("landscape"))
