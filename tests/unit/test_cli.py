import pytest
from src.cli.parser import parse_args, validate_paths
from src.utils.exceptions import PathNotFoundException

def test_parse_args_valid():
    args = parse_args(["--docs", "d", "--code", "c", "--past", "p", "--tests", "t", "--convert"])
    assert args.docs == "d"
    assert args.code == "c"
    assert args.past == "p"
    assert args.tests == "t"
    assert args.convert is True
    assert args.ingestion is False
    assert args.run is False

def test_parse_args_missing():
    with pytest.raises(SystemExit):
        parse_args(["--docs", "d"])

def test_validate_paths_success(base_test_dir):
    class MockArgs:
        docs = base_test_dir["docs"]
        code = base_test_dir["code"]
        past = base_test_dir["past"]
        tests = base_test_dir["tests"]
        
    paths = validate_paths(MockArgs())
    assert paths["docs"].exists()

def test_validate_paths_not_found():
    class MockArgs:
        docs = "non_existent_dir"
        code = "code"
        past = "past"
        tests = "tests.txt"
        
    with pytest.raises(PathNotFoundException):
        validate_paths(MockArgs())
