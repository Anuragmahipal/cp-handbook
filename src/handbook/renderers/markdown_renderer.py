from handbook.models import Algorithm
from handbook.template_engine import render


class MarkdownRenderer:

    @staticmethod
    def render(item):

        if isinstance(item, Algorithm):

            return render(
                "algorithms/algorithm.md.j2",
                **item.model_dump(),
            )

        raise TypeError(
            f"No renderer found for {type(item).__name__}"
        )
