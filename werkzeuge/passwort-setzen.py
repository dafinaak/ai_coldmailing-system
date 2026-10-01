"""Set the password of an interface user in users.yaml.

The file keeps bcrypt hashes only, so a forgotten password cannot be read
back - it can only be replaced. This tool writes a new hash with the same
CryptContext that web/auth.py uses to check it, so both always agree.

    python werkzeuge/passwort-setzen.py keti
    # asks for the password twice, without echoing it

The old file is kept as users.yaml.bak-<date> before anything is written:
a wrong edit here locks everyone out of the interface.
"""
from __future__ import annotations

import getpass
import shutil
import sys
from datetime import date
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

import yaml  # noqa: E402

from web.auth import _pwd_context  # noqa: E402

DATEI = PROJEKT / "users.yaml"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    name = sys.argv[1]

    if not DATEI.exists():
        print(f"Mungon {DATEI}")
        return 1
    nutzer = yaml.safe_load(DATEI.read_text(encoding="utf-8")) or []
    treffer = [e for e in nutzer if e.get("name") == name]
    if not treffer:
        vorhanden = ", ".join(e.get("name", "?") for e in nutzer) or "asnje"
        print(f"Perdoruesi {name!r} nuk ekziston. Te skedari jane: {vorhanden}")
        return 1

    if sys.stdin.isatty():
        passwort = getpass.getpass(f"Fjalekalimi i ri per {name}: ")
        if passwort != getpass.getpass("Edhe nje here: "):
            print("Nuk perputhen.")
            return 1
    else:
        # Pa terminal (p.sh. i nisur nga nje skript): lexohet nga stdin.
        passwort = sys.stdin.readline().rstrip("\n")
    if not passwort:
        print("Fjalekalim bosh - nuk vendoset.")
        return 1
    # Paralajmerim, jo ndalese: vendos njeriu, jo vegla.
    if len(passwort) < 10:
        print(f"KUJDES: {len(passwort)} shkronja - i shkurter. Interface-i "
              f"mund te nise fushata, prandaj ia vlen nje me i gjate kur "
              f"te dale jashte makines.")

    kopje = DATEI.with_name(f"users.yaml.bak-{date.today().isoformat()}")
    if not kopje.exists():
        shutil.copy2(DATEI, kopje)

    treffer[0]["passwort_hash"] = _pwd_context.hash(passwort)
    DATEI.write_text(yaml.safe_dump(nutzer, allow_unicode=True,
                                    sort_keys=False), encoding="utf-8")

    # Prova: lexohet prapa dhe kontrollohet, qe te mos mbetet nje skedar
    # qe duket i rregullt po nuk hyn dot askush me te.
    kontrolle = yaml.safe_load(DATEI.read_text(encoding="utf-8"))
    eintrag = next(e for e in kontrolle if e.get("name") == name)
    if not _pwd_context.verify(passwort, eintrag["passwort_hash"]):
        shutil.copy2(kopje, DATEI)
        print("Prova deshtoi - skedari u kthye si ishte.")
        return 1

    print(f"U vendos fjalekalimi i ri per {name}. Kopja e vjeter: {kopje.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
