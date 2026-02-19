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

- **Definition-type detection:** `is_definition_type_keyword(keyword)` returns True for patterns like "what is X", "X definition", "define X", "X meaning", "meaning of X".
- **Glossary mode:** When running in Standard mode (1), you are prompted: *"Use glossary format for definition-type keywords (what is X, X definition, meaning)? [y/N]"*. If you choose **y**, any keyword that matches the definition pattern gets:
  - **Short page (400–800 words):** definition in the first 1–2 sentences, brief context, then a **"Learn more"** section with 2–4 internal links to deeper content (from your sitemap).
  - **No 2000-word requirement:** content is accepted at 400–1200 words and still saved as a normal post (same JSON/MD and Prismic flow).
- **Linking:** The glossary prompt instructs the model to use only URLs from the available internal URLs list and to link to pillar guides, how-to articles, or in-depth guides on the same topic.

To use: run the generator in Standard mode, answer **y** to the glossary question, and use a CSV that includes your definition-type keywords (e.g. from `unplanned-downtime_list_2026-02-13.csv`). Ensure your sitemap is loaded so internal URLs are available for the "Learn more" links.
