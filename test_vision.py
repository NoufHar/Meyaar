from PIL import Image

from src.vision.image_preprocessor import preprocess_image


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
