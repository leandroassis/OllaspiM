import pytest
import json
from pathlib import Path
from src.worker.orchestrator import WorkerOrchestrator

@pytest.fixture
def dummy_catalog(tmp_path):
    catalog_path = tmp_path / "ensaios.json"
    data = {
        "EN-01": {"descricao": "Test 1", "automatizavel": "Sim", "justificativa": "Validável"},
        "EN-02": {"descricao": "Test 2", "automatizavel": "Não", "justificativa": "Manual"},
    }
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return str(catalog_path)

def test_worker_orchestrator(dummy_catalog, tmp_path):
    tests_file = tmp_path / "test.txt"
    tests_file.write_text("EN-01\nEN-02\nEN-03")
    
    worker = WorkerOrchestrator(ensaios_json_path=dummy_catalog)
    test_ids = worker.get_test_list(tests_file)
    assert test_ids == ["EN-01", "EN-02", "EN-03"]
    
    valid_tests = worker.filter_automatable_tests(test_ids)
    assert len(valid_tests) == 1
    assert valid_tests[0]["id"] == "EN-01"
