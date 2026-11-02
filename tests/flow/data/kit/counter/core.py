"""The covered class (only its name and methods matter to the model's covers=)."""
from .config import Config


class Counter:
    def __init__(self, config=None):
        self.config = config or Config()

    def rent(self, tool):
        return tool

    def give_back(self, tool):
        return tool
