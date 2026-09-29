# BooruGet

**BooruGet** is a modernized continuation of the original Python-based Gelbooru and Danbooru image downloader. The 2026 revival keeps the original CLI idea alive while adding current APIs, a desktop GUI, safer downloads and reproducible Windows builds.

> Original project: **fhrach4/BooruGet**  
> Modernized fork: **netdaemon91/BooruGet**

## What is new in 2.2

- modern **Tkinter desktop GUI**
- **Dark / Light Mode**
- named **search presets / favorites**
- queue with per-file status and progress
- **on-demand image preview** for the selected result
- direct link to the original Danbooru/Gelbooru post
- search-only / dry-run mode
- persistent search history and GUI settings
- current Danbooru and Gelbooru API handling
- parallel downloads with retries, timeouts and `.part` files
- standalone `BooruGet.exe` and `BooruGet-CLI.exe`
- automated Win64 builds through GitHub Actions
- automatic GitHub Release publishing for `v*` tags

## Screens / workflow

1. Enter one or more booru tags.
2. Optionally load or save a search preset.
3. Choose Gelbooru, Danbooru or both.
4. Configure resolution, ratings and limits.
5. Use **Nur suchen** to preview results without downloading, or **Download starten** to save them.
6. Select a result in the queue to load its preview and open the canonical post page.

## Requirements when running from source

- Python 3.10+
- `requests`
- `Pillow`

```powershell
py -3 -m pip install -r requirements.txt
```

Then start the GUI:

```powershell
py -3 BooruGet-GUI.py
```

or:

```powershell
py -3 BooruGet.py --gui
```

On Windows, `start_gui.bat` can also be launched by double-clicking it.

## Command line

Basic search:

```powershell
py -3 BooruGet.py landscape sunset
```

Gelbooru only, maximum 50 accepted posts:

```powershell
py -3 BooruGet.py landscape --gelbooru-only --max-results 50
```

Approximately 1920×1080:

```powershell
py -3 BooruGet.py landscape --width 1920 --height 1080
```

Search without downloading:

```powershell
py -3 BooruGet.py landscape --dry-run --max-pages 1 --verbose
```

The most important legacy switches remain supported, including `--nodan`, `--nogel`, `--nsfw`, `--anysize`, `--width`, `--height` and `--error`.

## API credentials

Copy `booruget.ini.example` to `booruget.ini` if you want to provide credentials manually:

```ini
[danbooru]
username = YOUR_NAME
api_key = YOUR_API_KEY

[gelbooru]
user_id = YOUR_USER_ID
api_key = YOUR_API_KEY
```

The GUI can also save these values. On Windows, its normal user configuration directory is:

```text
%APPDATA%\BooruGet\
```

API keys are stored as plain text in the INI file. Treat that file like a password-bearing configuration file.

## Windows EXE build

On a 64-bit Windows machine with Python installed, run:

```text
build_windows.bat
```

The build script creates an isolated build environment, runs the test suite and produces:

```text
release\BooruGet-2.2.1-win64\BooruGet.exe
release\BooruGet-2.2.1-win64\BooruGet-CLI.exe
release\BooruGet-2.2.1-win64.zip
```

The resulting executables do **not** require a separate Python installation.

PyInstaller is not a cross-compiler, so Windows executables should be built on Windows.

## GitHub Actions

The repository includes `.github/workflows/build-windows.yml`.

- pushes to `master`, `main` and `modernize/**` run a Win64 build
- manual runs are available through **Actions → Build Windows EXE**
- the release ZIP is uploaded as a workflow artifact
- pushing a tag such as `v2.2.1` creates a GitHub Release and attaches the Win64 ZIP automatically

## Modern API fixes

Compared with the historical version, the modernized codebase includes:

- HTTPS endpoints
- current Danbooru `posts.json` parsing and direct use of `file_url`
- Danbooru username/API-key authentication
- current Gelbooru DAPI parameters with optional `user_id` + `api_key`
- Gelbooru JSON parsing with XML fallback
- correct modern Danbooru rating semantics (`g/s/q/e`)
- request retries/backoff and explicit timeouts
- bounded parallel download queue
- Windows-safe output directory names
- existing-file detection
- atomic `.part` downloads

## Legacy blacklist compatibility

These historical files are still recognized when present:

- `.config/global_blacklist`
- `.config/nsfw_blacklist`
- `.config/md5_global_blacklist`
- `.config/md5_nsfw_blacklist`
- `.config/md5_nsfw_whitelist`

Each line represents one tag or MD5 value.

## Tests

```powershell
py -3 -m unittest discover -s tests -v
```

## Project history and credits

BooruGet was originally created by **fhrach4** and developed as a Python booru downloader. The historical README already listed a GUI as a planned feature; this fork continues that idea while updating the APIs and packaging for current systems.

- Original author/project: [fhrach4/BooruGet](https://github.com/fhrach4/BooruGet)
- Original history is preserved through the GitHub fork relationship.
- The historical source remains available on the untouched `master` history and through the original upstream repository.
- Modernization and continued development from 2026: **NetDaemon / netdaemon91**.

Thanks also to the contributors present in the original repository history.

## Licensing note

The original upstream repository did not contain a project license file when this modernization began. A fork and credits do not create a new license for the historical code, so this repository intentionally does **not** apply a blanket MIT/GPL-style license to the original source.

See [`NOTICE.md`](NOTICE.md) for the project-history and licensing-status notice.

## Project layout

- `booruget/` – modernized application package
- `assets/` – application icon and GUI assets
- `BooruGet-GUI.py` – GUI entry point
- `BooruGet.py` – CLI / combined entry point
- `build_windows.bat` / `build_windows.ps1` – reproducible Windows build
- `.github/workflows/build-windows.yml` – Win64 CI/release build
- `tests/` – unit tests
- Git history / `master` – preserved historical upstream source

## Recommended first live test

Because API availability and account permissions are external, begin with a small dry-run:

```powershell
py -3 BooruGet.py landscape --dry-run --max-pages 1 --verbose
```
