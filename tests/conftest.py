import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def tmp_path_custom(tmp_path):
    return tmp_path
