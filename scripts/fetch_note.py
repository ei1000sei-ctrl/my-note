"""note.com の記事を取得して articles/ に Markdown で保存し、README.md の記事一覧を更新する。

使い方: python3 scripts/fetch_note.py
"""

import json
import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

CREATOR = "ei__sensei"
ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "articles"


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as res:
        return json.load(res)


class MarkdownConverter(HTMLParser):
    """note の本文 HTML を簡易的に Markdown へ変換する。"""

    def __init__(self):
        super().__init__()
        self.out = []
        self.list_stack = []
        self.href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4"):
            self.out.append("\n\n" + "#" * (int(tag[1]) + 1) + " ")
        elif tag == "p":
            self.out.append("\n\n")
        elif tag == "br":
            self.out.append("  \n")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "blockquote":
            self.out.append("\n\n> ")
        elif tag in ("ul", "ol"):
            self.list_stack.append([tag, 0])
            self.out.append("\n")
        elif tag == "li":
            kind = self.list_stack[-1] if self.list_stack else ["ul", 0]
            kind[1] += 1
            indent = "  " * (len(self.list_stack) - 1)
            mark = f"{kind[1]}." if kind[0] == "ol" else "-"
            self.out.append(f"\n{indent}{mark} ")
        elif tag == "a":
            self.href = attrs.get("href")
            self.out.append("[")
        elif tag == "img":
            self.out.append(f"\n\n![{attrs.get('alt') or ''}]({attrs.get('src', '')})")
        elif tag == "hr":
            self.out.append("\n\n---")
        elif tag == "pre":
            self.out.append("\n\n```\n")

    def handle_endtag(self, tag):
        if tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag in ("ul", "ol") and self.list_stack:
            self.list_stack.pop()
        elif tag == "a":
            self.out.append(f"]({self.href or ''})")
            self.href = None
        elif tag == "pre":
            self.out.append("\n```")

    def handle_data(self, data):
        self.out.append(data)

    def markdown(self):
        text = "".join(self.out)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def html_to_markdown(html):
    conv = MarkdownConverter()
    conv.feed(html or "")
    return conv.markdown()


def clean_title(title):
    return re.sub(r"[\s　]+", " ", title).strip()


def fetch_list():
    notes, page = [], 1
    while True:
        data = get_json(
            f"https://note.com/api/v2/creators/{CREATOR}/contents?kind=note&page={page}"
        )["data"]
        notes.extend(data["contents"])
        if data["isLastPage"]:
            return notes
        page += 1


def main():
    ARTICLES.mkdir(exist_ok=True)
    notes = sorted(fetch_list(), key=lambda n: n["publishAt"], reverse=True)
    index = []
    for n in notes:
        detail = get_json(f"https://note.com/api/v3/notes/{n['key']}")["data"]
        title = clean_title(n["name"])
        date = n["publishAt"][:10]
        filename = f"{date}_{n['key']}.md"
        paid = bool(detail.get("price"))
        lines = [
            "---",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            f"date: {date}",
            f"url: {n['noteUrl']}",
            f"paid: {str(paid).lower()}",
            "---",
            "",
            f"# {title}",
            "",
            html_to_markdown(detail.get("body")),
        ]
        if paid:
            lines.append("\n> 有料部分は含まれていません。続きは note で読めます。\n")
        (ARTICLES / filename).write_text("\n".join(lines), encoding="utf-8")
        index.append(f"| {date} | [{title}](articles/{filename}) | [note]({n['noteUrl']}) |")
        time.sleep(0.5)

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    table = "\n".join(["| 公開日 | タイトル | 元記事 |", "| --- | --- | --- |", *index])
    text = re.sub(
        r"<!-- articles:start -->.*<!-- articles:end -->",
        f"<!-- articles:start -->\n{table}\n<!-- articles:end -->",
        text,
        flags=re.S,
    )
    readme.write_text(text, encoding="utf-8")
    print(f"{len(notes)} 件の記事を保存しました")


if __name__ == "__main__":
    main()
