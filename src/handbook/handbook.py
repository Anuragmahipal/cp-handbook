from pathlib import Path
from datetime import datetime

from handbook.models import Algorithm
from handbook.settings import settings
from handbook.template_engine import render
from handbook.utils.filesystem import ensure_directory
from handbook.utils.slug import note_slug


class Handbook:

    def __init__(self):

        self.root = settings.vault_path

    def create_algorithm(self, title: str):

        algorithm = Algorithm(title=title)

        folder = self.root / "Algorithms"

        ensure_directory(folder)

        filename = note_slug(title) + ".md"

        path = folder / filename

        if path.exists():
            return path

        markdown = render(
            "algorithms/algorithm.md.j2",
            **algorithm.model_dump(),
        )

        path.write_text(markdown, encoding="utf-8")

        return path
