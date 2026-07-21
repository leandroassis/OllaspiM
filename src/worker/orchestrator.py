import json
from pathlib import Path
from typing import List, Dict
from src.utils.logger import logger

class WorkerOrchestrator:
    """Manages the execution flow of technical tests filtering based on ensaios.json."""
    
    def __init__(self, ensaios_json_path: str = "ensaios.json"):
        self.ensaios_json_path = Path(ensaios_json_path)
        self.catalog = self._load_catalog()
        
    def _load_catalog(self) -> Dict[str, Dict[str, str]]:
        if not self.ensaios_json_path.exists():
            logger.warning(f"Arquivo de catálogo {self.ensaios_json_path} não encontrado. Assumindo dicionário vazio.")
            return {}
            
        try:
            with open(self.ensaios_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler {self.ensaios_json_path}: {e}")
            return {}
            
    def get_test_list(self, tests_file_path: Path) -> List[str]:
        """Reads the .txt file with test IDs to execute."""
        try:
            with open(tests_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return [line.strip() for line in lines if line.strip()]
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de testes {tests_file_path}: {e}")
            return []
            
    def filter_automatable_tests(self, test_ids: List[str]) -> List[Dict[str, str]]:
        """Filters the test list retaining only automatable ones."""
        valid_tests = []
        for tid in test_ids:
            if tid not in self.catalog:
                logger.warning(f"Ensaio {tid} não encontrado no catálogo. Pulando.")
                continue
                
            test_data = self.catalog[tid]
            if test_data.get("automatizavel", "Não").lower() == "não":
                logger.warning(f"Ensaio {tid} ignorado: {test_data.get('justificativa', 'Não é automatizável')}")
                continue
                
            valid_tests.append({"id": tid, **test_data})
            
        logger.info(f"Total de ensaios válidos para automação: {len(valid_tests)} de {len(test_ids)}")
        return valid_tests
