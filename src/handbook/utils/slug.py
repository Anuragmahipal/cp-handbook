from slugify import slugify


def note_slug(title: str) -> str:
    return slugify(title)
