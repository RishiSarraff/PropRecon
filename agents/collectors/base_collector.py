from abc import ABC, abstractmethod
from models.property_data import PropertyData, Confidence, Source
from rich.console import Console

console = Console()

class BaseCollector(ABC):

    def __init__(self, source: Source):
        self.source = source
        self.dead_letters: list[PropertyData] = []

    @abstractmethod
    def collect(self) -> list[PropertyData]:
        ...

    def dead_letter(self, prop: PropertyData, reason: str) -> PropertyData:
        prop.flags.append(reason)
        prop.confidence = Confidence.LOW
        self.dead_letters.append(prop)
        return prop

    def log(self, message: str) -> None:
        console.print(f"[PropRecon] {self.source.value} -> {message}")
        
    def validate_result(self, prop: PropertyData) -> PropertyData:
        if not prop.address or not prop.address.strip():
            console.print(f"[red] Dead letter --> missing address from {prop.source}[/red]")
            return self.dead_letter(prop, "missing address")
        
        if not prop.state:
            console.print(f"[red] Dead letter --> missing state from {prop.source}[/red]")
            return self.dead_letter(prop, "missing state")
        
        return prop



   
