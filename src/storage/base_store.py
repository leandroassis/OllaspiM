from abc import ABC, abstractmethod
from typing import Any, List, Dict

class GraphStoreInterface(ABC):
    """Interface for Knowledge Graph storage."""
    
    @abstractmethod
    def add_document(self, document_id: str, content: str, metadata: Dict[str, Any]):
        pass
        
    @abstractmethod
    def query(self, query_str: str) -> str:
        pass

class VectorStoreInterface(ABC):
    """Interface for Vector storage."""
    
    @abstractmethod
    def add_documents(self, documents: List[Dict[str, Any]]):
        pass
        
    @abstractmethod
    def query(self, query_str: str, top_k: int = 5) -> List[str]:
        pass
