# Changelog

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
