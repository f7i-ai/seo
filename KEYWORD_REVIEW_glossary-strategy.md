# Keyword review: definition-type keywords & glossary strategy

## Summary

**Yes—2000-word blog pages are overkill for “what is X” / definition / meaning keywords.** Use **short glossary or definition pages** (roughly 400–800 words) that give a clear, quotable definition and **link to your deeper content** on the same topic. That matches intent, SERP features, and keeps your site structure clear.

---

## What’s in the CSV

- **File:** `unplanned-downtime_list_2026-02-13.csv`  
- **~249 rows** match definition-style patterns: `what is`, `definition`, `meaning`, `define`, etc.
- **Topics:** Mix of downtime, maintenance, OEE, CMMS, QA, lead time, assets, calibration, FMEA, SOPs, and more.
- **Downtime examples:**  
  `downtime meaning`, `define downtime`, `definition downtime`, `downtime definition` (plus “what is unplanned downtime” style variants elsewhere).

SERPs for these often show **Knowledge Panel**, **Instant Answer**, **Featured Snippet**, **People Also Ask**—i.e. short, direct answers. Users are looking for a quick definition, not a long guide.

---

## Recommendation: glossary / definition pages

### 1. **Use a dedicated content type for definition-style keywords**

- **Glossary/definition page:** one clear definition, 1–2 short paragraphs of context, optional “in practice” or “related terms” snippet.
- **Length:** ~400–800 words (enough to be useful and rank, not padded).
- **Must:**  
  - Answer the query in the first 1–2 sentences (definition + one line of context).  
  - Include **internal links to your deeper content** on the same topic (e.g. “What is unplanned downtime?” → link to “Unplanned downtime: causes, cost, and how to reduce it” or “How to calculate and reduce unplanned downtime”).

### 2. **How to treat them in your structure**

- **Option A – Glossary section**  
  - One area, e.g. `/glossary/` or `/resources/glossary/`.  
  - One URL per term: e.g. `/glossary/unplanned-downtime`, `/glossary/oee`, `/glossary/cmms`.  
  - Each page: definition + 2–3 “Read more” links to pillar or long-form articles.

- **Option B – Short “What is X?” pages**  
  - Same idea as Option A but framed as “What is unplanned downtime?” etc.  
  - Still short (400–800 words), still with clear definition up top and links to deeper content.

Both satisfy “link to deeper content on the same topic”; choose based on URL and nav preference.

### 3. **Identifying definition-type keywords**

You can flag them in the CSV (or in code) with patterns like:

- `what is …`, `what are …`, `what does X mean`
- `… definition`, `definition of …`, `define …`
- `… meaning`, `meaning of …`
- SERP Intent = “Informational” **and** SERP features include “Knowledge Panel” or “Instant Answer”

Use that to route keywords to **glossary/definition** vs **standard/pillar** content.

### 4. **Linking to deeper content**

- For each glossary/definition page, **require** at least 2–3 internal links to:
  - Pillar or hub pages (e.g. “Unplanned downtime”, “Predictive maintenance”)
  - How-to or “reducing / calculating” articles on the same topic
- In the generator: pass existing URLs (from sitemap or a mapping of “topic → URLs”) and instruct the model to add a “Learn more” or “Related” block that links to those pages.

---

## Current generator behaviour

- **All articles** are forced to **≥2000 words** (`BlogPost` body validator and expansion logic).
- **Page type** (Pillar / Sub) and **Intent** are read from the CSV but **not** used to change format or length.
- So definition-style keywords are currently treated like standard blog posts → overkill and misaligned with intent.

---

## Next steps (implementation)

1. **Add a “glossary” or “definition” content mode** in the SEO content generator:
   - Target length ~400–800 words.
   - Prompt: “One clear definition in the first 1–2 sentences; brief context; then a ‘Learn more’ section with internal links to [list or topic].”
2. **Auto-detect definition-style keywords** (regex or tag in CSV) and either:
   - Route them to glossary mode when generating, or  
   - Export a “glossary keywords” list and generate those separately.
3. **Ensure internal links** for glossary pages use your real pillar/deep URLs (sitemap or topic → URL map).
4. **(Optional)** Add a column to the CSV, e.g. **Content type:** `pillar` | `sub` | `glossary`, and use it in the pipeline so you can maintain the split in one place.

---

## Implemented in `seo_content_generator.py`

### Auto-classify mode (recommended)

The generator now supports **auto-classification** of keywords into the best content format. Select mode **1 (Auto-classify)** at startup and each keyword is classified into one of:

| Format | Words | Trigger patterns | Examples |
|---|---|---|---|
| **Glossary/definition** | 400–800 | "what is X", "X definition", "define X", "X meaning" | "what is unplanned downtime", "OEE definition" |
| **Structured Q&A** | 800–1500 | "why X", "how to X", "can X", "is X worth it", "how much/long/many" | "why bearings fail", "how to detect bearing failure early", "can predictive maintenance work on conveyors" |
| **Comparative** | 1500–2500 | "X vs Y", "best/top X", "alternatives to X", "X competitors", product-category searches | "augury vs skf", "best CMMS for food manufacturing", "predictive maintenance software manufacturing" |
| **Industry data** | 1500–2500 | Industry keyword + data/cost/ROI/benchmark keyword | "predictive maintenance roi food manufacturing" |
| **Blog** | 3000+ | Catch-all for broad topics | "how predictive maintenance actually works", "ways to improve maintenance reliability" |

Shorter formats automatically use the fast research model.

### Legacy modes

- **Standard (mode 2):** All keywords → blog posts (3000+ words)
- **Pillar (mode 3):** All keywords → comprehensive hub content (4500+ words)
- **AI Visibility (mode 4):** All keywords → ChatGPT/Gemini citation-optimised (3500+ words)

### Key functions

- `classify_keyword(keyword)` — auto-classifies a keyword into `ContentFormat.BLOG`, `COMPARATIVE`, `STRUCTURED_KNOWLEDGE`, `GLOSSARY`, or `INDUSTRY_DATA`.
- `is_definition_type_keyword(keyword)` — legacy helper, returns True for definition-style patterns.
- `ContentFormat` — class with format constants and human-readable labels.
