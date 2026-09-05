from io import BytesIO

from PIL import Image, UnidentifiedImageError


class InvalidImageError(ValueError):
    pass


def inspect_image(content: bytes) -> dict:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()

        with Image.open(BytesIO(content)) as image:
            return {
                "format": image.format or "UNKNOWN",
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
            }

    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError("The uploaded file is not a valid image.") from error