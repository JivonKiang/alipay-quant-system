"""
Base Strategy — 策略基类
参考: Qlib 策略层 + Freqtrade 策略接口
所有策略必须继承此类并实现 generate_signals 方法
"""
from abc import ABC, abstractmethod
from typing import List, Dict


class BaseStrategy(ABC):
    """策略抽象基类"""

    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def generate_signals(self, data: List[Dict]) -> List[Dict]:
        """
        生成交易信号
        data: [{date, nav, ...}, ...] 历史数据
        返回: [{date, action, reason, strength}, ...]
        """
        pass

    @abstractmethod
    def get_params(self) -> Dict:
        """返回策略参数（用于回测优化）"""
        pass

    def describe(self) -> str:
        """策略描述"""
        return f"{self.name}: {self.__doc__ or 'No description'}"
