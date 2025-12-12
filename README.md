# sitrepc2 — Project Overview

**sitrepc2** is an automated OSINT processing engine that transforms raw, narrative battlefield reporting into structured, geolocated, operationally meaningful data. It is built for high-precision extraction of military activity from Telegram posts, news updates, and similar unstructured sources.

The system ingests natural-language text, detects relevant events, resolves locations, interprets military actors and actions, and outputs clean, mappable intelligence suitable for situational reporting, dashboards, or geospatial tools.

---

## Requirements

Holmes-Extractor requires both a spaCy pipeline and a large vector model. If you enable transformer support, spaCy will load both the vector and transformer models concurrently.

**Recommended Minimums:**

- **8 GB RAM**  
  - spaCy vector model: `en_core_web_lg`

- **16 GB RAM**  
  - `en_core_web_lg` + `en_core_web_trf`  
  - Required for best Coreference + Holmes performance

sitrepc2 adds lightweight entity-ruler rules and a domain lexicon. These additions have minimal overhead relative to the core NLP pipeline.

---

# 1. High-Precision Gazetteer & Geospatial Intelligence Layer

The gazetteer is backed by a **SQLite database** (`sitrepc2_seed.db`) initialized via `schema.sql` and accessed through `src/sitrepc2/db/`.  
It replaces all prior CSV lookups.

### Gazetteer Features
- Complete database of:
  - settlements  
  - admin regions  
  - aliases & exonyms  
  - operational groups  
  - directional clusters
- Deterministic ID-based lookup using canonical keys (CID, region OSM IDs, group IDs).
- Fast multilingual alias resolution.
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
- Location disambiguation using the database, aliasing, and spatial context
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
  - actors, assets
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
  All reference data is unified in the SQLite schema, enabling reproducibility and efficient updates.

---

# Summary

sitrepc2 provides an end-to-end engine for converting battlefield text reports into structured, geospatially valid military activity datasets.  
It is built for analysts who need transparent, reproducible, high-precision event extraction and mapping.

