from __future__ import annotations

from pathlib import Path

from .models import Post, SearchOptions


ALL_RATINGS = {"general", "sensitive", "questionable", "explicit"}


def normalize_rating(provider: str, value: str) -> str:
    value = (value or "").strip().lower()
    if provider == "danbooru":
        return {
            "g": "general",
            "general": "general",
            "s": "sensitive",
            "sensitive": "sensitive",
            "q": "questionable",
            "questionable": "questionable",
            "e": "explicit",
            "explicit": "explicit",
        }.get(value, value or "unknown")

    return {
        "g": "general",
        "general": "general",
        "safe": "general",
        "s": "general",
        "sensitive": "sensitive",
        "q": "questionable",
        "questionable": "questionable",
        "e": "explicit",
        "explicit": "explicit",
    }.get(value, value or "unknown")


class PostFilter:
    def __init__(self, options: SearchOptions, project_root: Path | None = None):
        self.options = options
        self.project_root = project_root or Path.cwd()
        self.global_blacklist = self._load_lines(Path(".config/global_blacklist"))
        self.nsfw_blacklist = self._load_lines(Path(".config/nsfw_blacklist"))
        self.md5_global_blacklist = set(self._load_lines(Path(".config/md5_global_blacklist")))
        self.md5_nsfw_blacklist = set(self._load_lines(Path(".config/md5_nsfw_blacklist")))
        self.md5_nsfw_whitelist = set(self._load_lines(Path(".config/md5_nsfw_whitelist")))

    def _load_lines(self, relative: Path) -> list[str]:
        path = self.project_root / relative
        if not path.exists():
            return []
        return [
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def accepts(self, post: Post) -> tuple[bool, str]:
        if post.md5 and post.md5 in self.md5_global_blacklist:
            return False, "MD5 is globally blacklisted"

        rating = normalize_rating(post.provider, post.rating)
        allowed = self.options.allowed_ratings
        if allowed is None:
            allowed = ALL_RATINGS if self.options.allow_nsfw else {"general"}
        if post.md5 in self.md5_nsfw_whitelist:
            allowed = ALL_RATINGS
        if post.md5 in self.md5_nsfw_blacklist and not self.options.allow_nsfw:
            return False, "MD5 is in the adult-content blacklist"
        if rating not in allowed:
            return False, f"rating {rating!r} is disabled"

        tags = set((post.tags or "").split())
        for tag in self.global_blacklist:
            if tag in tags:
                return False, f"tag {tag!r} is globally blacklisted"
        if not self.options.allow_nsfw:
            for tag in self.nsfw_blacklist:
                if tag in tags:
                    return False, f"tag {tag!r} is in the adult-content blacklist"

        if not self._size_ok(post):
            return False, "resolution/aspect ratio filter"
        return True, "accepted"

    def _size_ok(self, post: Post) -> bool:
        o = self.options
        if o.any_size or (o.target_width <= 0 and o.target_height <= 0):
            return True
        if post.width <= 0 or post.height <= 0:
            return False

        error = max(0.0, o.size_error)
        if o.target_width > 0 and post.width < o.target_width * (1.0 - error):
            return False
        if o.target_height > 0 and post.height < o.target_height * (1.0 - error):
            return False

        if o.target_width > 0 and o.target_height > 0:
            wanted_ratio = o.target_width / o.target_height
            actual_ratio = post.width / post.height
            tolerance = wanted_ratio * error
            if not (wanted_ratio - tolerance <= actual_ratio <= wanted_ratio + tolerance):
                return False
        return True
