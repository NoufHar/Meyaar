# Backend and Vision Integration

## Overview

The vision backend analyzes map images using a fine-tuned Moondream model.
It checks whether the map contains a title, legend, scale, and north arrow.
Missing elements are returned as structured issues.

## Fine-Tuned Model

Model ID:

`moondream3-preview/01M1PM29FRHRPMRS7JE58SZPF9@200`

Training configuration:

- Natural training samples: 800
- LoRA rank: 8
- Learning rate: 2e-5
- Batch size: 4
- Epochs: 1
- Training steps: 200

Validation results:

- Base macro F1: 0.8111
- Fine-tuned macro F1: 0.8253

Final test results:

- Accuracy: 0.9127
- Macro F1: 0.9029

## Environment Variables

Create a `.env` file in the project root:

```env
MOONDREAM_API_KEY=your_api_key
MOONDREAM_MODEL_ID=moondream3-preview/01M1PM29FRHRPMRS7JE58SZPF9@200
```

The `.env` file contains secrets and must not be committed to GitHub.

## Run the API

```bash
python -m uvicorn src.api.main:app --reload
```

Open the interactive API documentation at `http://127.0.0.1:8000/docs`.

## Vision Endpoints

- `POST /images/inspect`: validates the image and returns its metadata.
- `POST /images/analyze`: analyzes the four required map elements.

Supported formats are PNG, JPG, JPEG, TIFF, and TIF. The maximum upload size
is 25 MB.

## Run Tests

```bash
python -m pytest test_vision.py test_api.py -v
```

Expected result: `9 passed`.
