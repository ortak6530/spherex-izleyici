"""Tiny HTML-to-text helper for reading downloaded docs: prints text and links."""
import html
import re
import sys
from html.parser import HTMLParser


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.out.append(f" [{href}] ")
        if tag in ("p", "br", "li", "tr", "h1", "h2", "h3", "h4", "div"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


for path in sys.argv[1:]:
    p = P()
    p.feed(open(path, encoding="utf-8", errors="replace").read())
    text = re.sub(r"\n\s*\n+", "\n", html.unescape("".join(p.out)))
    print(f"===== {path} =====\n{text}\n")
