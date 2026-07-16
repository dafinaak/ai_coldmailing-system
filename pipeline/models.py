from dataclasses import dataclass, field

@dataclass
class Lead:
    first_name: str
    last_name: str
    email: str
    company: str
    title: str
    website: str
    source: str
    notizen: list = field(default_factory=list)

    def __post_init__(self):
        self.email = self.email.strip().lower()
