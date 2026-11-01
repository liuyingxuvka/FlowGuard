"""Settings of the counter (as in the small kit: a frozen dataclass with defaults)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    loan_days: int = 7
    max_on_loan: int = 3
    inspect_every: int = 5        # a tool is inspected after this many rentals (0: never)
    maintain_every: int = 4       # a tool gets a maintenance after this many rentals (0: never)
