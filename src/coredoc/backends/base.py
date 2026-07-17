from __future__ import annotations

from abc import ABC, abstractmethod

from coredoc.models import DoctorResult
from coredoc.runner import CommandRunner


class Doctor(ABC):
    module: str
    title: str

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    @abstractmethod
    def gather(self) -> DoctorResult: ...
