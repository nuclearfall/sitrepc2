# sitrepc2 — Project Overview

**sitrepc2** is an automated OSINT processing engine designed to extract structured, geolocated military activity from unstructured text sources—primarily Telegram war‑reporting posts. It ingests raw narrative descriptions of battlefield events and transforms them into normalized, mappable data suitable for tactical and operational-level situational reporting.

## Requirements:
Holmes still requires en_core_web_lg. So if you choose to use spaCys transform model, just be aware that this will require both being in memory at the same time. Our addition to spaCy's entity rulers is fairly minimal, so it shouldn't impact requirements at all.

Recommended Minimums:
8 GB RAM with vector based spaCy model: en_core_web_lg)
16 GB RAM for transform based spaCy model: en_core_web_lg and en_core_web_trf

---

## 1. High-precision Gazetteer + Geospatial Intelligence Layer
- Curated multi-thousand-entry gazetteer of Ukrainian localities, regions, aliases, and operational groups.
- Fast and accurate lookup with multilingual alias resolution.
- Computes geospatial metrics such as frontline distance, clustering, and spatial context.

---

## 2. NLP + Holmes Event Extraction Layer (LSS Layer)
- Uses spaCy, Holmes-Extractor, and Coreference resolution to detect:
  - actors (units, formations, forces)
  - actions (attacks, movements, captures, strikes)
  - assets (armor, artillery, UAVs, missiles, etc.)
  - geospatial references (villages, cities, operational sectors)
- Produces structured **EventMatch** objects that unify lexical, syntactic, and semantic information.

---

## 3. Domain Interpretation Layer (DOM Layer)
- Converts NLP matches into domain-meaningful **Events** with:
  - disambiguated locations
  - final coordinates
  - event classification
  - actors, assets, and directionality
- Ensures outputs are operationally coherent and geospatially valid.

---

## Purpose
Transform messy, ambiguous, natural-language battlefield reporting into **clean, structured, geospatially actionable intelligence**.

---

## Outputs
- Geolocated events with type, actors, assets, direction, and confidence.
- Frontline-relative spatial analysis.
- Map-ready coordinate sets.
- Structured data suitable for dashboards, visualization, or mapping tools.

---

## Design Principles
- Strong separation between NLP, semantics, and domain reasoning.
- Deterministic, reproducible extraction pipeline.
- Fully auditable transformations from raw text → structured event.
- Human-curated gazetteer ensures accuracy in ambiguous regions.
