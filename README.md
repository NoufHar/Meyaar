# Meyaar

**AI-powered geospatial data quality and compliance validation for Saudi geospatial standards.**

Meyaar is a work-in-progress research/MVP project for evaluating GIS datasets and map images using a combination of geospatial topology analysis, machine learning, vision models, and retrieval-augmented generation (RAG).

> Meyaar is designed to support validation against selected GeoSA standards and guidelines. It is not an official GeoSA certification tool.

## Current Work

The repository currently contains five experimental notebooks:

| Notebook | Purpose |
|---|---|
| `01_topo4vec_baseline.ipynb` | Baseline experiments for controlled topology-error generation and representation learning |
| `02_xgboost_topology_features.ipynb` | Topology-feature extraction and XGBoost classification experiments |
| `03_vision_florence2.ipynb` | Vision experiments on map images using Florence-2 |
| `04_element_presence.ipynb` | Paired experiments for detecting presence/missing map elements |
| `05_geosa_rag.ipynb` | Initial GeoSA knowledge retrieval / RAG experiments |

## MVP Scope

### Roads
- Overshoot
- Undershoot
- Duplicate geometry
- Invalid geometry
- Missing geometry

### Buildings
- Overlap
- Duplicate geometry
- Invalid geometry
- Missing geometry

### General GIS Validation
- Missing or incorrect CRS
- Invalid coordinates
- Missing required attributes
- Wrong data types
- Invalid attribute values

### Map Images
- Missing title
- Missing legend
- Missing scale
- Missing north arrow
- Element overlap
- Element clipping
- Text/label overlap
- Illegible text

## Approach

Meyaar is being developed as several complementary components:

1. **GIS validation and controlled error injection** for creating labeled topology examples.
2. **Machine-learning experiments** for classifying selected geospatial quality errors.
3. **Vision experiments** for detecting map-layout and cartographic element issues.
4. **GeoSA RAG** for retrieving relevant requirements and supporting compliance explanations.
5. **Rule-based validation** for deterministic checks where explicit geospatial rules are more appropriate.

## Meyaar-SA Benchmark

A core project goal is the creation of a reproducible labeled benchmark for selected Saudi geospatial quality tasks.

For GIS experiments, the intended workflow is:

`Real geospatial data → controlled error injection → ground-truth labels → train/test split → evaluation`

Example ground-truth fields include:

- `feature_id`
- `error_type`
- `severity`
- `rule_id`

## Data

The working dataset is intentionally **not stored directly in this Git repository** because several source and processed files are hundreds of megabytes.

Current working data includes:
- Riyadh road geometries
- Riyadh building geometries
- Riyadh connector geometries
- Map-image datasets
- GeoSA standards and supporting reference documents

See [`data/README.md`](data/README.md) for the dataset organization.

## Repository Structure

```text
Meyaar/
├── README.md
├── requirements.txt
├── .gitignore
├── LICENSE
├── notebooks/
├── data/
│   └── samples/
├── references/
├── results/
│   ├── figures/
│   └── metrics/
└── docs/
```

## Installation

```bash
git clone https://github.com/NoufHar/Meyaar.git
cd Meyaar
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
pip install -r requirements.txt
```

The notebooks are primarily intended to be run independently while the MVP pipeline is under development.

## Evaluation

Depending on the component, evaluation includes:

- Accuracy
- Precision
- Recall
- F1-score
- Confusion matrix
- ROC-AUC where appropriate
- Spatial holdout evaluation
- Per-element vision accuracy/F1
- RAG retrieval quality and citation grounding

## Roadmap

- [x] Prepare Riyadh road/building datasets
- [x] Controlled topology-error experiments
- [x] Baseline ML experiments
- [x] XGBoost topology-feature experiments
- [x] Initial vision experiments
- [x] Initial GeoSA RAG experiment
- [ ] Consolidate Meyaar-SA benchmark
- [ ] Implement documented validation rules
- [ ] Integrate vision validation pipeline
- [ ] Integrate GeoSA RAG with validation output
- [ ] Add compliance score and error report
- [ ] Build unified MVP interface

## Data and Reference Licensing

Code in this repository is licensed under the MIT License. External datasets, standards, map images, and reference documents retain their original licenses and terms of use and are not relicensed by this repository.
