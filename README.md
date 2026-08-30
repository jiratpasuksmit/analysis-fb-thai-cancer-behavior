# พฤติกรรมเสี่ยงมะเร็งที่คนไทยพูดถึง
### What Thai Facebook commenters believe causes cancer

544 public comments from a single Thai Facebook post asking what behaviours people
believe cause cancer, labelled with a language model.

**[→ Open the interactive dashboard](https://jiratpasuksmit.github.io/analysis-fb-thai-cancer-behavior/)**

---

## ⚠️ Read this before using any number here

**These are beliefs, not causes.** Every figure counts what people *wrote* under one
Facebook post. It is not epidemiology, not a patient population, and not evidence
about what causes cancer. Some of the most-cited items (reheated food, incense smoke)
are not established causes; some established ones barely appear — smoking is named by
9% of on-topic comments, infection by 2%.

For what the evidence actually says: [WHO cancer fact sheet](https://www.who.int/news-room/fact-sheets/detail/cancer)
· [IARC classifications](https://monographs.iarc.who.int/list-of-classifications)

**No medical advice is given or intended here.** The author is not a clinician.

**Labels are not human-verified.** They were assigned by Gemini 3.7 Flash, one call
per comment, against a fixed label list. Accuracy has not been measured against human
annotation — treat every count as provisional.

**Self-selected sample.** People who felt strongly enough to comment are
over-represented. Dramatic outcomes and confident opinions travel; quiet ones do not.

## Privacy

Author names, profile links, @-mentions and the original Facebook comment ids were
removed before publication — dropped, not hashed, because a hash of a name still links
one person's comments together. Ids here (`c0001…`) are sequential surrogates and do
not map back to the source thread. Names typed into comment text were replaced with
`[ชื่อ]`. Comments longer than 200 characters are withheld entirely, because that is
where identifying detail concentrates: 76 of 544 rows show no text.

The raw HTML, the un-anonymised CSVs and the pipeline code are not in this repository.

If you recognise a comment as yours and want it removed, open an issue or contact
the repository owner.

## Files

| File | What it is |
|---|---|
| `index.html` | the dashboard — self-contained, no server or network needed |
| `data/analysis.csv` | one row per comment, labels in `\|`-separated columns |
| `data/analysis_onehot.csv` | same rows, one 0/1 column per risk — for pivot tables and stats |
| `data/labels.json` | the label definitions, English + Thai |
| `data/summary.json` | pre-computed counts and co-occurrence pairs |

## Columns

`id` · `comment` (empty where withheld) · `chars` · `relevance` · `risk_behaviors`
(multi-label) · `primary_risk` · `risk_verbatim` (the commenter's own wording) ·
`relation` · `cancer_type` · `health_seeking` · `outcome` · `note` (Thai summary by
the model) · `conf_overall` · `flags`

`risk_behaviors` is multi-label: percentages are shares of *comments* and do not sum
to 100%. No label id is a substring of another, so `str.contains` filters are safe.

```python
import pandas as pd
df = pd.read_csv("data/analysis.csv")
df["risks"] = df.risk_behaviors.fillna("").str.split("|").apply(set)
df[df.risks >= {"stress", "poor_sleep"}]          # named both
```

## Method, in short

Comments were copied from the rendered Facebook page, parsed on the `role="article"`
attribute, and stripped of tag-only comments (35 that only tagged friends). Each
remaining comment went to the model once, constrained by a JSON schema to a fixed
label list, at low reasoning effort. Confidence is the model's own and is poorly
calibrated — most rows sit above 0.85.

## Licence

Labels and counts in `data/`: CC BY-NC 4.0. The underlying comments remain the work
of their authors and are not licensed here.

## Pipeline (`scripts/`)

| script | what it does |
|---|---|
| `parse_fb.py` | rendered Facebook HTML → `comments.csv` (anchors on `role="article"`, drops tag-only comments) |
| `judge.py` | one headless Antigravity CLI call per comment, output constrained by JSON schema, checkpointed and resumable |
| `publish.py` | anonymises and builds this folder; exits non-zero if anything identifying survives |
| `labels.json` | the label space — edit this, not the code |
| `dashboard_template.html` | the page `publish.py` fills with data |

The scripts are here for transparency, not convenience: they need the raw
`data.txt`, which is not in this repository and will not be. Running them requires
the Antigravity CLI signed in to your own account. No credentials are stored in this
repo; `agy` reads its own config from `~/.gemini/`.
