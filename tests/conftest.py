import pytest
from pathlib import Path

@pytest.fixture
def base_test_dir(tmp_path):
    """Creates a temporary structure mimicking the tests directory for unit testing."""
    docs_dir = tmp_path / "docs"
    code_dir = tmp_path / "code"
    past_dir = tmp_path / "past"
    
    docs_dir.mkdir()
    code_dir.mkdir()
    past_dir.mkdir()
    
    test_file = tmp_path / "test.txt"
    test_file.touch()
    
    return {
        "docs": str(docs_dir),
        "code": str(code_dir),
        "past": str(past_dir),
        "tests": str(test_file)
    }
