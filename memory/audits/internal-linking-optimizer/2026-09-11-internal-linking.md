# Internal linking audit — drivingschoolliverpool.sydney

Date: 2026-09-11
Scope: all 45 built pages in the repo
Method: `internal-linking-optimizer` (v9.9.12 methodology, retrieved from the
frozen upstream copy; both local copies in `seo-geo-claude-skills-main/` are
redirect stubs with no methodology text)
Tooling: `tools/link-audit.py` in this repo, re-runnable

## Metric labelling

Every figure below is **Measured** from the HTML in this repo. No traffic,
impression, ranking or backlink data was available to this audit, so no metric
that depends on those is reported, and none is estimated.

## Phase 1 — structure

| Metric | Before | After |
|---|---|---|
| Pages | 45 | 45 |
| Internal links | 2,911 | 1,928 |
| Footer share of all links | 1,758 (60%) | 1,098 (57%) |
| Contextual links in `<main>` | 1,011 | 688 |
| Average contextual out-links per page | 22.5 | 15.3 |
| Structure score | 85 / 100 | **100 / 100** |

Score deductions applied per the methodology: −10 per orphan, −5 per important
page deeper than 3 clicks, −5 per page with zero contextual inbound links, −10
if average links per page falls outside the target band.

## Phase 2 — orphans

| Condition | Before | After |
|---|---|---|
| Zero inbound links of any kind | 0 | 0 |
| Zero **contextual** inbound links | 3 | 0 |
| Deeper than 3 clicks from home | 0 | 0 |

The three pages with no contextual inbound were `/driving-lessons-service-areas/`
(the service-area hub itself), `/review-policy/` and
`/learner-referral-program-terms-and-conditions/`. All three now receive
in-copy links. No decision gate was triggered: none was a high-value orphan of
unknown merit.

## Phase 3 — anchor text

| Metric | Before | After |
|---|---|---|
| Contextual anchors | 1,011 | 688 |
| Distinct anchor strings | 119 | 286 |
| Generic anchors ("click here", "read more") | 0 | 0 |
| Targets where one exact anchor is >70% of inbound | 15 | 3 |

Anchor score: **8 / 10**. No generic anchors and strong entity coverage. The
deduction is for the three suburb pages still dominated by a bare place-name
anchor, and for the unresolved duplicate below.

The two primary commercial pages are now the healthiest in the graph:

| Page | Contextual inbound | Distinct anchors |
|---|---|---|
| `/driving-test-preparation-practice-test/` | 49 | 39 |
| `/driving-test-car-hire/` | 28 | 26 |

## Phase 4 — topic clusters

Restored to hub-and-spoke. Internal PageRank spread went from effectively flat
(nearly every page at 0.0266) to 9.4× between top and bottom, which is what
tells a crawler which pages the site considers important.

| Node | Role | PageRank | Contextual inbound |
|---|---|---|---|
| `/driving-lessons-service-areas/` | Suburb pillar | 0.0397 | 52 |
| `/our-services/` | Lesson-type pillar | 0.0394 | 33 |
| `/driving-test-preparation-practice-test/` | Primary commercial | 0.0393 | 49 |
| `/driving-test-car-hire/` | Primary commercial | 0.0392 | 28 |
| Policy pages | Tail | 0.0042–0.018 | 1–3 |

## Phase 5 — contextual placements

39 in-copy placements are defined in `templates/internal-links.json` and applied
by `tools/import-pages.py`. All 39 are verified present in the built HTML. The
anchor for each is the first phrase from an ordered preference list that
actually occurs in that page's body copy, so no anchor is bolted on.

| Target | Placements |
|---|---|
| `/driving-test-preparation-practice-test/` | 19 |
| `/driving-test-car-hire/` | 6 |
| `/automatic-driving-lessons/` | 5 |
| `/driving-instructors-liverpool/` | 5 |
| `/beginner-driving-lessons-liverpool/` | 4 |

## Phase 6 — navigation and footer

The footer previously carried a 12-item lesson list and a 15-item suburb list on
all 46 footers, which was 60% of every link on the site and the main cause of the
flattening. Both were cut to five curated links plus a link to the matching hub.
The Macquarie Fields test-centre link was repointed from the generic services
page to that suburb's own page.

Discovery moved into content where it belongs: suburb pages carry four
lesson links named with the suburb, lesson pages carry three siblings with
hand-written anchors, and the full 48-suburb directory now appears only on the
service-areas hub instead of on all 26 generated pages.

## Phase 7 — outstanding

1. **Unresolved duplicate.** `/driving-lessons-chipping-norton/` and
   `/driving-school-chipping-norton/` target the same suburb and the same
   intent, and both receive the identical anchor "chipping norton" 27 and 26
   times. Needs a canonical or a 301; this is an owner decision.
2. **`/contact-us/` is heavily linked** from body copy across the site. Worth
   reviewing whether some of those should point at a commercial page instead.
3. **Elizabeth Drive vs Orange Grove Road.** The footer names the Liverpool test
   centre as Elizabeth Drive; imported page copy puts it on Orange Grove Road,
   Warwick Farm. One is wrong.
