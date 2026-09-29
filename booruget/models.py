from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Post:
    provider: str
    post_id: str
    md5: str
    file_url: str
    file_ext: str
    width: int
    height: int
    rating: str
    tags: str
    preview_url: str = ""
    post_url: str = ""


@dataclass(slots=True)
class Credentials:
    danbooru_username: str = ""
    danbooru_api_key: str = ""
    gelbooru_user_id: str = ""
    gelbooru_api_key: str = ""


@dataclass(slots=True)
class SearchOptions:
    tags: str
    output_dir: str = "downloads"
    use_danbooru: bool = True
    use_gelbooru: bool = True
    any_size: bool = True
    target_width: int = -1
    target_height: int = -1
    size_error: float = 0.05
    allow_nsfw: bool = False
    allowed_ratings: set[str] | None = None
    max_results: int = 0
    max_pages: int = 0
    workers: int = 4
    verbose: bool = False
    dry_run: bool = False
