# BooruGet

[![Windows Build](https://github.com/netdaemon91/BooruGet/actions/workflows/build-windows.yml/badge.svg)](https://github.com/netdaemon91/BooruGet/actions/workflows/build-windows.yml)
![Version](https://img.shields.io/badge/version-2.5.1-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-x64-0078D4?logo=windows11&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-DE%20%7C%20EN-2ea44f)
![Boorus](https://img.shields.io/badge/Boorus-10-purple)

**BooruGet** is a modernized continuation of the original Python booru image downloader. The 2026 revival keeps the original command-line workflow while adding a desktop GUI, current APIs, multi-booru provider engines, safer downloads and reproducible Windows builds.

> Original project: **fhrach4/BooruGet**  
> Modernized fork: **netdaemon91/BooruGet**

## BooruGet 2.5

BooruGet is a **multi-booru downloader** with a bilingual German/English desktop interface. Ten built-in sources share reusable provider engines:

| Provider | ID | Engine | Default |
| --- | --- | --- | --- |
| Danbooru | `danbooru` | Danbooru API | yes |
| Gelbooru | `gelbooru` | Gelbooru 0.2 / public HTML fallback | yes |
| Safebooru | `safebooru` | Gelbooru 0.2 | no |
| Rule34.xxx | `rule34` | Gelbooru 0.2 / public HTML fallback | no |
| yande.re | `yandere` | Moebooru | no |
| Konachan | `konachan` | Moebooru | no |
| Sakugabooru | `sakugabooru` | Moebooru | no |
| e621 | `e621` | e621 | no |
| Derpibooru | `derpibooru` | Philomena | no |
| Rule34 Paheal | `paheal` | Shimmie XML | no |

The registry architecture makes additional compatible sites much easier to add later.

## GUI

The Tkinter desktop application includes:

- selectable provider checkboxes for all built-in boorus
- persistent **Deutsch / English** language switching
- **About** window with version, credits, project links and NetDaemon website
- Dark / Light Mode
- named search presets / favorites, including provider selections
- queue with per-file status and progress
- on-demand preview for the selected result
- direct link to the original post
- search-only / dry-run mode
- persistent search history and GUI settings
- optional Danbooru and Gelbooru credentials
- parallel downloads with retries, timeouts and atomic `.part` files

Start from source:

```powershell
py -3 -m pip install -r requirements.txt
py -3 BooruGet-GUI.py
```

On Windows, `start_gui.bat` can also be launched by double-clicking it.

The language button in the header switches the complete GUI between German and English immediately. The selected language is persisted with the other GUI settings. The **About** button next to the appearance/language controls shows the current version, modernization credits, NetDaemon links and the original `fhrach4/BooruGet` project.

## Command line

The historical default remains Danbooru + Gelbooru:

```powershell
py -3 BooruGet.py landscape sunset
```

Choose individual providers:

```powershell
py -3 BooruGet.py landscape --providers safebooru yandere sakugabooru
```

Search all built-in providers:

```powershell
py -3 BooruGet.py landscape --all-providers
```

List provider IDs:

```powershell
py -3 BooruGet.py --list-providers
```

Dry-run:

```powershell
py -3 BooruGet.py landscape --providers yandere konachan --dry-run --max-pages 1 --verbose
```

The important legacy switches remain supported, including `--nodan`, `--nogel`, `--danbooru-only`, `--gelbooru-only`, `--nsfw`, `--anysize`, `--width`, `--height` and `--error`.

## Ratings and adult content

By default, BooruGet only accepts posts normalized as **general/safe**. Enable **NSFW erlauben** in the GUI or `--nsfw` on the command line to allow all ratings.

Provider availability does not override the rating filter: selecting a source that mainly contains adult-rated posts may therefore produce few or no accepted results until NSFW ratings are enabled.

## API credentials

Danbooru and Gelbooru credentials are optional for normal public use:

```ini
[danbooru]
username = YOUR_NAME
api_key = YOUR_API_KEY

[gelbooru]
user_id = YOUR_USER_ID
api_key = YOUR_API_KEY
```

Danbooru public reads work anonymously. Gelbooru is attempted anonymously first and BooruGet can fall back to its public HTML listing/post pages when anonymous DAPI access is unavailable.

The additional 2.3 providers currently run anonymously. Rule34.xxx can require API authentication for its DAPI; BooruGet therefore falls back to its public site when anonymous API access is refused.

On Windows, GUI configuration is normally stored under:

```text
%APPDATA%\BooruGet\
```

API keys are stored as plain text in the INI file.

## Provider architecture

`booruget/providers.py` contains a provider registry and shared engines:

- **DanbooruProvider** for Danbooru-style `posts.json`
- **GelbooruV02Provider** for Gelbooru/Safebooru/Rule34-style DAPI
- **MoebooruProvider** for yande.re/Konachan/Sakugabooru `post.json`
- **E621Provider** for e621 nested JSON posts
- **PhilomenaProvider** for Derpibooru JSON searches
- **ShimmieProvider** for Paheal XML searches

Each site is described by a small `ProviderSpec` with its label, family, public URL and API URL. This is the intended extension point for future boorus.

## Windows EXE build

On a 64-bit Windows machine with Python installed:

```text
build_windows.bat
```

The build produces:

```text
release\BooruGet-2.5.1-win64\BooruGet.exe
release\BooruGet-2.5.1-win64\BooruGet-CLI.exe
release\BooruGet-2.5.1-win64.zip
```

The executables do not require a separate Python installation.

The repository also contains `.github/workflows/build-windows.yml`. Pushes to `master`, `main` and `modernize/**` run a Win64 build. Tags such as `v2.5.1` publish the ZIP as a GitHub Release.

## Download safety / reliability

The modernized downloader includes:

- HTTPS endpoints
- retry/backoff and explicit timeouts
- bounded parallel download queue
- per-target locking so duplicate images returned by multiple providers cannot corrupt the same `.part` file
- Windows-safe output directory names
- existing-file detection
- atomic `.part` downloads
- current Danbooru rating semantics
- provider-specific Referer handling

## Legacy blacklist compatibility

These historical files are still recognized:

- `.config/global_blacklist`
- `.config/nsfw_blacklist`
- `.config/md5_global_blacklist`
- `.config/md5_nsfw_blacklist`
- `.config/md5_nsfw_whitelist`

## Tests

```powershell
py -3 -m unittest discover -s tests -v
```

## Project history and credits

BooruGet was originally created by **fhrach4**. The historical README already listed a GUI as a planned feature; this fork continues that idea while updating APIs, packaging and the provider architecture for current systems.

- Original author/project: [fhrach4/BooruGet](https://github.com/fhrach4/BooruGet)
- Original history is preserved through the GitHub fork relationship.
- Modernization and continued development from 2026: **NetDaemon / netdaemon91**.

Thanks also to the contributors present in the original repository history.

## Licensing note

The original upstream repository did not contain a project license file when this modernization began. A fork and credits do not create a new license for the historical code, so this repository intentionally does **not** apply a blanket MIT/GPL-style license to the original source.

See [`NOTICE.md`](NOTICE.md) for the project-history and licensing-status notice.

## Project layout

- `booruget/providers.py` – provider registry and shared engines
- `booruget/` – application package
- `assets/` – application icon and GUI assets
- `BooruGet-GUI.py` – GUI entry point
- `BooruGet.py` – CLI / combined entry point
- `build_windows.bat` / `build_windows.ps1` – reproducible Windows build
- `.github/workflows/build-windows.yml` – Win64 CI/release build
- `tests/` – unit tests

## Recommended first live test

```powershell
py -3 BooruGet.py landscape --providers safebooru yandere --dry-run --max-pages 1 --verbose
```

### Provider-specific searches

Derpibooru accepts its native search syntax: separate tags with commas, for example `safe, landscape`. Tags containing spaces stay intact. Its anonymous API uses the site’s default content filter; selecting adult ratings locally does not override that server filter. Derpibooru uses SHA-512 instead of MD5, so cross-provider MD5 duplicate detection is unavailable for this source.

e621 searches use the usual space-separated tags. Deleted posts and posts without an accessible original file are skipped. All ten sources appear in a four-column selection grid; new sources remain disabled by default.

Paheal uses Shimmie’s Danbooru-compatible XML API. Because its API has no reliable per-post ratings, every result is conservatively treated as explicit and requires the corresponding rating setting. The user confirmed a live XML search response and opened its original CDN image successfully. The adapter is tested with that response; the complete application download still needs a Windows smoke test.

Other candidates checked: rule34.us identifies as modified Gelbooru 0.1.11 with custom routes; no confirmed reusable API was found. Behoimi could not be reached from this environment. Neither is included.
