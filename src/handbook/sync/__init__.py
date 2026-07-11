"""The Codeforces sync package: the first end-to-end usable workflow.

.. code-block:: text

    cp-handbook init    # configure a Codeforces handle + vault
    cp-handbook sync    # fetch new accepted submissions, update the vault
    cp-handbook status  # see what's configured and what's been synced

``sync`` runs the full pipeline for every newly accepted submission:

.. code-block:: text

    Submission (Codeforces)
        -> Problem object          (handbook.sync.mapping)
        -> Knowledge object        (models.Problem, a KnowledgeItem)
        -> Store                   (Handbook.store -- existing engine)
        -> Graph update            (GraphBuilder -- existing engine)
        -> Revision note           (structured intermediate format,
                                     NOT a final handwritten note)

No AI, no MCP, no recommendation engine -- see the module docs on each
submodule for what's deliberately left out and why.
"""

from __future__ import annotations

from handbook.sync.codeforces import (
    CFProblem,
    CFSubmission,
    CodeforcesAPIError,
    CodeforcesClient,
    CodeforcesError,
    CodeforcesTransportError,
)
from handbook.sync.config import SyncConfig
from handbook.sync.pipeline import SyncedProblem, SyncReport, run_sync
from handbook.sync.revision_note import RevisionNote, generate_revision_note
from handbook.sync.state import SyncState

__all__ = [
    "CFProblem",
    "CFSubmission",
    "CodeforcesClient",
    "CodeforcesError",
    "CodeforcesAPIError",
    "CodeforcesTransportError",
    "SyncConfig",
    "SyncState",
    "SyncedProblem",
    "SyncReport",
    "run_sync",
    "RevisionNote",
    "generate_revision_note",
]
