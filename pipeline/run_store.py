import json, re
from datetime import datetime
from pathlib import Path

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

class RunStore:
    def __init__(self, basis_dir, kunde_name, _existing: Path | None = None):
        if _existing is not None:
            self.run_dir = Path(_existing)
        else:
            stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.run_dir = Path(basis_dir) / _slug(kunde_name) / stempel
            self.run_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def resume(cls, run_dir) -> "RunStore":
        if not Path(run_dir).is_dir():
            raise ValueError(f"Laufordner existiert nicht: {run_dir}")
        return cls(None, None, _existing=run_dir)

    def _pfad(self, name: str) -> Path:
        return self.run_dir / f"{name}.json"

    def step_done(self, name: str) -> bool:
        return self._pfad(name).exists()

    def save_step(self, name: str, daten):
        self._pfad(name).write_text(
            json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_step(self, name: str):
        return json.loads(self._pfad(name).read_text(encoding="utf-8"))
