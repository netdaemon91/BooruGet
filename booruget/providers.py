from __future__ import annotations

import html as html_lib
import os
import re
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import Credentials, Post


USER_AGENT = "BooruGet/2.4 (+https://github.com/netdaemon91/BooruGet)"


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    id: str
    label: str
    family: str
    site_url: str
    api_url: str
    default_enabled: bool = False
    credentials_profile: str = ""
    adult_site: bool = False


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        "danbooru", "Danbooru", "danbooru",
        "https://danbooru.donmai.us/",
        "https://danbooru.donmai.us/posts.json",
        True, "danbooru",
    ),
    ProviderSpec(
        "gelbooru", "Gelbooru", "gelbooru_v02",
        "https://gelbooru.com/",
        "https://gelbooru.com/index.php",
        True, "gelbooru",
    ),
    ProviderSpec(
        "safebooru", "Safebooru", "gelbooru_v02",
        "https://safebooru.org/",
        "https://safebooru.org/index.php",
    ),
    ProviderSpec(
        "rule34", "Rule34.xxx", "gelbooru_v02",
        "https://rule34.xxx/",
        "https://api.rule34.xxx/index.php",
        adult_site=True,
    ),
    ProviderSpec(
        "yandere", "yande.re", "moebooru",
        "https://yande.re/",
        "https://yande.re/post.json",
    ),
    ProviderSpec(
        "konachan", "Konachan", "moebooru",
        "https://konachan.com/",
        "https://konachan.com/post.json",
        adult_site=True,
    ),
    ProviderSpec(
        "sakugabooru", "Sakugabooru", "moebooru",
        "https://www.sakugabooru.com/",
        "https://www.sakugabooru.com/post.json",
    ),
)

PROVIDER_MAP = {spec.id: spec for spec in PROVIDER_SPECS}
DEFAULT_PROVIDER_IDS = tuple(spec.id for spec in PROVIDER_SPECS if spec.default_enabled)


def provider_ids() -> tuple[str, ...]:
    return tuple(spec.id for spec in PROVIDER_SPECS)


def provider_label(provider_id: str) -> str:
    spec = PROVIDER_MAP.get(provider_id)
    return spec.label if spec else provider_id


def provider_referer(provider_id: str) -> str:
    spec = PROVIDER_MAP.get(provider_id)
    return spec.site_url if spec else "https://gelbooru.com/"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/xml;q=0.8, text/html;q=0.7, */*;q=0.5",
    })
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _extension(url: str, fallback: str = "jpg") -> str:
    ext = os.path.splitext(urlparse(url).path)[1].lstrip(".").lower()
    return ext if ext and len(ext) <= 8 else fallback


def _to_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class _AnonymousApiBlocked(ProviderError):
    pass


class _GelbooruListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.posts: list[dict[str, str]] = []
        self._post_id = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        data = {str(key).lower(): (value or "") for key, value in attrs}
        tag = tag.lower()
        if tag == "a":
            href = html_lib.unescape(data.get("href", "")).replace("&amp;", "&")
            if "page=post" in href and "s=view" in href:
                match = re.search(r"(?:[?&])id=(\d+)", href)
                self._post_id = match.group(1) if match else ""
            else:
                self._post_id = ""
            return

        if tag == "img" and self._post_id:
            src = html_lib.unescape(data.get("src", ""))
            if src:
                self.posts.append({
                    "id": self._post_id,
                    "preview_url": src,
                    "title": html_lib.unescape(data.get("title", "")),
                })
            self._post_id = ""

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self._post_id = ""


class _GelbooruDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.original_url = ""
        self.image_url = ""
        self._anchor_href = ""
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        data = {str(key).lower(): (value or "") for key, value in attrs}
        tag = tag.lower()
        if tag == "meta":
            key = (data.get("property") or data.get("name") or "").strip().lower()
            content = html_lib.unescape(data.get("content", "")).strip()
            if key and content:
                self.meta[key] = content
        elif tag == "a":
            self._anchor_href = html_lib.unescape(data.get("href", "")).strip()
            self._anchor_text = []
        elif tag == "img" and data.get("id", "").lower() == "image":
            self.image_url = html_lib.unescape(data.get("src", "")).strip()

    def handle_data(self, data: str) -> None:
        if self._anchor_href:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._anchor_href:
            return
        text = " ".join(self._anchor_text).strip().lower()
        if "original image" in text or text == "original":
            self.original_url = self._anchor_href
        self._anchor_href = ""
        self._anchor_text = []


class Provider(ABC):
    name: str
    label: str
    site_url: str
    delay_seconds: float = 1.0

    def __init__(self, credentials: Credentials, verbose: bool = False):
        self.credentials = credentials
        self.verbose = verbose
        self.session = _session()

    @abstractmethod
    def iter_posts(self, tags: str, max_pages: int = 0) -> Iterator[Post]:
        raise NotImplementedError

    def _sleep(self) -> None:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)


class DanbooruProvider(Provider):
    name = "danbooru"
    label = "Danbooru"
    api_url = "https://danbooru.donmai.us/posts.json"
    site_url = "https://danbooru.donmai.us/"
    per_page = 100
    delay_seconds = 1.0

    def iter_posts(self, tags: str, max_pages: int = 0) -> Iterator[Post]:
        page = 1
        while True:
            if max_pages and page > max_pages:
                return
            params = {"tags": tags, "limit": self.per_page, "page": page}
            auth = None
            if self.credentials.danbooru_username and self.credentials.danbooru_api_key:
                auth = (
                    self.credentials.danbooru_username,
                    self.credentials.danbooru_api_key,
                )

            if self.verbose:
                mode = "authenticated" if auth else "anonymous"
                print(f"[Danbooru] API page {page} ({mode})")
            try:
                response = self.session.get(
                    self.api_url,
                    params=params,
                    auth=auth,
                    timeout=(10, 40),
                )
            except requests.RequestException as exc:
                raise ProviderError(f"Danbooru connection failed: {exc}") from exc

            if response.status_code in (401, 403):
                raise ProviderError(
                    "Danbooru rejected the credentials or this search is not "
                    "available to the current account."
                )
            if response.status_code == 429:
                raise ProviderError(
                    "Danbooru rate limit reached. Try again later or reduce "
                    "request frequency."
                )
            try:
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise ProviderError(
                    f"Danbooru returned an invalid API response "
                    f"(HTTP {response.status_code})."
                ) from exc

            posts = payload.get("posts", []) if isinstance(payload, dict) else payload
            if not isinstance(posts, list) or not posts:
                return

            for item in posts:
                url = item.get("file_url") or item.get("large_file_url")
                if not url:
                    continue
                url = urljoin(self.site_url, str(url))
                md5 = str(item.get("md5") or "")
                post_id = str(item.get("id") or md5)
                yield Post(
                    provider=self.name,
                    post_id=post_id,
                    md5=md5,
                    file_url=url,
                    file_ext=str(item.get("file_ext") or _extension(url)),
                    width=_to_int(item.get("image_width")),
                    height=_to_int(item.get("image_height")),
                    rating=str(item.get("rating") or ""),
                    tags=str(item.get("tag_string") or ""),
                    preview_url=urljoin(
                        self.site_url,
                        str(
                            item.get("preview_file_url")
                            or item.get("large_file_url")
                            or url
                        ),
                    ),
                    post_url=urljoin(self.site_url, f"posts/{post_id}"),
                )

            if len(posts) < self.per_page:
                return
            page += 1
            self._sleep()


class GelbooruV02Provider(Provider):
    per_page = 100
    delay_seconds = 1.0
    public_detail_delay_seconds = 0.15

    def __init__(
        self,
        spec: ProviderSpec,
        credentials: Credentials,
        verbose: bool = False,
    ):
        super().__init__(credentials, verbose)
        self.spec = spec
        self.name = spec.id
        self.label = spec.label
        self.site_url = spec.site_url
        self.api_url = spec.api_url

    def _has_credentials(self) -> bool:
        return bool(
            self.spec.credentials_profile == "gelbooru"
            and self.credentials.gelbooru_api_key
            and self.credentials.gelbooru_user_id
        )

    def iter_posts(self, tags: str, max_pages: int = 0) -> Iterator[Post]:
        if self._has_credentials():
            yield from self._iter_api(tags, max_pages)
            return

        try:
            yield from self._iter_api(tags, max_pages)
        except _AnonymousApiBlocked as exc:
            if self.verbose:
                print(f"[{self.label}] anonymous DAPI unavailable: {exc}")
                print(f"[{self.label}] using public HTML fallback")
            yield from self._iter_public(tags, max_pages)

    def _iter_api(self, tags: str, max_pages: int = 0) -> Iterator[Post]:
        page = 0
        while True:
            if max_pages and page >= max_pages:
                return
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": self.per_page,
                "pid": page,
                "tags": tags,
            }
            if self._has_credentials():
                params["api_key"] = self.credentials.gelbooru_api_key
                params["user_id"] = self.credentials.gelbooru_user_id

            if self.verbose:
                mode = "authenticated" if self._has_credentials() else "anonymous"
                print(f"[{self.label}] API page {page} ({mode})")
            try:
                response = self.session.get(
                    self.api_url,
                    params=params,
                    timeout=(10, 40),
                )
            except requests.RequestException as exc:
                raise ProviderError(
                    f"{self.label} connection failed: {exc}"
                ) from exc

            if response.status_code in (401, 403):
                if not self._has_credentials():
                    raise _AnonymousApiBlocked(f"HTTP {response.status_code}")
                raise ProviderError(
                    f"{self.label} rejected the configured API credentials."
                )
            if response.status_code == 429:
                raise ProviderError(f"{self.label} rate limit reached.")
            if not response.ok:
                raise ProviderError(
                    f"{self.label} API returned HTTP {response.status_code}."
                )

            posts, total = self._parse_response(response)
            if not posts:
                return
            for item in posts:
                post = self._post_from_api(item)
                if post is not None:
                    yield post

            page += 1
            if len(posts) < self.per_page:
                return
            if total is not None and page * self.per_page >= total:
                return
            self._sleep()

    def _post_from_api(self, item: dict) -> Post | None:
        raw_url = str(item.get("file_url") or item.get("source") or "")
        if not raw_url:
            return None
        url = self._normalize_file_url(raw_url)
        md5 = str(item.get("md5") or "")
        post_id = str(item.get("id") or md5)
        preview = str(item.get("preview_url") or item.get("sample_url") or url)
        return Post(
            provider=self.name,
            post_id=post_id,
            md5=md5,
            file_url=url,
            file_ext=str(item.get("file_ext") or _extension(url)),
            width=_to_int(item.get("width") or item.get("image_width")),
            height=_to_int(item.get("height") or item.get("image_height")),
            rating=str(item.get("rating") or ""),
            tags=str(item.get("tags") or item.get("tag_string") or ""),
            preview_url=urljoin(self.site_url, preview),
            post_url=urljoin(
                self.site_url,
                f"index.php?page=post&s=view&id={post_id}",
            ),
        )

    def _normalize_file_url(self, value: str) -> str:
        url = urljoin(self.site_url, value)
        if self.name != "rule34" or _extension(url) in {"webm", "mp4"}:
            return url
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host.endswith("rule34.xxx") and host != "wimg.rule34.xxx":
            netloc = "wimg.rule34.xxx"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))
        return url

    def _iter_public(self, tags: str, max_pages: int = 0) -> Iterator[Post]:
        offset = 0
        page_no = 0
        seen_ids: set[str] = set()
        public_url = urljoin(self.site_url, "index.php")

        while True:
            if max_pages and page_no >= max_pages:
                return
            params = {
                "page": "post",
                "s": "list",
                "tags": tags.strip() or "all",
                "pid": offset,
            }
            if self.verbose:
                print(f"[{self.label}] public page offset {offset}")
            try:
                response = self.session.get(
                    public_url,
                    params=params,
                    timeout=(10, 40),
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise ProviderError(
                    f"{self.label} public search failed: {exc}"
                ) from exc

            parser = _GelbooruListingParser()
            parser.feed(response.text)
            records = [
                record
                for record in parser.posts
                if record["id"] not in seen_ids
            ]
            if not records:
                return

            for record in records:
                seen_ids.add(record["id"])
                post = self._public_post(record)
                if post is not None:
                    yield post
                if self.public_detail_delay_seconds > 0:
                    time.sleep(self.public_detail_delay_seconds)

            page_no += 1
            offset += len(records)

    def _public_post(self, record: dict[str, str]) -> Post | None:
        post_id = record["id"]
        public_url = urljoin(self.site_url, "index.php")
        try:
            response = self.session.get(
                public_url,
                params={"page": "post", "s": "view", "id": post_id},
                timeout=(10, 40),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            if self.verbose:
                print(f"[{self.label}] skip public post {post_id}: {exc}")
            return None

        parser = _GelbooruDetailParser()
        parser.feed(response.text)
        file_url = (
            parser.original_url
            or parser.meta.get("og:image", "")
            or parser.image_url
        )
        if not file_url:
            if self.verbose:
                print(
                    f"[{self.label}] skip public post {post_id}: "
                    "original image URL not found"
                )
            return None

        file_url = urljoin(self.site_url, html_lib.unescape(file_url))
        preview_url = urljoin(
            self.site_url,
            record.get("preview_url", ""),
        )
        title = record.get("title", "")
        plain = self._plain_text(response.text)
        rating = self._rating_from_text(title) or self._rating_from_text(plain)
        tags = self._tags_from_title(title)
        if not tags:
            keywords = parser.meta.get("keywords", "")
            if keywords:
                tags = " ".join(
                    part.strip().replace(" ", "_")
                    for part in keywords.split(",")
                    if part.strip()
                )

        width = self._int_meta(parser.meta.get("og:image:width"))
        height = self._int_meta(parser.meta.get("og:image:height"))
        if width <= 0 or height <= 0:
            match = re.search(
                r"\b(?:Size|Dimensions)\s*:\s*(\d+)\s*[x×]\s*(\d+)",
                plain,
                re.IGNORECASE,
            )
            if match:
                width = width or int(match.group(1))
                height = height or int(match.group(2))

        md5 = self._md5_from_urls(preview_url, file_url)
        return Post(
            provider=self.name,
            post_id=post_id,
            md5=md5,
            file_url=file_url,
            file_ext=_extension(file_url),
            width=width,
            height=height,
            rating=rating,
            tags=tags,
            preview_url=preview_url or file_url,
            post_url=urljoin(
                self.site_url,
                f"index.php?page=post&s=view&id={post_id}",
            ),
        )

    @staticmethod
    def _rating_from_text(value: str) -> str:
        match = re.search(
            r"(?:^|\s)rating\s*:\s*"
            r"(general|safe|sensitive|questionable|explicit|[gsqe])\b",
            value or "",
            re.IGNORECASE,
        )
        return match.group(1).lower() if match else ""

    @staticmethod
    def _tags_from_title(value: str) -> str:
        value = html_lib.unescape(value or "").strip()
        if not value:
            return ""
        marker = re.search(
            r"\s+(?:score|rating|user)\s*:",
            value,
            re.IGNORECASE,
        )
        return value[:marker.start()].strip() if marker else value

    @staticmethod
    def _plain_text(value: str) -> str:
        value = re.sub(
            r"(?is)<script\b.*?</script>|<style\b.*?</style>",
            " ",
            value or "",
        )
        value = re.sub(r"(?s)<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", html_lib.unescape(value)).strip()

    @staticmethod
    def _int_meta(value: str | None) -> int:
        return _to_int(value)

    @staticmethod
    def _md5_from_urls(*urls: str) -> str:
        for url in urls:
            match = re.search(r"(?i)([0-9a-f]{32})", url or "")
            if match:
                return match.group(1).lower()
        return ""

    def _parse_response(
        self,
        response: requests.Response,
    ) -> tuple[list[dict], int | None]:
        try:
            payload = response.json()
            if isinstance(payload, str):
                self._handle_api_refusal(payload)
            if isinstance(payload, list):
                return payload, None
            if isinstance(payload, dict):
                if payload.get("success") is False:
                    self._handle_api_refusal(
                        str(
                            payload.get("reason")
                            or payload.get("message")
                            or f"{self.label} API refused the request"
                        )
                    )
                if "post" not in payload and any(
                    key in payload for key in ("reason", "message", "error")
                ):
                    self._handle_api_refusal(
                        str(
                            payload.get("reason")
                            or payload.get("message")
                            or payload.get("error")
                        )
                    )
                posts = payload.get("post", [])
                if isinstance(posts, dict):
                    posts = [posts]
                attrs = payload.get("@attributes", {})
                total_raw = (
                    attrs.get("count")
                    if isinstance(attrs, dict)
                    else None
                )
                total = (
                    int(total_raw)
                    if str(total_raw or "").isdigit()
                    else None
                )
                return posts if isinstance(posts, list) else [], total
        except ValueError:
            pass

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise ProviderError(
                f"{self.label} returned neither valid JSON nor XML."
            ) from exc

        if root.tag.lower() == "error":
            self._handle_api_refusal(
                root.text or f"{self.label} API refused the request"
            )

        total_raw = root.attrib.get("count")
        total = (
            int(total_raw)
            if str(total_raw or "").isdigit()
            else None
        )
        return [
            dict(child.attrib)
            for child in root
            if child.tag == "post"
        ], total

    def _handle_api_refusal(self, reason: str) -> None:
        reason = (reason or f"{self.label} API refused the request").strip()
        lower = reason.lower()
        if not self._has_credentials() and any(
            token in lower
            for token in ("auth", "api key", "api_key", "anonymous", "login")
        ):
            raise _AnonymousApiBlocked(reason)
        raise ProviderError(f"{self.label} API refused the request: {reason}")


class GelbooruProvider(GelbooruV02Provider):
    """Compatibility wrapper for the original public class name."""

    def __init__(self, credentials: Credentials, verbose: bool = False):
        super().__init__(PROVIDER_MAP["gelbooru"], credentials, verbose)


class MoebooruProvider(Provider):
    per_page = 100
    delay_seconds = 0.5

    def __init__(
        self,
        spec: ProviderSpec,
        credentials: Credentials,
        verbose: bool = False,
    ):
        super().__init__(credentials, verbose)
        self.spec = spec
        self.name = spec.id
        self.label = spec.label
        self.site_url = spec.site_url
        self.api_url = spec.api_url

    def iter_posts(self, tags: str, max_pages: int = 0) -> Iterator[Post]:
        page = 1
        while True:
            if max_pages and page > max_pages:
                return
            params = {
                "tags": tags,
                "limit": self.per_page,
                "page": page,
            }
            if self.verbose:
                print(f"[{self.label}] API page {page}")
            try:
                response = self.session.get(
                    self.api_url,
                    params=params,
                    timeout=(10, 40),
                )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as exc:
                raise ProviderError(
                    f"{self.label} connection failed: {exc}"
                ) from exc
            except ValueError as exc:
                raise ProviderError(
                    f"{self.label} returned invalid JSON."
                ) from exc

            if isinstance(payload, dict):
                posts = payload.get("posts", payload.get("post", []))
            else:
                posts = payload
            if not isinstance(posts, list) or not posts:
                return

            for item in posts:
                post = self._post_from_api(item)
                if post is not None:
                    yield post

            if len(posts) < self.per_page:
                return
            page += 1
            self._sleep()

    def _post_from_api(self, item: dict) -> Post | None:
        raw_url = str(item.get("file_url") or "")
        if not raw_url:
            return None
        url = urljoin(self.site_url, raw_url)
        md5 = str(item.get("md5") or "")
        post_id = str(item.get("id") or md5)
        preview = str(
            item.get("preview_url")
            or item.get("sample_url")
            or url
        )
        return Post(
            provider=self.name,
            post_id=post_id,
            md5=md5,
            file_url=url,
            file_ext=str(item.get("file_ext") or _extension(url)),
            width=_to_int(item.get("width")),
            height=_to_int(item.get("height")),
            rating=str(item.get("rating") or ""),
            tags=str(item.get("tags") or ""),
            preview_url=urljoin(self.site_url, preview),
            post_url=urljoin(self.site_url, f"post/show/{post_id}"),
        )


def create_provider(
    provider_id: str,
    credentials: Credentials,
    verbose: bool = False,
) -> Provider:
    spec = PROVIDER_MAP.get(provider_id)
    if spec is None:
        raise ValueError(f"Unknown provider: {provider_id}")
    if spec.family == "danbooru":
        return DanbooruProvider(credentials, verbose)
    if spec.family == "gelbooru_v02":
        return GelbooruV02Provider(spec, credentials, verbose)
    if spec.family == "moebooru":
        return MoebooruProvider(spec, credentials, verbose)
    raise ValueError(f"Unsupported provider family: {spec.family}")
