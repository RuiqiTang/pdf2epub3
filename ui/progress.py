# ui/progress.py
from abc import ABC, abstractmethod
from typing import Optional


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
    
    def update(self, message: str) -> None:
        """
        更新进度消息（可选方法，用于显示中间状态）
        
        Args:
            message: 要显示的消息
        """
        # 默认实现为空，子类可以重写
        pass