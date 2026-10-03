# Changelog

## 2.5.0 – 2026-10-04

- Added e621 and Derpibooru, bringing the source selection to nine providers.
- Added nested e621 file/tag mapping and Philomena pagination, ratings and previews.
- Documented Derpibooru native query syntax and anonymous filter limitations.


## 2.4.1 – 2026-09-29

- Added README badges for Windows build status, version, Python requirement, Windows x64, bilingual GUI and provider count.
- Added a visual separator above the version section in the About dialog so the current BooruGet version is clearly separated from the original-project credit.
- Rebuilt the Windows package as 2.4.1.

## 2.4.0 – 2026-09-29

- Added persistent German/English GUI language switching.
- Localized GUI labels, dialogs, status messages, queue statuses, table headings and preview metadata.
- Added an About button beside the theme/language controls.
- Added an About window with version, `Coded by NetDaemon`, https://ntdmn.xyz/, NetDaemon GitHub/profile and project links, and credit/link to the original `fhrach4/BooruGet` project.
- Language changes apply immediately without restarting the application and are stored in GUI settings.
- Added i18n and About-link regression tests.

## 2.3.0 – 2026-09-29

- Added a provider registry and shared provider-engine architecture.
- Added Safebooru and Rule34.xxx through the Gelbooru 0.2 engine.
- Added yande.re, Konachan and Sakugabooru through a new Moebooru engine.
- GUI now exposes all seven built-in providers as selectable sources and stores provider choices in settings/presets.
- CLI gained `--providers`, `--all-providers` and `--list-providers` while preserving legacy Danbooru/Gelbooru switches.
- Added provider-specific Referer handling for previews/downloads.
- Added per-target download locks to prevent duplicate cross-provider results from racing on the same `.part` file.
- Added multi-booru registry, factory, Moebooru and compatibility tests.

## 2.2.2 – 2026-09-29

- Gelbooru credentials are explicitly optional in the GUI.
- Anonymous Gelbooru searches try DAPI first and automatically fall back to the public HTML search and post pages when Gelbooru temporarily requires API authentication.
- Handles Gelbooru authentication refusals returned as HTTP 401/403, JSON strings, JSON error objects or XML error responses.
- Danbooru credentials are also explicitly optional; public searches continue to use the anonymous `posts.json` API when no account is configured.
- Added regression tests for anonymous Gelbooru fallback and anonymous Danbooru requests.

## 2.2.1 – 2026-09-29

- Fixed a startup crash in the Tkinter GUI caused by accidentally overriding Tkinter's internal `Misc._options()` method.
- Renamed the BooruGet search-options builder to `_build_search_options()` to avoid framework method collisions.
- Added a regression test so future GUI changes cannot silently reintroduce this Tkinter method shadowing bug.
- Rebuilt the Windows release package as 2.2.1.

## 2.2.0 – 2026-09-29

- Added selectable **Dark / Light Mode**, persisted between launches.
- Added named **search presets / favorites** for tags, providers, filters and limits.
- Added a split Queue view with **on-demand post previews**.
- Added direct **Open original post in browser** action for selected results.
- Extended provider models with preview and canonical post URLs.
- Added a dedicated BooruGet application icon for source and Windows EXE builds.
- Removed the extensionless root `BooruGet` launcher and the historical `BooruGet/` working-tree copy from the modern branch to avoid a case-insensitive Windows checkout collision with the modern `booruget/` package; the original source remains preserved in Git history and `master`.
- Windows build now embeds the icon and GUI assets into the one-file executable.
- GitHub Actions also runs on `modernize/**` branches and publishes a GitHub Release automatically for `v*` tags.
- Added `NOTICE.md` documenting the original project, credits and the upstream repository's missing license file.
- Updated public project documentation and bumped the version to 2.2.0.

## 2.1.0 – 2026-09-29

- GUI deutlich ausgebaut: Queue-/Status-Tabelle, laufender Datei-Fortschritt, globale Statusanzeige und Statistikzeile.
- Neuer **Nur suchen**-Modus in der GUI (Dry-run ohne Downloads).
- Suchhistorie und GUI-Einstellungen werden benutzerbezogen gespeichert.
- API-Zugangsdaten können aus der GUI gespeichert werden; Speicherort ist für eine One-File-EXE geeignet.
- Standard-Ausgabe der GUI ist unter Windows der Benutzerordner `Downloads\BooruGet`.
- Ausgabeordner kann direkt aus der GUI geöffnet werden.
- Download-Queue intern begrenzt, damit große Suchläufe nicht unbegrenzt viele Futures im Speicher sammeln.
- Download-Events für Queue, Start, Fortschritt, Erfolg, vorhandene Dateien, Fehler und Abbruch ergänzt.
- Windows-Build vollständig automatisiert (`build_windows.bat` / `build_windows.ps1`).
- Build erzeugt `BooruGet.exe` (GUI), `BooruGet-CLI.exe` und ein portables ZIP-Paket.
- Windows-Dateimetadaten/Versionsinformationen für die EXE ergänzt.
- GitHub-Actions-Workflow für reproduzierbare Win64-Builds hinzugefügt.
- Version auf 2.1.0 angehoben.

## 2.0.0 – 2026-09-29

- Alte Python-Codebasis auf aktuelles Python 3 modernisiert.
- HTTPS- und API-Anpassungen für Danbooru/Gelbooru.
- Moderne Rating-Normalisierung.
- Retry/Timeout-Handling, parallele Downloads und `.part`-Dateien.
- Erste Tkinter-GUI.
- CLI-Kompatibilität zu den wichtigsten alten Schaltern.
- Unit-Tests und Legacy-Quellen aufgenommen.
