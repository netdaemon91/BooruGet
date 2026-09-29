from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Iterator
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import Credentials, Post


USER_AGENT = "BooruGet/2.2 (+https://github.com/netdaemon91/BooruGet)"


class ProviderError(RuntimeError):
    pass


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, application/xml;q=0.8, */*;q=0.5"})
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


class Provider(ABC):
    name: str
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
                auth = (self.credentials.danbooru_username, self.credentials.danbooru_api_key)

            if self.verbose:
                print(f"[Danbooru] API page {page}")
            try:
                response = self.session.get(self.api_url, params=params, auth=auth, timeout=(10, 40))
            except requests.RequestException as exc:
                raise ProviderError(f"Danbooru connection failed: {exc}") from exc

            if response.status_code in (401, 403):
                raise ProviderError("Danbooru rejected the credentials or this search is not available to the current account.")
            if response.status_code == 429:
                raise ProviderError("Danbooru rate limit reached. Try again later or reduce request frequency.")
            try:
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise ProviderError(f"Danbooru returned an invalid API response (HTTP {response.status_code}).") from exc

            posts = payload.get("posts", []) if isinstance(payload, dict) else payload
            if not isinstance(posts, list) or not posts:
                return

            for item in posts:
                url = item.get("file_url") or item.get("large_file_url")
                if not url:
                    continue
                url = urljoin(self.site_url, url)
                md5 = str(item.get("md5") or "")
                yield Post(
                    provider=self.name,
                    post_id=str(item.get("id") or md5),
                    md5=md5,
                    file_url=url,
                    file_ext=str(item.get("file_ext") or _extension(url)),
                    width=int(item.get("image_width") or 0),
                    height=int(item.get("image_height") or 0),
                    rating=str(item.get("rating") or ""),
                    tags=str(item.get("tag_string") or ""),
                    preview_url=urljoin(self.site_url, str(item.get("preview_file_url") or item.get("large_file_url") or url)),
                    post_url=urljoin(self.site_url, f"posts/{item.get('id') or ''}"),
                )

            if len(posts) < self.per_page:
                return
            page += 1
            self._sleep()


class GelbooruProvider(Provider):
    name = "gelbooru"
    api_url = "https://gelbooru.com/index.php"
    site_url = "https://gelbooru.com/"
    per_page = 100
    delay_seconds = 1.0

    def iter_posts(self, tags: str, max_pages: int = 0) -> Iterator[Post]:
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
            if self.credentials.gelbooru_api_key and self.credentials.gelbooru_user_id:
                params["api_key"] = self.credentials.gelbooru_api_key
                params["user_id"] = self.credentials.gelbooru_user_id

            if self.verbose:
                print(f"[Gelbooru] API page {page}")
            try:
                response = self.session.get(self.api_url, params=params, timeout=(10, 40))
            except requests.RequestException as exc:
                raise ProviderError(f"Gelbooru connection failed: {exc}") from exc

            if response.status_code in (401, 403):
                raise ProviderError(
                    "Gelbooru rejected the request. Add user_id and api_key to booruget.ini if API authentication is required."
                )
            if response.status_code == 429:
                raise ProviderError("Gelbooru rate limit reached. Try again later.")
            if not response.ok:
                raise ProviderError(f"Gelbooru API returned HTTP {response.status_code}.")

            posts, total = self._parse_response(response)
            if not posts:
                return
            for item in posts:
                url = str(item.get("file_url") or item.get("source") or "")
                if not url:
                    continue
                url = urljoin(self.site_url, url)
                md5 = str(item.get("md5") or "")
                yield Post(
                    provider=self.name,
                    post_id=str(item.get("id") or md5),
                    md5=md5,
                    file_url=url,
                    file_ext=str(item.get("file_ext") or _extension(url)),
                    width=int(item.get("width") or item.get("image_width") or 0),
                    height=int(item.get("height") or item.get("image_height") or 0),
                    rating=str(item.get("rating") or ""),
                    tags=str(item.get("tags") or item.get("tag_string") or ""),
                    preview_url=urljoin(self.site_url, str(item.get("preview_url") or item.get("sample_url") or url)),
                    post_url=urljoin(self.site_url, f"index.php?page=post&s=view&id={item.get('id') or ''}"),
                )

            page += 1
            if len(posts) < self.per_page:
                return
            if total is not None and page * self.per_page >= total:
                return
            self._sleep()

    def _parse_response(self, response: requests.Response) -> tuple[list[dict], int | None]:
        try:
            payload = response.json()
            if isinstance(payload, list):
                return payload, None
            if isinstance(payload, dict):
                posts = payload.get("post", [])
                if isinstance(posts, dict):
                    posts = [posts]
                attrs = payload.get("@attributes", {})
                total_raw = attrs.get("count") if isinstance(attrs, dict) else None
                total = int(total_raw) if str(total_raw or "").isdigit() else None
                return posts if isinstance(posts, list) else [], total
        except ValueError:
            pass

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise ProviderError("Gelbooru returned neither valid JSON nor XML.") from exc
        total_raw = root.attrib.get("count")
        total = int(total_raw) if str(total_raw or "").isdigit() else None
        return [dict(child.attrib) for child in root if child.tag == "post"], total
