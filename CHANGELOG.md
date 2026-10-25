# Changelog

## 1.6.0

### Changed
- When the program asks for the wiki address, it saves the list of all categories to `<wiki>_categories.txt` right after it, before asking for the categories, and shows where the file is. The answer `?` is not needed any more and is removed. With `--wiki` on the command line the list is saved only with `--list-categories`.
- A wrong wiki address stops the program right after the address, before the questions about categories. If only the list of categories could not be loaded, it is a warning and the export goes on.

### Added
- Every line of `<wiki>_categories.txt` ends with the address of the category page, to open it in a browser: `Characters — 292 pages, 35 subcategories — https://konosuba.fandom.com/wiki/Category:Characters`.

## 1.5.0

### Added
- An export of categories keeps the articles in folders, as the categories are on the wiki: `pages/Anime/`, `pages/Anime/Episodes/`. An article that is in several categories is saved once, in the first one. Links between articles in different folders work.
- `--list-categories` saves the list of all categories of the wiki, with the number of pages and subcategories, to `<wiki>_categories.txt` (also in `.gitignore`). Categories with no pages and no subcategories (empty, or only images and videos) are left out. When the program asks for the categories, `?` does the same and asks again.
- `--redownload` downloads every page again.

### Changed
- Pages already saved are not downloaded again, without any option: a rerun continues an interrupted export. `--skip-existing` still works; it is now the default.

## 1.4.0

### Added
- Faster export: 5 pages are downloaded at the same time, and the categories are asked the same way. `--workers N` sets the number, from 1 to 10; `--workers 1` downloads one page at a time, as before.

### Changed
- Pages are listed as they are saved, so the order of the `[i/N]` lines may differ from the alphabet. The list of pages that could not be downloaded stays in the order of titles.
- `--skip-existing` prints one line with the number of skipped pages instead of a line for each.
- Ctrl+C stops the export: the pages being downloaded are finished, the rest are not started. Run again with `--skip-existing` to continue.

### Fixed
- `.gitignore` left out the folders of category exports (`konosuba_Characters_MD`): only `*_ALL_MD` was ignored. Now `*_MD`.

## 1.3.0

### Added
- Export only some categories instead of the whole wiki: `--category NAME` (repeat it, or separate names with `;`). When the program asks for the wiki address, it also asks for the categories; Enter exports the whole wiki.
- `--subcats`: also the articles of the subcategories, at any depth. Subcategories that contain each other are asked once. When the program asks for the categories, it also asks about subcategories.
- A category export goes to its own folder, for example `konosuba_Characters_MD`, so it does not overwrite the full export `konosuba_ALL_MD`. Its indexes list only the chosen categories, and links to articles outside them become plain text.
- A category with no articles (for example, a misspelled name) is a warning in `errors.log`. If none of the categories has articles, the program stops with an error and creates no folder.

## 1.2.4

### Changed
- Category members: the extra check that a page is an article is removed. The request already asks the wiki for articles only (`cmnamespace=0`). The result is the same.

## 1.2.3

### Fixed
- If the list of categories could not be loaded, the whole export stopped before any article was downloaded. Now this is a warning in `errors.log`: the articles are exported, only the category indexes stay empty.
- An answer cut off midway by the network was not retried: the page was listed as not downloaded, and during the page or category lists the whole export stopped. It is now retried like a lost connection.
- A wrong address gave an unclear error (`HTTPError: 404 Client Error`, or `JSONDecodeError` for a site that is not a wiki). It now says that there is no wiki at that address.

### Changed
- README: how `--skip-existing` finds pages, and when its file numbers `(2)`, `(3)` may shift.
- README: what to do if pages with long titles are not saved on Windows (the path is over 260 characters).

## 1.2.2

### Added
- `errors.log` in the export folder: every error and warning with its reason (pages, categories, redirects) and the list of pages that were not downloaded. It is created only if there were errors; a rerun adds to it under a new date line.
- If the program stops before the export folder exists (for example, a wrong address), the full error text is written to `error.log` next to the program.

## 1.2.1

### Fixed
- The export stopped right after the wiki address, leaving empty folders: the request for the list of redirects was refused by Fandom (MediaWiki does not allow it in that form). Redirects are now asked from the articles' side, and if the list still cannot be read, the export goes on without it (links through redirects become plain text) with a warning.
- Folders are created only after the wiki has answered with its page list, so a wrong address leaves no empty folders.
- When the program asks for the wiki address (double-click), its window no longer closes at the end or after an error: it waits for Enter. `FandomExporter.bat` no longer adds its own second pause.

## 1.2.0

### Added
- Articles that are in no category are exported too (before, only pages listed in categories were found).
- Links through redirects lead to the article.
- A busy server (HTTP 429, 5xx) or a lost connection is retried up to 5 times with a growing pause. Pages that still fail are listed at the end; `--skip-existing` downloads only them.
- `FandomExporter.bat` installs the dependencies if they are missing.
- `--version`.

### Fixed
- Links with spaces or brackets in the file name (`Kazuma Satou.md`, `Megumin (anime).md`) did not work in Markdown viewers, in the indexes and inside articles. They are now written as `%20`, `%28`, `%29`.
- A link to a section (`/wiki/Kazuma_Satou#Abilities`) pointed to a missing file `Kazuma Satou#Abilities.md`. It now leads to the article.
- Links to missing pages (`?action=edit&redlink=1`), files and service pages became broken `.md` links. They are now plain text.
- A wiki given as a page address of a language wiki (`https://naruto.fandom.com/ru/wiki/...`) exported the English wiki. The language part is now kept, and the output folder is `naruto_ru_ALL_MD`.
- Titles that give the same file name (`A/B` and `A?B`, or names differing only in letter case on Windows) overwrote each other. They now get `(2)`, `(3)`. Reserved Windows names (`CON`, `NUL`, ...) get `_`.
- `FandomExporter.bat` stopped at the Microsoft Store "python" stub when Python was not installed; it now checks that Python really runs and tries `py` first.
- Indexes linked to pages that failed to download.

### Changed
- One program: `fandom_exporter.py` (the single-category script is removed). `requirements.txt` instead of `fandom_exporter_all_requirements.txt`.

## 1.1

All categories of a wiki in one run; pages in several categories are downloaded once.

## 1.0

One category of the KonoSuba wiki.
