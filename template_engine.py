from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from handbook.settings import settings

env = Environment(
    loader=FileSystemLoader(settings.template_path),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template: str, **kwargs) -> str:
    return env.get_template(template).render(**kwargs)
