# sitrepc2 — Project Overview

**sitrepc2** is an automated OSINT processing engine that transforms raw, narrative battlefield reporting into structured, geolocated, operationally meaningful data. It is built for high-precision extraction of military activity from Telegram posts, social media, news updates, and similar unstructured sources.

The system ingests natural-language text, detects relevant events, resolves locations, interprets military actors and actions, and outputs clean, mappable intelligence suitable for situational reporting, dashboards, or geospatial tools.

---

## Requirements

Holmes-Extractor requires both a spaCy pipeline and a large vector model. If you enable transformer support, spaCy will load both the vector and transformer models concurrently.

### Recommended Minimums

- **8 GB RAM**
  - spaCy vector model: `en_core_web_lg`

- **16 GB RAM**
  - `en_core_web_lg` + `en_core_web_trf`
  - Required for best Coreference + Holmes performance

sitrepc2 adds lightweight entity-ruler rules and a domain lexicon. These additions have minimal overhead relative to the core NLP pipeline.

---

## Machine Translation (Important)

sitrepc2 operates **internally on English text only**.  
Non-English sources are translated *during ingestion*.

### Translation behavior by source

| Source type | Translation method |
|------------|--------------------|
| Telegram | Native Telegram server-side translation (via Telethon) |
| Twitter/X | MarianMT (local, offline, zero-cost) |
| Facebook | MarianMT (local, offline, zero-cost) |
| HTTP / News | MarianMT (local, offline, zero-cost) |

### MarianMT model installation

Machine translation models are **not installed at package install time**.

They are:
- **Downloaded automatically on first use**
- Cached locally (Hugging Face cache)
- Reused across runs
- Fully offline after initial download

Approximate resource usage:
- **~300–400 MB disk per language model**
- **~1–1.5 GB RAM per model during translation**

No API keys, accounts, or licenses are required.

---

## Ingestion Sources

sitrepc2 supports multiple ingestion paths, all normalized into a single canonical `records.db` schema.

### Supported sources

- **Telegram**
  - Ingested via Telethon
  - Native translation available
  - High-confidence publish timestamps

- **Twitter / X**
  - Ingested via unofficial scraping (Twint)
  - No API keys required
  - Publish date and post ID extracted from platform metadata
  - Translation via MarianMT

- **Facebook**
  - Ingested via unofficial scraping (`facebook-scraper`)
  - Public pages and groups supported
  - Post ID and publish time extracted when available
  - Translation via MarianMT

- **HTTP / News sites**
  - Scraped using `requests` + `BeautifulSoup`
  - Article text extracted via Readability
  - Canonical article URL used as post ID
  - Publication date extracted conservatively from:
    - HTML metadata
    - JSON-LD
    - Date-encoded URL paths
    - HTTP headers (fallback)
  - Translation via MarianMT

All sources are configured uniformly via `sources.jsonl`.

---

# 1. High-Precision Gazetteer & Geospatial Intelligence Layer

The gazetteer is backed by a **SQLite database** (`sitrepc2_seed.db`) initialized via schema files and accessed through `src/sitrepc2/gazetteer/`.

It replaces all prior CSV lookups.

### Gazetteer Features

- Complete database of:
  - settlements
  - admin regions
  - aliases & exonyms
  - operational groups
  - directional clusters
- Deterministic ID-based lookup using canonical keys (CID, region OSM IDs, group IDs)
- Fast multilingual alias resolution
- Integrated geospatial utilities:
  - frontline distance calculations
  - directional axes
  - clustering and spatial grouping
  - polygonal region intelligence (admin4 boundaries)

The gazetteer provides **high-confidence localization** for ambiguous battlefield references.

---

# 2. NLP + Holmes Event Extraction (LSS Layer)

Located under `src/sitrepc2/lss/`, this layer unifies:

- **Lexical** signals (domain lexicon, keyphrases)
- **Syntactic** structures (dependency analysis)
- **Semantic** pattern matching (Holmes rules)
- **Coreference resolution** for pronouns, anaphora, and repeated actors

The layer identifies:

- **Actors** (military units, formations, force groupings)
- **Actions** (attacks, advances, captures, strikes, shelling, repulsed attacks)
- **Assets** (armor, artillery, drones, missiles)
- **Locations or directional references**

It produces structured `EventMatch` records which serve as the intermediate semantic representation.

---

# 3. Domain Interpretation Layer (DOM Layer)

Located under `src/sitrepc2/dom/`, this layer converts event matches into final, operationally meaningful **Events**.

### Responsibilities

- Location disambiguation using the gazetteer and spatial context
- Computing final coordinate assignments
- Actor & asset normalization
- Event classification into operationally relevant categories
- Ensuring geospatial and semantic coherence:
  - resolving anchors and directional context
  - ensuring references match real places and valid military structures

This converts raw linguistic detections into **interpreted, geolocated, structured intelligence objects**.

---

# Purpose

To transform messy, ambiguous narrative battlefield reporting into:

**clean, structured, geospatially actionable intelligence.**

This enables:
- tactical and operational analysis
- situational awareness dashboards
- map overlays and time-series conflict visualizations

---

# Outputs

sitrepc2 produces:

- **Geolocated event objects** with:
  - event type
  - actors and assets
  - directionality and contextualization
  - confidence scoring

- **Frontline-relative spatial metrics**
- **Structured JSONL event streams**
- **Map-ready coordinates** suitable for GIS and analytical tools

---

# Design Principles

- **Strict separation of concerns**
  - Gazetteer layer
  - LSS (linguistic-semantic) extraction layer
  - DOM (domain interpretation) layer

- **Deterministic, auditable pipeline**
  Every stage from text ingestion → event extraction → geolocation is explicit and inspectable.

- **High precision over high recall**
  Ambiguous references must be provably disambiguated or excluded.

- **Database-driven canonicalization**
  All reference data is unified in SQLite schemas, enabling reproducibility and efficient updates.

---

# Summary

sitrepc2 provides an end-to-end engine for converting battlefield text reports from multiple open sources into structured, geospatially valid military activity datasets.

It is built for analysts who require **transparent, reproducible, high-precision event extraction and mapping**, without reliance on paid APIs or opaque services.
---

---

## License Constraints (Important)

This project is licensed under the **PolyForm Noncommercial License 1.0.0**.

### Default license terms

Under the default license, you may:

- Use this software for **research, academic, journalistic, or personal purposes**
- Study, modify, and redistribute the source code
- Create derivative works

**Provided that all use is non-commercial.**

You may **not**:

- Use this software as part of a **commercial product or paid service**
- Use it internally at a **for-profit organization** for commercial advantage
- Sell, license, or monetize the software or its outputs
- Incorporate it into proprietary or closed-source systems

### Share-alike requirement

If you distribute this software or any derivative work:

- You **must provide the complete source code**
- You **must license it under the same PolyForm Noncommercial License**
- You **may not impose additional restrictions**

---

## Commercial API Integration Exception

Notwithstanding the PolyForm Noncommercial License, the project author grants a
**limited commercial-use exception** under the following conditions:

Commercial use is permitted **only** if **all** of the following are true:

1. The user independently obtains and pays for **official, licensed APIs**
   for any third-party services accessed (e.g. Twitter/X, Facebook/Meta).

2. All integrations with those services are implemented **exclusively**
   using official APIs and in full
---
