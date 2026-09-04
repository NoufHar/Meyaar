from PIL import Image


DEFAULT_MAX_SIZE = (1024, 1024)


def preprocess_image(
    image: Image.Image,
    max_size: tuple[int, int] = DEFAULT_MAX_SIZE,
) -> Image.Image:
    """Convert an image to RGB and resize it without changing its aspect ratio."""
    prepared = image.convert("RGB")
    prepared.thumbnail(max_size, Image.Resampling.LANCZOS)
    return prepared
