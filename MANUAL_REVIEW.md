# Manual name review — 2026-08-30

Scope: all 419 on-topic rows (`--only-ontopic`), every `comment`, `note` and
`risk_verbatim` field read.

Pattern matching alone is not sufficient here. Thai personal names have no
reliable orthographic signature, and the Latin-name regex was defeated by
diacritics (`Pätcharee Saelëë`), single-letter initials (`Witsarut P K-ros`),
and names fused to Thai text with no word boundary (`Mink Chruaphetที่บ่น`).

## Removed — 12 personal names, now in `REVIEWED_NAMES` in publish.py

Naruedon Maneewan · Alisa Stamp · Tanisorn Pongtanesuan · Phobchok Ploymukda
Zine Wannisa · Davarin Chankhum · Aelly Siwakornmetasit · Ken Luenthaisong
Thaweesak Khemchoknawee · Max Phutthimet · Boonma Thanapat · Mo Moo

Plus, from rows now excluded as off-topic: Witsarut P K-ros · Pätcharee Saelëë
Mink Chruaphet · อี๊ฟ อรทัย · S.tower · Jobi SK Nyrhinen · Fantar NG · Nguansuk

Also removed: one YouTube link in a comment.

## Checked and kept — not names

Enjoy eating · Surprise · Follow up · Anaplastic CA · WHO Cancer Prevention
Pigging · Healthy · Genetic · Eat · Hotdog

## Thai names

Four rows opened with a Thai token pair that pattern-matched as a possible
tagged name. All four are content, not names:

- `อากง อาโกว` — Chinese-Thai kinship terms (grandfather, aunt)
- `ควบคุม อารมณ์` — "control emotions"
- `กรรมพันธ์ เลือด` — "heredity, blood"
- `บางที เกิด` — "maybe caused by"

No Thai personal names remain in the 419.

## Limits of this review

Comments are read as text; a name written in an unusual form, or a person
identifiable from the situation they describe rather than from a name, would
not be caught. 74 comments over 200 characters are withheld entirely, which is
where such detail concentrates.
