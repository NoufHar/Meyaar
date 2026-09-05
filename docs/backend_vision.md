# Backend, Vision, and Vector Integration

## Overview

The Meyaar backend supports two geospatial processing workflows:

1. Vector data validation using PostgreSQL, PostGIS, and the Error Analysis Agent.
2. Optional map-image analysis using a fine-tuned Moondream vision model.

## System Workflows

### Vector Workflow

```text
Vector File
→ File Validation
→ Layer Detection
→ PostgreSQL/PostGIS
→ Spatial Validation Rules
→ Error Detection
→ Error Analysis Agent
→ Structured JSON
```

### Vision Workflow

```text
Map Image
→ Image Validation
→ Image Preprocessing
→ Fine-Tuned Moondream
→ Element-Presence Detection
→ Structured Issues
→ JSON
```

## Fine-Tuned Moondream Model

Model ID:

`moondream3-preview/01M1PM29FRHRPMRS7JE58SZPF9@200`

The model checks whether a map contains:

- Title
- Legend
- Scale
- North arrow

Missing elements are returned as structured warnings.

### Training Configuration

- Natural training samples: 800
- LoRA rank: 8
- Learning rate: 2e-5
- Batch size: 4
- Epochs: 1
- Training steps: 200

### Validation Results

- Base macro F1: 0.8111
- Fine-tuned macro F1: 0.8253

### Final Test Results

- Accuracy: 0.9127
- Macro F1: 0.9029

## Environment Variables

Create a `.env` file in the project root:

```env
MOONDREAM_API_KEY=your_api_key
MOONDREAM_MODEL_ID=moondream3-preview/01M1PM29FRHRPMRS7JE58SZPF9@200
MEYAAR_DATABASE_URL=postgresql+psycopg2://postgres@127.0.0.1:55432/meyaar_db
```

The `.env` file contains secrets and must not be committed to GitHub.

## Start Local PostGIS

Start the local development database:

```bash
docker compose -f docker-compose.vector-dev.yml up -d
```

Verify that the container is healthy:

```bash
docker ps
```

The local database is available at:

`postgresql+psycopg2://postgres@127.0.0.1:55432/meyaar_db`

Stop the local database when needed:

```bash
docker compose -f docker-compose.vector-dev.yml down
```

## Run the API

```bash
python -m uvicorn src.api.main:app --reload
```

Open the interactive API documentation:

`http://127.0.0.1:8000/docs`

## General Endpoint

- `GET /health`: checks whether the backend is running.

## Vision Endpoints

- `POST /images/inspect`: validates an image and returns its metadata.
- `POST /images/analyze`: analyzes the four required map elements.

Supported image formats:

- PNG
- JPG
- JPEG
- TIFF
- TIF

Maximum image upload size: 25 MB.

### Vision Output

The response contains:

- Uploaded filename
- Processing status
- Detected map elements
- Missing-element issues
- Optional confidence and location fields

Moondream does not provide a calibrated confidence score for this workflow.
Therefore, the confidence field is returned as `null`.

## Vector Processing Endpoint

- `POST /vectors/process`: runs the complete vector-processing workflow.

Supported vector formats:

- GeoJSON
- JSON
- GeoPackage
- CSV with WKT geometry
- CSV with longitude and latitude columns
- GeoParquet
- Zipped Shapefile

A zipped Shapefile must contain:

- `.shp`
- `.shx`
- `.dbf`
- `.prj` when CRS information is available

Maximum vector upload size: 100 MB.

The optional `layer_type` field accepts:

- `roads`
- `buildings`

If it is not provided, the backend attempts to detect the layer type from
the geometry and attributes.

### Vector Workflow Details

The endpoint:

1. Validates the uploaded file and extension.
2. Safely extracts zipped Shapefiles.
3. Loads the vector data using GeoPandas.
4. Detects or accepts the layer type.
5. Adds or standardizes feature identifiers.
6. Inserts the layer into PostgreSQL/PostGIS.
7. Runs the applicable spatial validation rules.
8. Generates a validation `run_id`.
9. Passes detected errors to the Error Analysis Agent.
10. Returns insertion, validation, and analysis results as JSON.

### Implemented Validation Rules

Depending on the layer, the PostGIS rule engine can detect:

- Overlapping features
- Invalid geometry
- Missing geometry
- Duplicate geometry
- Road overshoots and undershoots
- Missing or incorrect CRS
- Invalid coordinates
- Missing required attributes
- Invalid attribute values

### Error Analysis

For every detected error, the response can include:

- Error type
- Rule ID
- Layer name
- Feature ID
- Severity
- Status
- Explanation
- Cause
- Recommendation
- Human-review requirement
- Related features

When no external LLM is configured, the Agent uses its deterministic
template fallback while preserving the same response structure.

## Agent Endpoints

The Error Analysis Agent router is mounted under `/api`.

- `POST /api/validation/{run_id}/analyze`
- `GET /api/validation/{run_id}/analysis`
- `POST /api/validation/{run_id}/chat`

The chat endpoint requires the Agent's LLM configuration.

## Run Tests

Run all Backend and Vision tests:

```bash
python -m pytest test_vision.py test_api.py test_vector_api.py -v
```

Expected result:

```text
12 passed
```

The automated tests do not call the real Moondream API or require a real
PostGIS operation unless an explicit integration test is performed.

## Verified Integration Test

The complete Vector workflow was tested using a GeoJSON file containing two
duplicate road geometries.

The test successfully:

- Inserted two road features into PostGIS
- Detected two `RD003` duplicate-road errors
- Generated a validation `run_id`
- Passed both errors to the Error Analysis Agent
- Generated explanations and recommendations
- Returned the complete result as JSON

## Vector Benchmark Evaluation

The vector benchmark evaluator compares PostGIS validation results with a
ground-truth CSV file using the validation run ID.

It calculates the following metrics for each supported road error type:

- True positives
- False positives
- False negatives
- Precision
- Recall
- F1 score

Run the evaluator:

```bash
python -m tools.vector_benchmark_evaluator \
  --ground-truth "path/to/test_ground_truth.csv" \
  --run-id "validation-run-id" \
  --output-directory "outputs/vector_benchmark"