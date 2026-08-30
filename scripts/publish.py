#!/usr/bin/env python3
"""
Turn judged.csv into a publishable bundle: strips everything that identifies a
person, then writes a docs/ folder ready to serve as a GitHub Page.

    python3 publish.py --judged judged.csv --comments comments.csv --out docs

NOTHING that names a person leaves this script. Author names, profile URLs and
@-mentions are dropped, not hashed — a hash of a name is still a stable
identifier that links a person's comments together across the dataset.

Comment ids are replaced with sequential surrogates, so a row cannot be traced
back to the Facebook thread it came from.

Read the privacy audit it prints before you commit anything.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
csv.field_size_limit(10_000_000)

# columns that identify a person and never reach the bundle
DROP = ["author", "profile_url", "mentions", "comment_id", "comment"]

# Names typed as plain text rather than linked as @-mentions. The parser only sees
# anchor tags, so these survive the mention list and must be caught by shape.
NOT_NAMES = {
    "fast food","junk food","line man","grab food","food panda","seven eleven",
    "coca cola","big c","central world","covid","long covid","the one","new york",
    "pm two","air pollution","world health","health organization","of course",
}
# Names confirmed by reading all 419 on-topic rows by hand (2026-08-30). Pattern
# matching missed these: initials, diacritics, and names fused to Thai text.
REVIEWED_NAMES = [
    "Aelly Siwakornmetasit", "Ken Luenthaisong", "Tanisorn Pongtanesuan",
    "Thaweesak Khemchoknawee", "Naruedon Maneewan", "Phobchok Ploymukda",
    "Davarin Chankhum", "Boonma Thanapat", "Max Phutthimet", "Zine Wannisa",
    "Alisa Stamp", "Mo Moo",
    "Witsarut P K-ros", "Pätcharee Saelëë", "Mink Chruaphet", "อี๊ฟ อรทัย",
    "S.tower", "Jobi SK Nyrhinen", "Fantar NG", "Nguansuk",
]

LATIN_NAME = re.compile(r"\b[A-Z][a-z']{2,}(?:\s+[A-Z][a-z'.]{1,}){1,2}\b")
THAI_TITLE_NAME = re.compile(r"(?:อ|นพ|พญ|ดร)\.\s?[ก-๙]{2,15}")
# คุณ/พี่/หมอ + a word is usually kinship or a common noun, not a name — reported, not scrubbed
THAI_MAYBE_NAME = re.compile(r"(?:คุณ|พี่|หมอ)\s?[ก-๙]{2,12}")
THAI_KIN = ("แม่","พ่อ","ยาย","ตา","ป้า","ลุง","น้า","อา","หมอ","ภาพ","ค่า","ผู้","สมบัติ","ประโยชน","ธรรม")

def strip_typed_names(text: str) -> tuple[str, list[str]]:
    """Replace name-shaped strings the mention list never knew about."""
    found = []
    for n in sorted(REVIEWED_NAMES, key=len, reverse=True):
        if n in text:
            found.append(n); text = text.replace(n, "[ชื่อ]")
    def latin(m):
        if m.group(0).lower() in NOT_NAMES:
            return m.group(0)
        found.append(m.group(0)); return "[ชื่อ]"
    out = LATIN_NAME.sub(latin, text or "")
    def thai(m):
        found.append(m.group(0)); return "[ชื่อ]"
    out = THAI_TITLE_NAME.sub(thai, out)
    return out, found


CONTACT = [
    (re.compile(r"https?://\S+"), "[ลิงก์]"),
    (re.compile(r"\b(?:youtu\.be|youtube\.com)/\S+"), "[ลิงก์]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[อีเมล]"),
    (re.compile(r"(?<!\d)0\d[\s-]?\d{3}[\s-]?\d{4}(?!\d)"), "[เบอร์โทร]"),   # Thai mobile
    (re.compile(r"(?i)\b(line|ไลน์)\s*(id)?\s*[:：]?\s*[\w.\-]{3,}"), "[ไลน์]"),
    (re.compile(r"(?i)\b(fb|facebook)\.com/[\w.\-]+"), "[เฟซบุ๊ก]"),
]


TYPED_NAMES_FOUND = []


def scrub(text: str, names: list[str]) -> str:
    """Remove @-mentioned names, then name-shaped strings the mention list missed,
    then any contact details left in the prose."""
    out = text or ""
    for n in sorted([n for n in names if len(n) >= 3], key=len, reverse=True):
        out = out.replace(n, "[ชื่อ]")
    out, typed = strip_typed_names(out)
    TYPED_NAMES_FOUND.extend(typed)
    for rx, repl in CONTACT:
        out = rx.sub(repl, out)
    return re.sub(r"\s+\n", "\n", out).strip()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--judged", default="judged.csv")
    p.add_argument("--comments", default="comments.csv", help="source CSV, for the mention list used to scrub")
    p.add_argument("--out", default="docs", help="output directory (GitHub Pages serves docs/ on main)")
    p.add_argument("--labels", default=str(HERE / "labels.json"))
    p.add_argument("--template", default=str(HERE / "dashboard_template.html"))
    p.add_argument("--only-ontopic", action="store_true",
                   help="drop off_topic and promotion rows entirely (544 -> 419)")
    p.add_argument("--text", choices=["full", "short", "none"], default="none",
                   help="how much comment text to publish. DEFAULT none, and that is deliberate: "
                        "Thai personal names have no reliable pattern, so free comment text CANNOT "
                        "be scrubbed of names by any regex. full/short will leak names.")
    p.add_argument("--text-max", type=int, default=200,
                   help="with --text short, comments longer than this are withheld")
    p.add_argument("--title", default="พฤติกรรมเสี่ยงมะเร็งที่คนไทยพูดถึง — What Thai Facebook commenters believe causes cancer")
    p.add_argument("--source-note", default="Public comments on one Facebook post, collected 2026.")
    a = p.parse_args()

    out = Path(a.out); (out / "data").mkdir(parents=True, exist_ok=True)

    with open(a.judged, newline="", encoding="utf-8-sig") as fh:
        judged = list(csv.DictReader(fh))
    mentions_by_id = {}
    if Path(a.comments).exists():
        with open(a.comments, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                mentions_by_id[r.get("comment_id", "")] = [m for m in (r.get("mentions") or "").split(" | ") if m]
    all_names = sorted({n for v in mentions_by_id.values() for n in v}, key=len, reverse=True)

    labels = json.loads(Path(a.labels).read_text(encoding="utf-8"))
    risk_ids = [x["id"] for x in labels["risk_behavior"]]

    split = lambda v: [x for x in (v or "").split("|") if x]
    rows, withheld, scrubbed, skipped = [], 0, 0, 0

    NOISE_REL = {"off_topic", "promotion"}
    for i, r in enumerate(judged, 1):
        if (r.get("judge_error") or "").strip():
            skipped += 1
            continue
        if a.only_ontopic and r.get("relevance") in NOISE_REL:
            skipped += 1
            continue
        raw = r.get("body_only") or r.get("comment") or ""
        names = mentions_by_id.get(r.get("comment_id", ""), []) or all_names
        clean = scrub(raw, names)
        if clean != raw:
            scrubbed += 1
        if a.text == "none":
            text = ""
        elif a.text == "short" and len(clean) > a.text_max:
            text = ""
            withheld += 1
        else:
            text = clean
        rows.append({
            "id": f"c{i:04d}",
            "comment": text,
            "chars": len(clean),                 # length is published even when the text is not
            "relevance": r.get("relevance", ""),
            "risk_behaviors": r.get("risk_behaviors", ""),
            "primary_risk": r.get("primary_risk", ""),
            "risk_verbatim": scrub(r.get("risk_verbatim", ""), names),
            "relation": r.get("relation", ""),
            "cancer_type": r.get("cancer_type", ""),
            "health_seeking": r.get("health_seeking", ""),
            "outcome": r.get("outcome", ""),
            "note": scrub(r.get("note", ""), names),
            "conf_overall": r.get("conf_overall", ""),
            "flags": r.get("flags", ""),
        })

    # ---- long format -------------------------------------------------------
    long_path = out / "data" / "analysis.csv"
    with long_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # ---- one-hot format ----------------------------------------------------
    oh_path = out / "data" / "analysis_onehot.csv"
    base = ["id", "relevance", "relation", "cancer_type", "outcome", "conf_overall"]
    with oh_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(base + [f"risk_{x}" for x in risk_ids] + ["n_risks"])
        for r in rows:
            s = set(split(r["risk_behaviors"]))
            real = s - {"none_mentioned"}
            w.writerow([r[c] for c in base] + [1 if x in s else 0 for x in risk_ids] + [len(real)])

    # ---- aggregates --------------------------------------------------------
    NOISE = {"off_topic", "promotion"}
    signal = [r for r in rows if r["relevance"] not in NOISE]
    risk_of = lambda r: set(split(r["risk_behaviors"])) - {"none_mentioned"}
    counts = Counter(b for r in signal for b in risk_of(r))
    cooc = defaultdict(int)
    for r in signal:
        s = sorted(risk_of(r))
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                cooc[f"{s[i]}|{s[j]}"] += 1
    by_relevance = {}
    for kind in ("personal_story", "risk_opinion"):
        grp = [r for r in rows if r["relevance"] == kind]
        c = Counter(b for r in grp for b in risk_of(r))
        by_relevance[kind] = {"n": len(grp), "counts": dict(c)}
    summary = {
        "generated": date.today().isoformat(),
        "n_comments": len(rows), "n_on_topic": len(signal),
        "risk_counts": dict(counts.most_common()),
        "co_occurrence": dict(sorted(cooc.items(), key=lambda kv: -kv[1])),
        "by_relevance": by_relevance,
        "relevance": dict(Counter(r["relevance"] for r in rows)),
        "relation": dict(Counter(r["relation"] for r in signal)),
        "cancer_type": dict(Counter(r["cancer_type"] for r in signal)),
    }
    (out / "data" / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "data" / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- the page ----------------------------------------------------------
    payload = {
        "meta": {"title": a.title, "source": a.source_note,
                 "generated": date.today().isoformat(),
                 "analysed": len(rows), "errors": skipped, "pending": 0,
                 "text_policy": a.text, "text_max": a.text_max, "withheld": withheld},
        "labels": {k: {x["id"]: {"en": x.get("en", x["id"]),
                                 "short": x.get("short") or x.get("en", x["id"]),
                        "short_th": x.get("short_th") or x.get("short") or x.get("en", x["id"]),
                                 "match": x.get("match", []),
                                 "iarc": x.get("iarc", "na"),
                                 "iarc_note": x.get("iarc_note", ""),
                                 "th": x.get("th", "")} for x in labels.get(k, [])}
                   for k in ("relevance", "risk_behavior", "relation", "cancer_type", "behavior", "outcome")},
        "risk_group": [{"id": g["id"], "en": g.get("en", g["id"]),
                        "short": g.get("short") or g.get("en", g["id"]),
                        "short_th": g.get("short_th") or g.get("short", g["id"])}
                       for g in labels.get("risk_group", [])],
        "risk_of_group": {x["id"]: x.get("group", "other_group") for x in labels.get("risk_behavior", [])},
        "iarc_meta": labels.get("iarc_meta", {}),
        "thai_incidence": labels.get("thai_incidence", {}),
        "records": [{
            "id": r["id"], "comment": r["comment"], "chars": r["chars"],
            "relevance": r["relevance"], "risk": split(r["risk_behaviors"]),
            "primary": r["primary_risk"], "riskVerb": r["risk_verbatim"],
            "relation": r["relation"], "cancer": r["cancer_type"], "verbatim": "",
            "health": split(r["health_seeking"]), "outcome": r["outcome"],
            "note": r["note"],
            "conf": float(r["conf_overall"]) if r["conf_overall"] else None,
            "confRisk": None, "confRel": None, "flags": split(r["flags"]),
        } for r in rows],
    }
    tpl = Path(a.template).read_text(encoding="utf-8")
    (out / "index.html").write_text(
        tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")),
        encoding="utf-8")

    # ---- privacy audit -----------------------------------------------------
    # scan the DATA only — not the page title, CSS font stack or label definitions,
    # which are ours and would otherwise trip the name-shape check
    blob = json.dumps(payload["records"], ensure_ascii=False) + long_path.read_text(encoding="utf-8-sig")
    leaks = []
    for rx, what in [(LATIN_NAME, "a name-shaped Latin string"),
                     (THAI_TITLE_NAME, "a Thai title + name"),
                     (re.compile(r"https?://"), "a URL"),
                     (re.compile(r"facebook\.com"), "a facebook.com reference"),
                     (re.compile(r"[\w.+-]+@[\w-]+\.\w+"), "an email address"),
                     (re.compile(r"(?<!\d)0\d[\s-]?\d{3}[\s-]?\d{4}(?!\d)"), "a phone number")]:
        n = len(rx.findall(blob))
        if n:
            leaks.append(f"{n} x {what}")
    surviving = [n for n in all_names if n in blob]

    print(f"\nwrote {out}/index.html, {out}/data/*.csv, {out}/data/summary.json")
    print(f"\nPRIVACY AUDIT")
    print(f"  dropped columns          : {', '.join(DROP)}")
    print(f"  ids                      : replaced with sequential surrogates (c0001…)")
    print(f"  rows published           : {len(rows)}   ({skipped} unjudged/errored rows excluded)")
    print(f"  texts scrubbed           : {scrubbed} had a name or contact detail removed")
    print(f"  typed-in names removed   : {len(TYPED_NAMES_FOUND)}"
          + (f"  e.g. {sorted(set(TYPED_NAMES_FOUND))[:3]}" if TYPED_NAMES_FOUND else ""))
    print(f"  texts withheld           : {withheld}"
          + (f"  (--text short: longer than {a.text_max} chars)" if a.text == "short" else ""))
    print(f"  @-mentioned names left   : {len(surviving)}" + (f"  -> {surviving[:5]}" if surviving else "  (none)"))
    print(f"  contact patterns left    : {', '.join(leaks) if leaks else 'none'}")
    maybe = sorted({m for m in THAI_MAYBE_NAME.findall(blob)
                    if not any(m.replace("คุณ","").replace("พี่","").replace("หมอ","").startswith(k) for k in THAI_KIN)})
    if maybe:
        print(f"  REVIEW BY HAND           : {len(maybe)} คุณ/พี่/หมอ + word — could be given names:")
        print(f"                             {maybe[:10]}")
    if surviving or leaks:
        print("\n  !! Something identifying survived. Do not commit until this reads clean.")
        sys.exit(1)
    if a.text != "none":
        print("\n  !! --text %s publishes raw comment text. Name-scrubbing is BEST EFFORT only:" % a.text)
        print("     Thai names (อี๊ฟ อรทัย), initials (Witsarut P K-ros), diacritics (Pätcharee Saelëë)")
        print("     and names fused to Thai text (Mink Chruaphetที่บ่น) all defeat pattern matching.")
        print("     Do not publish comment text unless a human has read every row.\n")
    else:
        print("\n  Clean. Comment text is withheld entirely (--text none), which is the only")
        print("  setting where name-freedom is guaranteed rather than attempted.\n")


if __name__ == "__main__":
    main()
