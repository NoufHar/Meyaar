# Meyaar

**Agentic AI for Geospatial Data Quality & Standards Compliance**

Meyaar is an intelligent geospatial data quality assessment platform designed to validate vector datasets and inspect map images, detect quality issues, explain findings, and generate human-readable recommendations and reports.

The system combines deterministic geospatial validation using PostgreSQL/PostGIS, an agent-based analysis layer, a vision model for map-image inspection, reporting, voice summaries, and an interactive React interface.

---

## Overview

Geospatial datasets often contain topology, geometry, coordinate reference system, attribute, and cartographic quality issues.

Manually reviewing these problems can be time-consuming and inconsistent.

Meyaar provides an automated workflow that:

- Accepts geospatial vector datasets.
- Inserts data into PostgreSQL/PostGIS.
- Runs deterministic spatial validation rules.
- Detects and locates geospatial quality issues.
- Uses an Error Analysis Agent to explain detected findings.
- Provides causes and recommended corrective actions.
- Visualizes errors on an interactive map.
- Inspects map images using a Vision model.
- Generates quality reports.
- Produces Arabic audio summaries.
- Supports Telegram report delivery.
- Provides a context-aware Chat Assistant for explaining existing results.

---

# System Architecture

## Vector Dataset Pipeline

```text
Vector Dataset
      |
      v
Insertion Agent
      |
      v
PostgreSQL / PostGIS
      |
      v
Validation Rules
      |
      v
Error Detection
      |
      v
Error Analysis Agent
      |
      v
Explanation + Cause + Recommendation
      |
      +-------------------+
      |                   |
      v                   v
Interactive Map        Quality Report
                          |
                          v
                PDF + Arabic Audio