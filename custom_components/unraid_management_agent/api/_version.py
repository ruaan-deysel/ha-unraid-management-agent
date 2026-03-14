"""
Version metadata for the vendored Unraid Management Agent API client.

Convention:
- ``__version__`` tracks the local vendored Python client revision in this repository.
- ``__upstream_feature_epoch__`` tracks the upstream UMA release train the
        vendored surface is aligned to.
- ``__upstream_release__`` tracks the exact upstream release audited when the
        vendored surface was last refreshed.
"""

__version__ = "1.6.1"
__upstream_feature_epoch__ = "2026.03"
__upstream_release__ = "2026.03.01"
