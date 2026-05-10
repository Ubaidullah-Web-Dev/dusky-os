#!/usr/bin/env python3
from dataclasses import dataclass, field
from typing import Any, Literal, Dict, Tuple, List
from abc import ABC, abstractmethod

ConfigType = Literal["bool", "int", "float", "string", "cycle", "action", "menu", "picker", "color"]

@dataclass(kw_only=True)
class ConfigItem:
    label: str
    key: str
    scope: str = "DEFAULT"
    type_: ConfigType
    default: Any
    options: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    min_val: float | None = None
    max_val: float | None = None
    step: float | None = None
    value: Any = None

    def __post_init__(self) -> None:
        if self.value is None:
            self.value = self.default

class BaseEngine(ABC):
    """Abstract Base Class enforcing the contract for all mutator backends."""
    
    @property
    @abstractmethod
    def target_path(self) -> str:
        """Returns the primary target file path for UI display."""
        pass

    @abstractmethod
    def load_state(self) -> Dict[str, Any]:
        """Loads and returns a flattened dictionary of the current state."""
        pass

    @abstractmethod
    def write_value(self, target_key: str, target_scope: str, new_value: str) -> Tuple[bool, str, str]:
        """
        Commits a value change. 
        Returns (Success Boolean, Status Message, Debug Output).
        """
        pass
