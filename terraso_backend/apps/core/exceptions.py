from dataclasses import dataclass

from .formatters import from_snake_to_camel_case


@dataclass
class ErrorContext:
    model: str
    field: str
    extra: str = ""

    def __post_init__(self):
        self.field = from_snake_to_camel_case(self.field) if self.field else self.field


@dataclass
class ErrorMessage:
    code: str
    context: ErrorContext
