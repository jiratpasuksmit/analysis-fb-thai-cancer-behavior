#!/usr/bin/env python3
"""
Turn a Facebook comment-section HTML dump into a clean CSV.

    python3 parse_fb.py --in data.txt --out comments.csv

Each comment on Facebook is one <div role="article" aria-label="Comment by NAME ...">.
That attribute is the anchor: it survives Facebook's obfuscated class names, which
change constantly, so this parser does not depend on any of the x1r8uery-style classes.
"""
from __future__ import annotations
import argparse, base64, csv, re, sys, unicodedata
from pathlib import Path
from urllib.parse import unquote
from bs4 import BeautifulSoup

ARIA = re.compile(r"^(Comment|Reply) by (.+?)(?:\s+((?:an?|\d+)\s+\w+\s+ago))?$")
ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def clean(t: str) -> str:
    """Normalise Thai text: NFC, strip zero-width junk, collapse runs of blank space."""
    t = unicodedata.normalize("NFC", t or "").translate(ZERO_WIDTH)
    t = t.replace("\xa0", " ").replace(" ", "\n").replace(" ", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def decode_cid(param: str) -> str:
    """Facebook's comment_id param is url-encoded base64 of 'comment:<post>_<comment>'.
    Some hrefs carry a different token shape, so anything that does not decode to that
    exact form is rejected rather than written out as mojibake."""
    try:
        b = unquote(param)
        raw = base64.b64decode(b + "=" * (-len(b) % 4)).decode("utf-8", "strict")
    except Exception:
        return ""
    m = re.match(r"^comment:(\d+)_(\d+)$", raw)
    return m.group(2) if m else ""



# Words that carry no information once the @-mentions are removed: "read this",
# "look", politeness particles, pure punctuation. A comment whose remainder is only
# these is someone tagging friends, not answering the question.
FILLER = {
    "อ่าน", "อ่านนะ", "อ่านน", "อ่านค่ะ", "อ่านครับ", "อ่านดู", "อ่านเลย", "อ่านกัน", "อ่านเม้นท์",
    "ดู", "ดูนะ", "ดูสิ", "ดูด้วย", "ศึกษา", "เผื่อ", "กันไว้", "ไว้", "นะ", "นะคะ", "นะครับ",
    "ค่ะ", "คะ", "ครับ", "จ้า", "จ้ะ", "ฮะ", "มาค่ะ", "มา", "เลย", "ด้วย", "ปัก", "ปักอ่าน",
    "แท็ก", "tag", "read", "fyi", "note", "อ่านๆ", "มาอ่าน", "เข้ามาอ่าน",
}
# Thai runs words together, so a token list is not enough: "แกมาอ่าน" is one token.
# This matches the whole remainder when it is nothing but a "go read this" phrase.
TAG_PHRASE = re.compile(
    r"^(?:แก|เธอ|มึง|นี่|นี้|เนี่ย|ปัก|มา|เข้ามา|ไป|ลอง|ช่วย)*"
    r"(?:อ่าน|ดู|ศึกษา|เม้น|เม้นท์|คอมเม้น|คอมเมนต์|tag|read)+"
    r"(?:เม้นท์|เม้น|กัน|ดู|เลย|นะ|น้า|จ้า|จ้ะ|ค่ะ|คะ|ครับ|คับ|ด้วย|ไว้|หน่อย|สิ|ๆ)*"
    r"[\s\.\!\?~]*$")

PUNCT = re.compile(r"^[\s\.\-–—_,!?~ๆฯ:;•·^\*\(\)\[\]\'\"@#/\\+=0-9]+$")


def strip_mentions(text: str, mentions: list) -> str:
    """Remove the literal mention strings so what remains is the comment's own words."""
    out = text
    for m in sorted(mentions, key=len, reverse=True):
        out = out.replace(m, " ")
    return clean(out)


def is_tag_only(body_only: str, mentions: list) -> bool:
    """True when the comment is only friend-tagging. Deliberately conservative:
    a short but substantive answer ("เครียด", "นอนดึก") is NOT tag-only, because the
    test is what the words MEAN, not how many there are."""
    t = body_only.strip()
    if not t:
        return bool(mentions)          # nothing but names
    if PUNCT.match(t) or TAG_PHRASE.match(t.replace(" ", "").replace("\n", "")):
        return True
    toks = [w for w in re.split(r"[\s\n]+", t) if w]
    if len(toks) > 4:
        return False
    return all(w.strip("ๆฯ.,!?~") in FILLER or PUNCT.match(w) for w in toks)


def parse(html: str):
    soup = BeautifulSoup(html, "lxml")
    arts = soup.find_all(attrs={"role": "article"})
    out, seen = [], set()

    for art in arts:
        label = (art.get("aria-label") or "").strip()
        m = ARIA.match(label)
        if not m:
            continue
        kind, author_aria, age = m.group(1), m.group(2), m.group(3) or ""

        # a reply is an article nested inside another article
        depth = sum(1 for p in art.parents if p.get("role") == "article")

        # profile link + comment id, from the first anchor carrying comment_id
        profile, cid_param = "", ""
        for a in art.find_all("a", href=True):
            if "comment_id=" in a["href"]:
                profile = a["href"].split("?")[0]
                cid_param = re.search(r"comment_id=([^&]+)", a["href"]).group(1)
                break
        cid = decode_cid(cid_param) if cid_param else ""

        # the comment body: the dir="auto" block that carries a lang attribute
        body, mentions = "", []
        for d in art.find_all(attrs={"dir": "auto"}):
            if d.has_attr("lang"):
                # @-mentions are profile anchors inside the body; hashtags are not mentions
                for a in d.find_all("a", href=True):
                    href, txt = a["href"], a.get_text(" ", strip=True)
                    if txt and "facebook.com/" in href and "/hashtag/" not in href:
                        mentions.append(txt)
                body = d.get_text("\n", strip=True)
                break
        if not body:                      # fallback: longest dir=auto block that is not the name
            cands = [d.get_text("\n", strip=True) for d in art.find_all(attrs={"dir": "auto"})]
            cands = [c for c in cands if c and c != author_aria]
            body = max(cands, key=len) if cands else ""

        # display name as rendered, falling back to the aria-label
        name_el = art.find("span", attrs={"dir": "auto"})
        author = clean(name_el.get_text(" ", strip=True)) if name_el else ""
        if not author or len(author) > 80:
            author = clean(author_aria)

        reactions = 0
        for el in art.find_all(attrs={"aria-label": True}):
            rm = re.match(r"^(\d[\d,]*) reactions?; see who reacted", el["aria-label"])
            if rm:
                reactions = max(reactions, int(rm.group(1).replace(",", "")))

        text = clean(body)
        body_only = strip_mentions(text, mentions)
        key = cid or (author + "|" + text[:80])
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "comment_id": cid or f"row{len(out)+1}",
            "author": author,
            "comment": text,
            "body_only": body_only,
            "mentions": " | ".join(mentions),
            "chars": len(text),
            "body_chars": len(body_only),
            "tag_only": 1 if is_tag_only(body_only, mentions) else 0,
            "age": age,
            "reactions": reactions,
            "is_reply": 1 if (kind == "Reply" or depth > 0) else 0,
            "profile_url": profile,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="data.txt")
    ap.add_argument("--out", dest="outfile", default="comments.csv")
    ap.add_argument("--min-chars", type=int, default=1, help="drop comments shorter than this")
    ap.add_argument("--keep-dupes", action="store_true")
    ap.add_argument("--keep-tag-only", action="store_true",
                    help="keep comments that only tag friends (dropped by default)")
    ap.add_argument("--dropped-out", default="dropped_tag_only.csv",
                    help="where the dropped tag-only comments are written, so you can audit them")
    a = ap.parse_args()

    html = Path(a.infile).read_text(encoding="utf-8", errors="replace")
    rows = parse(html)
    kept = [r for r in rows if r["chars"] >= a.min_chars]

    tagged = [r for r in kept if r["tag_only"]]
    if not a.keep_tag_only:
        kept = [r for r in kept if not r["tag_only"]]

    if not a.keep_dupes:                  # identical text pasted by different people stays; exact re-posts go
        seen, ded = set(), []
        for r in kept:
            k = (r["author"], r["comment"])
            if k in seen:
                continue
            seen.add(k); ded.append(r)
        kept = ded

    cols = ["comment_id", "author", "comment", "body_only", "mentions", "chars", "body_chars",
            "tag_only", "age", "reactions", "is_reply", "profile_url"]
    with open(a.outfile, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader(); w.writerows(kept)

    if tagged:                       # always write the audit file, so nothing vanishes silently
        with open(a.dropped_out, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(tagged)

    empties = sum(1 for r in rows if not r["chars"])
    lens = sorted(r["chars"] for r in kept)
    med = lens[len(lens)//2] if lens else 0
    print(f"parsed {len(rows)} comment blocks -> wrote {len(kept)} rows to {a.outfile}")
    print(f"  {empties} had no text (image/sticker-only)")
    print(f"  {len(tagged)} tag-only comments {'kept' if a.keep_tag_only else 'dropped'}"
          + (f" -> {a.dropped_out} (audit them)" if tagged else ""))
    print(f"  length: median {med} chars, longest {lens[-1] if lens else 0}, shortest kept {lens[0] if lens else 0}")
    print(f"  replies: {sum(r['is_reply'] for r in kept)}   with reactions: {sum(1 for r in kept if r['reactions'])}")


if __name__ == "__main__":
    main()
