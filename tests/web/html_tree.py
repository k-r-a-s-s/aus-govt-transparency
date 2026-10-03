"""A tiny element tree over ``html.parser`` for the page tests (no third-party parser)."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterator, List, Optional

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
        "track", "wbr"}


class El:
    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional["El"] = None):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: List[object] = []  # El or str

    @property
    def classes(self) -> List[str]:
        return self.attrs.get("class", "").split()

    def iter(self) -> Iterator["El"]:
        for c in self.children:
            if isinstance(c, El):
                yield c
                yield from c.iter()

    def find_all(self, tag: Optional[str] = None, cls: Optional[str] = None,
                 **attrs) -> List["El"]:
        out = []
        for e in self.iter():
            if tag and e.tag != tag:
                continue
            if cls and cls not in e.classes:
                continue
            if any(e.attrs.get(k.replace("_", "-")) != v for k, v in attrs.items()):
                continue
            out.append(e)
        return out

    def find(self, tag: Optional[str] = None, cls: Optional[str] = None, **attrs) -> "El":
        found = self.find_all(tag, cls, **attrs)
        if not found:
            raise LookupError(f"no <{tag} class={cls} {attrs}>")
        return found[0]

    def by_id(self, id_: str) -> "El":
        for e in self.iter():
            if e.attrs.get("id") == id_:
                return e
        raise LookupError(f"no element with id {id_!r}")

    @property
    def text(self) -> str:
        """Text content with whitespace collapsed."""
        return " ".join(self.raw_text().split())

    def raw_text(self) -> str:
        return "".join(c if isinstance(c, str) else c.raw_text() for c in self.children)

    def rows(self) -> List["El"]:
        """``<tr>`` of a table's ``<tbody>``."""
        return [tr for tb in self.find_all("tbody") for tr in tb.children
                if isinstance(tr, El) and tr.tag == "tr"]

    def cells(self) -> List["El"]:
        return [c for c in self.children if isinstance(c, El) and c.tag in ("td", "th")]


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = El("#root", {})
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        e = El(tag, {k: (v or "") for k, v in attrs}, self.cur)
        self.cur.children.append(e)
        if tag not in VOID:
            self.cur = e

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(El(tag, {k: (v or "") for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        e = self.cur
        while e is not None and e.tag != tag:
            e = e.parent
        if e is not None and e.parent is not None:
            self.cur = e.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(text: str) -> El:
    b = _Builder()
    b.feed(text)
    b.close()
    return b.root


def parse_file(path: Path) -> El:
    return parse(Path(path).read_text(encoding="utf-8"))
