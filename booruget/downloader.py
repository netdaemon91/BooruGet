from __future__ import annotations

import os
import re
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, as_completed, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

import requests

from .filters import PostFilter
from .models import Credentials, Post, SearchOptions
from .providers import (
    PROVIDER_MAP,
    PROVIDER_SPECS,
    Provider,
    ProviderError,
    USER_AGENT,
    create_provider,
    provider_referer,
)


@dataclass(slots=True)
class RunStats:
    seen: int = 0
    accepted: int = 0
    downloaded: int = 0
    skipped_existing: int = 0
    filtered: int = 0
    failed: int = 0


EventCallback = Callable[[str, dict], None]


def safe_folder_name(value: str) -> str:
    value = unquote(value).strip().replace("+", " ")
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:120] or "untagged"


def safe_extension(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]", "", (value or "").lower())
    return value[:8] or "bin"


def resolve_provider_ids(options: SearchOptions) -> list[str]:
    if options.provider_ids is None:
        selected: set[str] = set()
        if options.use_danbooru:
            selected.add("danbooru")
        if options.use_gelbooru:
            selected.add("gelbooru")
    else:
        selected = set(options.provider_ids)

    unknown = selected.difference(PROVIDER_MAP)
    if unknown:
        raise ValueError(
            "Unknown provider(s): " + ", ".join(sorted(unknown))
        )
    return [spec.id for spec in PROVIDER_SPECS if spec.id in selected]


class DownloadRunner:
    def __init__(
        self,
        options: SearchOptions,
        credentials: Credentials,
        log=print,
        cancel_event: threading.Event | None = None,
        event_callback: EventCallback | None = None,
    ):
        self.options = options
        self.credentials = credentials
        self.log = log
        self.cancel_event = cancel_event or threading.Event()
        self.event_callback = event_callback
        self.filter = PostFilter(options)
        self.stats = RunStats()
        self._target_locks: dict[str, threading.Lock] = {}
        self._target_locks_guard = threading.Lock()

    def _emit(self, event: str, **payload) -> None:
        if not self.event_callback:
            return
        try:
            self.event_callback(event, payload)
        except Exception:
            pass

    def run(self) -> RunStats:
        if not self.options.tags.strip():
            raise ValueError("No search tags supplied.")

        selected = resolve_provider_ids(self.options)
        if not selected:
            raise ValueError("At least one provider must be enabled.")

        destination = (
            Path(self.options.output_dir).expanduser().resolve()
            / safe_folder_name(self.options.tags)
        )
        destination.mkdir(parents=True, exist_ok=True)
        self.log(f"Output: {destination}")
        self._emit("destination", path=str(destination))

        providers: list[Provider] = [
            create_provider(
                provider_id,
                self.credentials,
                self.options.verbose,
            )
            for provider_id in selected
        ]

        worker_count = max(1, min(16, self.options.workers))
        pending: set[Future] = set()
        max_pending = max(worker_count * 4, 8)

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            for provider in providers:
                if self.cancel_event.is_set() or self._limit_reached():
                    break
                self.log(f"Searching {provider.label} …")
                self._emit(
                    "searching",
                    provider=provider.name,
                    label=provider.label,
                )
                try:
                    for post in provider.iter_posts(
                        self.options.tags,
                        self.options.max_pages,
                    ):
                        if self.cancel_event.is_set() or self._limit_reached():
                            break
                        self.stats.seen += 1
                        self._emit(
                            "post_seen",
                            post=post,
                            stats=asdict(self.stats),
                        )
                        accepted, reason = self.filter.accepts(post)
                        if not accepted:
                            self.stats.filtered += 1
                            self._emit(
                                "post_filtered",
                                post=post,
                                reason=reason,
                                stats=asdict(self.stats),
                            )
                            if self.options.verbose:
                                self.log(
                                    f"[{post.provider}] skip "
                                    f"{post.post_id}: {reason}"
                                )
                            continue

                        self.stats.accepted += 1
                        self._emit(
                            "post_accepted",
                            post=post,
                            stats=asdict(self.stats),
                        )
                        if self.options.dry_run:
                            self.log(
                                f"[dry-run] {post.provider} "
                                f"{post.post_id}: {post.file_url}"
                            )
                            self._emit(
                                "dry_run",
                                post=post,
                                stats=asdict(self.stats),
                            )
                            continue

                        self._emit(
                            "download_queued",
                            post=post,
                            stats=asdict(self.stats),
                        )
                        pending.add(
                            pool.submit(
                                self._download_one,
                                post,
                                destination,
                            )
                        )
                        if len(pending) >= max_pending:
                            done, pending = wait(
                                pending,
                                return_when=FIRST_COMPLETED,
                            )
                            self._consume_futures(done)
                except ProviderError as exc:
                    self.stats.failed += 1
                    self.log(f"ERROR [{provider.label}]: {exc}")
                    self._emit(
                        "provider_error",
                        provider=provider.name,
                        label=provider.label,
                        error=str(exc),
                        stats=asdict(self.stats),
                    )

            if pending:
                self._consume_futures(as_completed(pending))

        self.log(
            "Finished: "
            f"seen={self.stats.seen}, accepted={self.stats.accepted}, "
            f"downloaded={self.stats.downloaded}, "
            f"existing={self.stats.skipped_existing}, "
            f"filtered={self.stats.filtered}, failed={self.stats.failed}"
        )
        self._emit(
            "run_finished",
            stats=asdict(self.stats),
            cancelled=self.cancel_event.is_set(),
        )
        return self.stats

    def _consume_futures(self, futures) -> None:
        for future in futures:
            try:
                result = future.result()
            except Exception as exc:
                self.stats.failed += 1
                self.log(f"ERROR download: {exc}")
                self._emit(
                    "download_worker_error",
                    error=str(exc),
                    stats=asdict(self.stats),
                )
                continue
            if result == "downloaded":
                self.stats.downloaded += 1
            elif result == "exists":
                self.stats.skipped_existing += 1
            elif result == "failed":
                self.stats.failed += 1
            self._emit("stats_updated", stats=asdict(self.stats))

    def _limit_reached(self) -> bool:
        return bool(
            self.options.max_results
            and self.stats.accepted >= self.options.max_results
        )

    def _target_lock(self, target: Path) -> threading.Lock:
        key = str(target)
        with self._target_locks_guard:
            lock = self._target_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._target_locks[key] = lock
            return lock

    def _download_one(self, post: Post, destination: Path) -> str:
        if self.cancel_event.is_set():
            self._emit("download_cancelled", post=post)
            return "cancelled"

        stem = post.md5 or f"{post.provider}_{post.post_id}"
        ext = safe_extension(post.file_ext)
        target = destination / f"{stem}.{ext}"

        with self._target_lock(target):
            return self._download_locked(post, target)

    def _download_locked(self, post: Post, target: Path) -> str:
        if target.exists() and target.stat().st_size > 0:
            if self.options.verbose:
                self.log(f"exists: {target.name}")
            self._emit(
                "download_exists",
                post=post,
                path=str(target),
            )
            return "exists"

        tmp = target.with_suffix(target.suffix + ".part")
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": provider_referer(post.provider),
        }
        self._emit("download_started", post=post)
        try:
            with requests.get(
                post.file_url,
                headers=headers,
                stream=True,
                timeout=(10, 90),
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length") or 0)
                received = 0
                last_reported = -1
                with tmp.open("wb") as handle:
                    for chunk in response.iter_content(
                        chunk_size=256 * 1024
                    ):
                        if self.cancel_event.is_set():
                            self._emit(
                                "download_cancelled",
                                post=post,
                            )
                            return "cancelled"
                        if not chunk:
                            continue
                        handle.write(chunk)
                        received += len(chunk)
                        percent = (
                            int(received * 100 / total)
                            if total
                            else 0
                        )
                        if (
                            not total
                            or percent >= last_reported + 5
                            or received == total
                        ):
                            last_reported = percent
                            self._emit(
                                "download_progress",
                                post=post,
                                received=received,
                                total=total,
                                percent=percent,
                            )
            os.replace(tmp, target)
            self.log(f"saved: {target.name}")
            self._emit(
                "download_finished",
                post=post,
                path=str(target),
                size=target.stat().st_size,
            )
            return "downloaded"
        except requests.RequestException as exc:
            self.log(
                f"ERROR [{post.provider} {post.post_id}]: {exc}"
            )
            self._emit(
                "download_failed",
                post=post,
                error=str(exc),
            )
            return "failed"
        except OSError as exc:
            self.log(
                f"ERROR saving [{post.provider} {post.post_id}]: {exc}"
            )
            self._emit(
                "download_failed",
                post=post,
                error=str(exc),
            )
            return "failed"
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
