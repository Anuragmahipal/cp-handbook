from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from handbook.renderers import filters

ROOT = Path(__file__).resolve().parents[2]

TEMPLATE_DIR = ROOT / "templates"

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Reusable rendering helpers (handbook.renderers.filters), available to every
# template under the same name they're defined with. Registering them here,
# once, is what makes them "reusable" rather than reimplemented per template.
env.filters.update(
    {
        "blockquote": filters.blockquote,
        "editable_block": filters.editable_block,
        "mermaid_escape": filters.mermaid_escape,
        "status_emoji": filters.status_emoji,
        "difficulty_emoji": filters.difficulty_emoji,
        "platform_emoji": filters.platform_emoji,
        "format_dt": filters.format_dt,
        "format_minutes": filters.format_minutes,
    }
)


def render(template_name: str, **kwargs) -> str:
    template = env.get_template(template_name)
    return template.render(**kwargs)
