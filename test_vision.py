from PIL import Image

from src.vision.image_preprocessor import preprocess_image

from src.vision import vision_model


def test_preprocess_converts_image_to_rgb():
    image = Image.new("RGBA", (100, 50))

    result = preprocess_image(image)

    assert result.mode == "RGB"


def test_preprocess_resizes_without_distortion():
    image = Image.new("RGB", (2000, 1000))

    result = preprocess_image(image, max_size=(1000, 1000))

    assert result.size == (1000, 500)


def test_preprocess_does_not_enlarge_small_images():
    image = Image.new("RGB", (200, 100))

    result = preprocess_image(image, max_size=(1000, 1000))

    assert result.size == (200, 100)



class FakeMoondreamModel:
    def query(
        self,
        image,
        question,
        settings,
    ):
        if "title" in question.lower():
            return {"answer": "no"}

        return {"answer": "yes"}


def test_analyze_image_builds_elements_and_issues(
    monkeypatch,
):
    monkeypatch.setattr(
        vision_model,
        "get_vision_model",
        lambda: FakeMoondreamModel(),
    )

    image = Image.new(
        "RGB",
        (100, 100),
        color="white",
    )

    result = vision_model.analyze_image(image)

    assert len(result["elements"]) == 4

    elements = {
        item["element"]: item["present"]
        for item in result["elements"]
    }

    assert elements == {
        "title": False,
        "legend": True,
        "scale": True,
        "north_arrow": True,
    }

    assert result["issues"] == [
        {
            "error_type": "missing_title",
            "severity": "warning",
            "message": (
                "The map does not contain "
                "a detectable title."
            ),
            "confidence": None,
        }
    ]
