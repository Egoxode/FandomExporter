# Fandom Exporter

Command-line tool that exports a whole Fandom wiki, or only some of its categories, to Markdown files.

Version **1.6.0** ([changelog](CHANGELOG.md))

Fandom Exporter downloads every article of a wiki once and saves it as a `.md` file, with indexes of all pages and all categories. Links between articles lead to the local files, so the export can be read offline, for example in Obsidian, or used to build lorebooks. You can freely use, copy, and modify this program.

## AI Disclaimer

This project was edited with an AI assistant. Read the code before you rely on it.

## Features

- Exports all articles of a wiki, including those that are in no category
- Or only the articles of chosen categories, with their subcategories if you want, in folders as on the wiki
- The list of all categories of a wiki with their sizes (`--list-categories`)
- Indexes: all pages (`index.md`), all categories (`categories.md`) and the pages of each category
- Keeps article text, infoboxes, tables and lists; removes site menus, edit links, references and images
- Links between articles point to the local `.md` files; links through redirects lead to the article
- Language wikis: `https://naruto.fandom.com/ru` exports the Russian wiki, not the English one
- Downloads 5 pages at the same time (`--workers`)
- Retries when the server is busy, and lists the pages that could not be downloaded at the end
- Errors are saved in `errors.log` in the export folder, so they are not lost when the window is closed
- Pages already saved are not downloaded again, so a rerun continues an interrupted export

## Requirements

- Windows, Linux, or macOS
- Python 3.10 or newer
- `pip`
- Internet connection

## Install

### 1. Install Python

Install Python 3.10+ from [python.org](https://www.python.org/downloads/).

During setup on Windows, enable:

- **Add python.exe to PATH**

Check that Python works:

```bash
python --version
```

If `python` is not found, try:

```bash
py --version
```

### 2. Download the program

Copy the `FandomExporter` folder anywhere, then open that folder in a terminal.

### 3. Create a virtual environment (recommended)

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

After activation, your terminal prompt should show `(.venv)`.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

This installs:

- `requests` — downloading
- `beautifulsoup4` — cleaning the HTML
- `markdownify` — converting to Markdown

### 5. Run

```bash
python fandom_exporter.py
```

The program asks for the wiki address. You can also give it on the command line:

```bash
python fandom_exporter.py --wiki konosuba.fandom.com
```

Then it asks for the categories: type their names separated by `;`, or press Enter to export the whole wiki. Before this question the program saves the list of all categories of the wiki to `<wiki>_categories.txt` (as `--list-categories` does) and shows where the file is, so you can pick the names from it. A wrong wiki address stops the program already here. If you typed categories, it also asks whether to export their subcategories. On the command line:

```bash
python fandom_exporter.py --wiki konosuba.fandom.com --category Characters --subcats
```

The list of all categories:

```bash
python fandom_exporter.py --wiki konosuba.fandom.com --list-categories
```

### Run by double-click (Windows)

Double-click `FandomExporter.bat` (or `fandom_exporter.py`). The `.bat` finds Python, installs the dependencies if they are missing, and runs the program. When the program asks for the wiki address, its window stays open at the end until you press Enter, also after an error, so you can read the result.

## Command-line options

- `--wiki ADDRESS` — the wiki: `konosuba.fandom.com`, `https://naruto.fandom.com/ru`, or the address of any page of the wiki
- `--category NAME` — export only the articles of this category. Repeat it, or separate names with `;`: `--category "Characters; Magic"`. The name is as on the wiki, with or without `Category:`; all category names are on the page `Special:Categories` of the wiki
- `--subcats` — with `--category`: also the articles of its subcategories, at any depth
- `--workers N` — how many pages are downloaded at the same time, from 1 to 10 (default `5`)
- `--delay SECONDS` — pause after each page request, in every download (default `0.25`)
- `--redownload` — download every page again. Without it, pages whose `.md` file already exists are skipped (the old `--skip-existing` still works and does the same as no option)
- `--list-categories` — do not export; save the list of all categories of the wiki to `<wiki>_categories.txt` next to where you run the program, one line per category with the address of its page, to open it in a browser: `Characters — 292 pages, 35 subcategories — https://konosuba.fandom.com/wiki/Category:Characters`. Notepad++ or VS Code open such an address with a double-click or Ctrl+click; in the Windows Notepad copy it into the browser. Categories without pages and subcategories are left out: empty ones, and those with only images or videos (there is nothing to export in them). The wiki counts all pages of a category, not only articles, so an export may have fewer
- `--version` — show the version

## Troubleshooting

**`python` is not recognized**  
Python is not in PATH. Reinstall Python and enable **Add python.exe to PATH**, or use `py` instead of `python`.

**`No module named requests` (or `bs4`, `markdownify`)**  
Dependencies were not installed, or you are not inside the virtual environment. Run `pip install -r requirements.txt` again.

**`ERROR: ...` right after the address, no export folder**  
The wiki did not answer with its page list: check the address (it should open in a browser). For an address where there is no wiki the error says so (`No wiki at ...`). No folders are created in this case; the full error text is in `error.log` next to the program.

**`ERROR: ... No such file or directory` for pages with long titles (Windows)**  
The full path of the file is longer than Windows allows (260 characters). This happens when the program folder is deep inside other folders. Move the `FandomExporter` folder closer to the drive root, for example `C:\FandomExporter`, and run again. Category folders make the path longer: with `--subcats` on a deep category tree this happens sooner.

**`WARNING: no articles in category ...` or `No articles in the categories`**  
The wiki has no such category, or it has no articles. Check the name on the page `Special:Categories` of the wiki. With `--subcats` the articles of subcategories count too.

**`WARNING: could not get categories`**  
The articles are still exported, but the category indexes are empty. Run the program again later to get them.

**Many `HTTP 429` errors, or the export is slow because of waiting**  
The server limits how many requests it takes at once. Run again with fewer downloads at the same time, for example `--workers 2`.

**The export was stopped with Ctrl+C**  
The pages that were being downloaded are finished, the rest are not. The indexes are not written. Run again: only the missing pages are downloaded, and the indexes are written.

**Some pages are listed as "Not downloaded"**  
The server did not answer even after several retries. The reason for each page is in `errors.log` in the export folder. Run the program again: only the missing pages are downloaded, and the indexes are rebuilt.

## Usage notes

### Output

The export is written to a folder next to where you run the program, named after the wiki: `konosuba_ALL_MD`, or `naruto_ru_ALL_MD` for a language wiki. An export of categories is named after them: `konosuba_Characters_MD`, `konosuba_Characters_Magic_MD`.

```
konosuba_ALL_MD/
  pages/          one .md file per article
  categories/     one file per category with links to its pages
  index.md        all pages
  categories.md   all categories
  errors.log      errors and warnings, only if there were any
```

An export of categories keeps the articles in folders, as the categories are on the wiki:

```
konosuba_Anime_MD/
  pages/
    Anime/          articles of the category Anime
      Episodes/     articles of its subcategory Episodes (with --subcats)
  categories/     index.md     categories.md
```

- File names are article titles. Characters that Windows does not allow in file names (`<>:"/\|?*`) become `_`. Titles that would give the same file name (for example, differing only in letter case) get `(2)`, `(3)`.
- An export of categories: `index.md` lists its articles, `categories.md` and `categories/` only the chosen categories. A category file lists the articles of the category; with `--subcats` also those of its subcategories.
- An article that is in several chosen categories or subcategories is saved once, in the first folder: the chosen categories in the order you gave, each from the top down. A subcategory that is in several places gets one folder, in the first place. The category files list the article in each of its categories, with a link to that one file.
- An index lists only pages that were saved. After a rerun it is complete.
- A rerun finds the saved pages by file name; to get changed articles again, use `--redownload`. If the wiki gets a new article between the runs whose title differs from another one only in letter case, the numbers `(2)`, `(3)` may shift to other articles. In that case export into a new folder (rename or move the old one).

### Links

- A link to another exported article points to its `.md` file, also in another category folder (`../Episodes/...`). Spaces and brackets in the file name are written as `%20`, `%28`, `%29`, so the link works in Markdown viewers.
- A link to a section of an article leads to the article.
- Links to pages that do not exist, to files, or to service pages become plain text. In an export of categories, links to articles outside the chosen categories become plain text too.

### Content

- Only articles (the main namespace) are exported. Redirects are not saved as separate files.
- Images are removed; captions stay as text.
- Text on Fandom is usually licensed under CC BY-SA. If you publish the exported text, keep the attribution to the wiki.

## License

MIT. You may freely use and modify this program.
