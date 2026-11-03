"""Put the pipeline modules on the path.

In the project this was extracted from, underwrite.py and its helpers sit at
the repository root and the tests import them directly. Here they live under
src/, so the imports need the directory added -- otherwise `pytest tests/`,
which the README tells readers to run, fails at collection.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)


import pytest


@pytest.fixture
def client():
    """The Flask app is not part of this repository.

    The source project serves the payload and the page from app.py; what is
    published here is the pipeline, the data and the write-up, so the route
    tests have nothing to drive. They skip rather than error, and the asset
    they would have checked is checked directly by the file-level tests.
    """
    pytest.skip("app.py is not published in this repository (pipeline + data only)")
