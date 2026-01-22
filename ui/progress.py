# ui/progress.py
from abc import ABC, abstractmethod


class ProgressCallback(ABC):
    @abstractmethod
    def on_start(self, total_pages: int) -> None:
        pass

    @abstractmethod
    def on_page_processed(self, page_number: int) -> None:
        pass

    @abstractmethod
    def on_finish(self, output_path: str) -> None:
        pass