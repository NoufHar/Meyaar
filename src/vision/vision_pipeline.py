from io import BytesIO

from PIL import Image

from src.vision.image_preprocessor import preprocess_image


def prepare_image_for_model(content: bytes) -> Image.Image:
    """Open uploaded image bytes and prepare them for vision inference."""
    with Image.open(BytesIO(content)) as image:
        return preprocess_image(image)
