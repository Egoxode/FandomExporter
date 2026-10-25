#!/usr/bin/env python3
"""
Fandom Exporter: export a whole Fandom (MediaWiki) wiki, or only some of its categories, to Markdown.

Every article is downloaded once (rendered HTML, action=parse), site UI is removed,
the rest is converted to Markdown. Links between articles point to the local .md files.

Output:

  <wiki>_ALL_MD/           or <wiki>_<categories>_MD/ for chosen categories
    pages/                 one .md file per article; for categories in folders: pages/<category>/<subcategory>/
    categories/            one index file per category
    index.md               all pages
    categories.md          all categories
"""

import argparse
import datetime
import os
import posixpath
import re
import sys
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from urllib.parse import quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

VERSION = "1.6.0"

HEADERS = {
    "User-Agent": f"FandomExporter/{VERSION} (+https://example.invalid)"
}

RETRIES = 5                                   # attempts per request
RETRY_STATUS = {429, 500, 502, 503, 504}      # server is busy or temporarily down
# Network errors worth another try: no connection, timeout, answer cut off midway
RETRY_ERRORS = (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError)
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
WORKERS, MAX_WORKERS = 5, 10                  # requests at the same time; more would be refused by the server (429)

sleep = time.sleep  # replaced in tests
# A crash before the export folder exists is written here (next to the program); replaced in tests
CRASH_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")

# Link to an article of this wiki: /wiki/Title or /ru/wiki/Title (language wikis), maybe with ?query and #section
WIKI_LINK = re.compile(r"^/(?:[^/?#]+/)?wiki/([^?#]+)(\?[^#]*)?(#.*)?$")


def clean(name):
    """File name for a title: no characters Windows forbids, not a reserved device name, not too long."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "untitled"
    name = name[:150]
    if name.split(".")[0].upper() in RESERVED:
        name += "_"
    return name


def link(path):
    """Markdown link target: spaces, brackets, # and % would break the link, so they are encoded."""
    for ch, code in (("%", "%25"), (" ", "%20"), ("(", "%28"), (")", "%29"), ("#", "%23")):
        path = path.replace(ch, code)
    return path


def link_text(text):
    return re.sub(r"([\\\[\]])", r"\\\1", text)


def api_url(address):
    """API address for a wiki address: host, wiki URL, page URL or api.php URL. Keeps the language part (/ru)."""
    address = address.strip()
    if not re.match(r"^https?://", address):
        address = "https://" + address
    parsed = urlparse(address)
    path = parsed.path
    if "/wiki/" in path + "/":
        path = (path + "/").split("/wiki/", 1)[0]
    for tail in ("/api.php", "/index.php"):
        if path.endswith(tail):
            path = path[: -len(tail)]
    return f"https://{parsed.netloc}{path.rstrip('/')}/api.php"


def wiki_parts(api):
    """naruto, or naruto + ru for the language wiki."""
    parsed = urlparse(api)
    return [parsed.netloc.split(".")[0]] + [p for p in parsed.path.split("/")[:-1] if p]


def out_name(api, categories=()):
    """Output folder: naruto_ALL_MD, naruto_ru_ALL_MD for the language wiki, naruto_Characters_MD for a category."""
    return clean("_".join(wiki_parts(api) + list(categories))) + ("_MD" if categories else "_ALL_MD")


def wiki_url(api, title):
    """Address of a wiki page for the browser, as the wiki writes it: spaces as _, other special characters
    %-encoded (MediaWiki keeps ;@$!*(),/~: as they are). Keeps the language part: .../ru/wiki/..."""
    return api[: -len("api.php")] + "wiki/" + quote(title.replace(" ", "_"), safe=";@$!*(),/~:")


def list_name(api):
    """File with the list of all categories: naruto_categories.txt, naruto_ru_categories.txt."""
    return clean("_".join(wiki_parts(api))) + "_categories.txt"


def category_names(text):
    """Category names from "Characters; Category:Main_characters": the Category: prefix and _ as in URLs are allowed.

    Separated by ; because a category name may contain a comma.
    """
    names = []
    for name in text.split(";"):
        name = name.strip().replace("_", " ")
        if name.lower().startswith("category:"):
            name = name[len("category:"):].strip()
        if name and name not in names:
            names.append(name)
    return names


class NoWiki(RuntimeError):
    """The address does not answer as a wiki: stop at once, before any question."""


def api_get(api, params, session):
    """One API request. Busy server (429, 5xx) and network errors are retried with a growing pause."""
    params = dict(params)
    params.setdefault("format", "json")
    error = None
    for attempt in range(RETRIES):
        wait = min(60, 2 ** (attempt + 1))
        try:
            r = session.get(api, params=params, headers=HEADERS, timeout=30)
        except RETRY_ERRORS as e:
            error = e
        else:
            if r.status_code not in RETRY_STATUS:
                if r.status_code == 404:
                    raise NoWiki(f"No wiki at {api} (HTTP 404). Check the wiki address: it should open in a browser.")
                r.raise_for_status()
                try:
                    data = r.json()
                except ValueError:
                    raise NoWiki(f"{api} did not answer as a wiki (HTTP {r.status_code}, not JSON). "
                                       "Check the wiki address: it should open in a browser.") from None
                if "error" in data:
                    raise RuntimeError(data["error"].get("info", str(data["error"])))
                return data
            error = requests.HTTPError(f"HTTP {r.status_code}", response=r)
            retry_after = r.headers.get("Retry-After", "")
            if retry_after.isdigit():
                wait = min(120, int(retry_after))
        if attempt < RETRIES - 1:
            sleep(wait)
    raise error


def iter_query(api, session, params):
    """action=query with continuation: yields the "query" part of every answer."""
    params = dict(params, action="query")
    cont = {}
    while True:
        data = api_get(api, {**params, **cont}, session)
        yield data.get("query", {})
        if "continue" not in data:
            break
        cont = data["continue"]


def all_pages(api, session):
    """All articles (main namespace, without redirects) — also those that are in no category."""
    params = {"list": "allpages", "apnamespace": "0", "apfilterredir": "nonredirects", "aplimit": "500"}
    return [p["title"] for q in iter_query(api, session, params) for p in q.get("allpages", []) if p.get("title")]


def all_redirects(api, session):
    """Redirect title -> target title, so that links through redirects lead to the article.

    Asked from the articles' side (prop=redirects: which redirects lead here): MediaWiki refuses
    generator=allpages with gapfilterredir=redirects together with redirects=1.
    """
    params = {"generator": "allpages", "gapnamespace": "0", "gapfilterredir": "nonredirects", "gaplimit": "500",
              "prop": "redirects", "rdprop": "title", "rdlimit": "500"}
    return {r["title"]: page["title"] for q in iter_query(api, session, params)
            for page in q.get("pages", {}).values() if page.get("title")
            for r in page.get("redirects", []) if r.get("title")}


def all_categories(api, session):
    params = {"list": "allcategories", "aclimit": "500"}
    names = (str(c.get("category") or c.get("*") or "").strip()
             for q in iter_query(api, session, params) for c in q.get("allcategories", []))
    return sorted({n for n in names if n})


def category_sizes(api, session):
    """(name, pages, subcategories) of every category with pages or subcategories: one with only files
    (images, videos) has nothing to export. The wiki counts all pages of a category, not only articles."""
    params = {"list": "allcategories", "acprop": "size", "aclimit": "500"}
    rows = {}
    for q in iter_query(api, session, params):
        for c in q.get("allcategories", []):
            name = str(c.get("category") or c.get("*") or "").strip()
            pages, subcats = int(c.get("pages") or 0), int(c.get("subcats") or 0)
            if name and (pages or subcats):
                rows[name] = pages, subcats
    return [(name, *rows[name]) for name in sorted(rows)]


def list_categories(api, session, path):
    """Save the list of all categories to path: too long for the console on a big wiki."""
    print("Getting all categories...")
    rows = category_sizes(api, session)
    write(path, "".join(f"{name} — {pages} page{'' if pages == 1 else 's'}, "
                        f"{subcats} {'subcategory' if subcats == 1 else 'subcategories'} — "
                        f"{wiki_url(api, 'Category:' + name)}\n" for name, pages, subcats in rows))
    print(f"Found {len(rows)} categories. The list is saved in {os.path.abspath(path)}")


def category_pages(api, session, category):
    params = {"list": "categorymembers", "cmtitle": f"Category:{category}", "cmnamespace": "0", "cmlimit": "500"}
    # cmnamespace=0: the wiki itself returns only articles
    return [m["title"] for q in iter_query(api, session, params) for m in q.get("categorymembers", [])
            if m.get("title")]


def category_tree(api, session, category):
    """Articles of a category and of all its subcategories at any depth, from the top down:
    [(folders, titles)], folders = (category, subcategory, ...).

    A subcategory in several places, or in a loop (A in B, B in A), is asked once and kept in the first place.
    """
    tree, seen, todo = [], {category}, [(category,)]
    while todo:
        folders, found = todo.pop(0), []
        params = {"list": "categorymembers", "cmtitle": f"Category:{folders[-1]}", "cmnamespace": "0|14",
                  "cmlimit": "500"}
        for q in iter_query(api, session, params):
            for m in q.get("categorymembers", []):
                title = m.get("title")
                if not title:
                    continue
                if m.get("ns") == 0:
                    found.append(title)
                elif m.get("ns") == 14 and ":" in title:  # Category:Name, on a language wiki with its own prefix (Категория:Name)
                    sub = title.split(":", 1)[1]
                    if sub not in seen:
                        seen.add(sub)
                        todo.append(folders + (sub,))
        tree.append((folders, found))
    return tree


def download_html(api, session, title):
    data = api_get(api, {"action": "parse", "page": title, "prop": "text"}, session)
    return data["parse"]["text"]["*"]


def file_names(titles):
    """Title -> unique file name. Names differing only in letter case are one file on Windows, so they get (2), (3)."""
    names, used = {}, set()
    for title in titles:
        base = clean(title)
        name, n = base, 2
        while name.casefold() in used:
            name, n = f"{base} ({n})", n + 1
        used.add(name.casefold())
        names[title] = name + ".md"
    return names


def cleanup_html(html, target_file):
    """Remove site UI, keep text, infoboxes, tables and lists.

    target_file(title) gives the local .md file of an article or None. Links to exported articles point
    to their files; links to anything else of this wiki (missing pages, files, other namespaces) become text.
    """
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "script",
        "style",
        ".mw-editsection",
        ".toc",
        ".reference",
        ".reflist",
        ".navbox",
        ".error",
        ".mw-empty-elt",
        ".mw-collapsible-toggle",
        ".portal",
        ".catlinks",
    ]
    for sel in selectors:
        for tag in soup.select(sel):
            tag.decompose()
    for img in soup.find_all("img"):
        img.decompose()
    for figure in soup.select("figure"):
        figure.unwrap()
    for a in soup.find_all("a"):
        m = WIKI_LINK.match(a.get("href", ""))
        if not m:
            continue
        target = None if m.group(2) else target_file(unquote(m.group(1)).replace("_", " "))
        if target:
            a["href"] = link(target)
        else:
            a.unwrap()
    return str(soup)


def html_to_markdown(html):
    text = md(html, heading_style="ATX", bullets="-", strip=["span"])
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class ErrorLog:
    """errors.log in the export folder: every ERROR and WARNING with its reason, printed and kept after the
    console is closed. Created on the first message; every run starts with a date line, so reruns add to it."""

    def __init__(self, path):
        self.path, self.started = path, False

    def __call__(self, text):
        print(text)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            if not self.started:
                f.write(f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
                self.started = True
            f.write(text + "\n")


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def run_parallel(items, job, workers, report):
    """job(item) in up to `workers` threads (at most MAX_WORKERS). report(i, item, result, error) runs in this
    thread as the jobs finish, so printing and errors.log are not mixed up.

    Ctrl+C: the running jobs finish, the waiting ones are cancelled. Waiting with a timeout: on Windows an
    endless wait is not interrupted by Ctrl+C.
    """
    pool = ThreadPoolExecutor(max_workers=max(1, min(workers, MAX_WORKERS)))
    try:
        pending = {pool.submit(job, item): item for item in items}
        i = 0
        while pending:
            done, _ = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
            for future in done:
                item = pending.pop(future)
                i += 1
                try:
                    result, error = future.result(), None
                except Exception as e:
                    result, error = None, e
                report(i, item, result, error)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def export(api, out, session, delay=0.25, skip_existing=True, categories=(), subcats=False, workers=WORKERS):
    """Download into the folder out the whole wiki or, if categories are given, only their articles
    (with subcats also those of their subcategories), `workers` requests at the same time.
    Pages already on disk are not downloaded again, unless skip_existing is False.

    Files: pages/<title>.md; for categories in folders as on the wiki, pages/<category>/<subcategory>/<title>.md.
    Returns the titles that could not be downloaded."""
    log = ErrorLog(os.path.join(out, "errors.log"))
    notes = []  # written to errors.log once the folders exist
    print(f"API: {api}")
    print("Getting all pages...")
    titles = sorted(set(all_pages(api, session)))
    try:
        redirects = all_redirects(api, session)
    except Exception as e:
        # Without the list the export still works; links through redirects become plain text.
        notes.append(f"WARNING: could not get redirects: {e}")
        redirects = {}

    def ask(get):
        """Job for run_parallel: the articles of one category."""
        def job(category):
            try:
                return get(api, session, category)
            finally:
                sleep(delay)
        return job

    def one_category(api, session, category):
        """Without subcats: one folder, the category's own articles."""
        return [((category,), category_pages(api, session, category))]

    categories = list(categories)
    membership = {}
    placed = {}  # article -> its folders (category, subcategory, ...): the first place it was found
    if categories:
        answers = {}

        def got_category(i, category, tree, error):
            print(f"[cat {i}/{len(categories)}] {category}")
            answers[category] = tree, error

        run_parallel(categories, ask(category_tree if subcats else one_category), workers, got_category)
        # Only articles of the list of all pages: a redirect in a category counts as its article.
        articles = set(titles)
        for category in categories:  # in the given order, whichever answer came first
            tree, error = answers[category]
            if error:
                notes.append(f"ERROR category: {category}: {error}")
            members = set()
            for folders, found in tree or []:
                for t in found:
                    t = redirects.get(t, t)
                    if t in articles:
                        members.add(t)
                        placed.setdefault(t, folders)
            membership[category] = sorted(members)
            if not error and not members:
                # A missing category is not an error for the wiki: it answers with an empty list.
                notes.append(f"WARNING: no articles in category {category} (check the name)")
        titles = sorted(placed)
        if not titles:
            raise RuntimeError("No articles in the categories: " + "; ".join(categories) + ". Check the names: "
                               "the wiki lists them on the page Special:Categories." + "".join("\n" + n for n in notes))
    names = file_names(titles)
    # Paths inside out with /, as in the links: pages/Name.md, pages/Anime/Episodes/Name.md
    files = {t: "/".join(["pages", *(clean(c) for c in placed.get(t, ())), names[t]]) for t in titles}

    def disk(path):
        return os.path.join(out, *path.split("/"))

    # Folders only after the wiki has answered: a wrong address or category leaves no empty folders behind.
    for folder in {"pages", "categories"} | {posixpath.dirname(f) for f in files.values()}:
        os.makedirs(disk(folder), exist_ok=True)
    for note in notes:
        log(note)
    print(f"Found {len(titles)} pages, {len(redirects)} redirects.")

    def links_from(title):
        """target_file for cleanup_html: the link from this article's folder to the file of another one."""
        here = posixpath.dirname(files[title])

        def target_file(other):
            path = files.get(redirects.get(other, other))
            return path and posixpath.relpath(path, here)
        return target_file

    if not categories:
        print("Getting all categories...")
        try:
            categories = all_categories(api, session)
        except Exception as e:
            # Without the list the articles are still exported; only the category indexes stay empty.
            log(f"WARNING: could not get categories: {e}")
            categories = []
        print(f"Found {len(categories)} categories.")

        def got_members(i, category, found, error):
            print(f"[cat {i}/{len(categories)}] {category}")
            if error:
                log(f"ERROR category: {category}: {error}")
            membership[category] = sorted({redirects.get(t, t) for t in found or []} & set(files))

        run_parallel(categories, ask(category_pages), workers, got_members)

    todo = [t for t in titles if not (skip_existing and os.path.exists(disk(files[t])))]
    if len(todo) < len(titles):
        print(f"Skipping {len(titles) - len(todo)} pages that are already saved (--redownload to download them again).")
    not_saved = set()

    def save_page(title):
        try:
            markdown = html_to_markdown(cleanup_html(download_html(api, session, title), links_from(title)))
            write(disk(files[title]), f"# {title}\n\n{markdown}\n")
        finally:
            sleep(delay)

    def saved_page(i, title, result, error):
        print(f"[{i}/{len(todo)}] {title}")
        if error:
            log(f"ERROR: {title}: {error}")
            not_saved.add(title)

    run_parallel(todo, save_page, workers, saved_page)
    failed = [t for t in titles if t in not_saved]

    # Indexes list only pages that are on disk: a failed page gets a link after a successful rerun.
    saved = [t for t in titles if os.path.exists(disk(files[t]))]
    cat_files = file_names(categories)
    write(os.path.join(out, "index.md"),
          "# Pages\n\n" + "".join(f"- [{link_text(t)}]({link(files[t])})\n" for t in saved))
    write(os.path.join(out, "categories.md"),
          "# Categories\n\n" + "".join(f"- [{link_text(c)}]({link('categories/' + cat_files[c])})\n" for c in categories))
    on_disk = set(saved)
    for c in categories:
        write(disk("categories/" + cat_files[c]),
              f"# {c}\n\n" + "".join(f"- [{link_text(t)}]({link('../' + files[t])})\n"
                                     for t in membership[c] if t in on_disk))

    print(f"Done. Output: {out}")
    if failed:
        log(f"\nNot downloaded ({len(failed)}):\n" + "".join(f"  {t}\n" for t in failed)
            + "Run again: only the missing pages are downloaded.")
    if log.started:
        print(f"Errors are saved in {log.path}")
    return failed


def parse_args():
    parser = argparse.ArgumentParser(description="Export a whole Fandom wiki, or only some of its categories, to Markdown.")
    parser.add_argument("--wiki", default="",
                        help="Wiki address, e.g. konosuba.fandom.com or https://naruto.fandom.com/ru")
    parser.add_argument("--category", action="append", default=[], metavar="NAME",
                        help="Export only the articles of this category; repeat it or separate names with ; "
                             "for several categories")
    parser.add_argument("--subcats", action="store_true",
                        help="With --category: also the articles of its subcategories at any depth")
    parser.add_argument("--workers", type=int, default=WORKERS,
                        help=f"Pages downloaded at the same time, 1 to {MAX_WORKERS} (default {WORKERS})")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between page requests in seconds")
    parser.add_argument("--redownload", action="store_true",
                        help="Download every page again, also those already saved (by default they are skipped)")
    parser.add_argument("--skip-existing", action="store_true", help=argparse.SUPPRESS)  # before 1.5.0; now the default
    parser.add_argument("--list-categories", action="store_true",
                        help="Save the list of all categories of the wiki to <wiki>_categories.txt, do not export")
    parser.add_argument("--version", action="version", version=f"Fandom Exporter {VERSION}")
    return parser.parse_args()


def main():
    try:
        sys.stdout.reconfigure(errors="replace")  # titles in any language, even if the console cannot show them
    except Exception:
        pass
    args = parse_args()
    # Started without --wiki (double-click): the window must stay open, or the result and errors vanish with it.
    interactive = not args.wiki.strip()
    try:
        wiki = args.wiki.strip() or input("Wiki address (e.g. konosuba.fandom.com): ").strip() or "konosuba.fandom.com"
        api = api_url(wiki)
        session = requests.Session()
        if args.list_categories:
            list_categories(api, session, list_name(api))
            code = 0
        else:
            categories = category_names(";".join(args.category))
            subcats = args.subcats
            if interactive and not categories:
                # The list to choose from, before the question. A wrong address stops here; any other failure
                # of the list does not stop the export (as in export itself).
                try:
                    list_categories(api, session, list_name(api))
                except NoWiki:
                    raise
                except Exception as e:
                    print(f"WARNING: could not get the list of categories: {e}")
                categories = category_names(input("Categories, separated by ; (Enter = the whole wiki): "))
                if categories and not subcats:
                    subcats = input("Also the subcategories? (y/N): ").strip().lower().startswith("y")
            failed = export(api, out_name(api, categories), session, args.delay, not args.redownload,
                            categories, subcats, args.workers)
            code = 1 if failed else 0
    except KeyboardInterrupt:
        print("\nStopped. Run again: only the missing pages are downloaded.")
        code = 130
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        try:
            with open(CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n{traceback.format_exc()}\n")
            print(f"Details: {CRASH_LOG}")
        except OSError:
            pass
        code = 2
    if interactive:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
