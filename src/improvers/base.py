from abc import ABC, abstractmethod

class TextImprover(ABC):
    @abstractmethod
    def improve(self, text: str) -> str: ...
    def close(self) -> None:  # optional hook
        pass
