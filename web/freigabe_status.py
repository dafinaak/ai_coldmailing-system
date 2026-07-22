"""Dauerhafter Freigabestand je Empfänger und E-Mail-Schritt."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path


SCHRITTE = ("mail_1", "follow_up_1", "follow_up_2")
DATEINAME = "freigabe-status.json"

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class VeralteterStand(ValueError):
    """Die angezeigte Revision entspricht nicht mehr dem gespeicherten Stand."""


def _lock_fuer(lauf_dir: Path) -> threading.RLock:
    key = str(lauf_dir.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _leerer_schritt() -> dict:
    return {
        "approved": False,
        "approved_at": None,
        "approved_by": None,
        "content_hash": None,
        "override": None,
    }


def _versandfelder(texte: dict) -> dict:
    return {
        "email": texte.get("email", ""),
        "betreff": texte.get("betreff", ""),
        "mail_1": texte.get("mail_1", ""),
        "follow_up_1": texte.get("follow_up_1", ""),
        "follow_up_2": texte.get("follow_up_2", ""),
    }


def _inhalt(texte: dict, schritt: str) -> dict[str, str]:
    if schritt == "mail_1":
        return {"betreff": texte.get("betreff", ""), "text": texte.get("mail_1", "")}
    return {"text": texte.get(schritt, "")}


def inhalts_hash(texte: dict, schritt: str) -> str:
    roh = json.dumps(
        _inhalt(texte, schritt), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(roh.encode("utf-8")).hexdigest()


def _source_hash(texte: dict) -> str:
    roh = json.dumps(
        _versandfelder(texte), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def _revision(daten: dict, texte: list[dict]) -> str:
    roh = json.dumps(
        {"status": daten, "texte": texte},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def _atomar_speichern(pfad: Path, daten: dict) -> None:
    temp_pfad: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=pfad.parent,
            prefix=f".{pfad.name}-",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            json.dump(daten, tmp, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_pfad = Path(tmp.name)
        os.replace(temp_pfad, pfad)
        temp_pfad = None
    finally:
        if temp_pfad is not None:
            temp_pfad.unlink(missing_ok=True)


class FreigabeStatusStore:
    def __init__(self, lauf_dir: Path, *, jetzt=None, id_factory=None):
        self.lauf_dir = Path(lauf_dir)
        self.pfad = self.lauf_dir / DATEINAME
        self._jetzt = jetzt or datetime.now
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self.lock = _lock_fuer(self.lauf_dir)

    def _laden(self) -> dict:
        if not self.pfad.exists():
            return {"version": 1, "recipients": {}}
        try:
            daten = json.loads(self.pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError) as fehler:
            raise ValueError("Der gespeicherte Freigabestand ist beschädigt.") from fehler
        if daten.get("version") != 1 or not isinstance(daten.get("recipients"), dict):
            raise ValueError("Der gespeicherte Freigabestand ist falsch aufgebaut.")
        return daten

    @staticmethod
    def _mit_overrides(grundtext: dict, empfaenger: dict) -> dict:
        wirksam = _versandfelder(grundtext)
        for schritt in SCHRITTE:
            override = empfaenger["steps"][schritt].get("override")
            if not override:
                continue
            if schritt == "mail_1":
                wirksam["betreff"] = override["betreff"]
            wirksam[schritt] = override["text"]
        return wirksam

    def _abgleichen(
        self,
        daten: dict,
        texte: list[dict],
        *,
        alte_freigabe: dict | None,
        legacy_bootstrap: bool,
    ) -> tuple[list[tuple[dict, dict]], bool]:
        aktiv: list[tuple[dict, dict]] = []
        geaendert = False
        ids_nach_email = {
            e.get("email_key"): empfaenger_id
            for empfaenger_id, e in daten["recipients"].items()
            if e.get("email_key")
        }
        gesehen: set[str] = set()

        for grundtext in texte:
            email_key = str(grundtext.get("email") or "").strip().lower()
            if not email_key:
                raise ValueError("Ein Empfänger hat keine E-Mail-Adresse.")
            if email_key in gesehen:
                raise ValueError(f"Empfänger {email_key} kommt mehrfach vor.")
            gesehen.add(email_key)

            empfaenger_id = ids_nach_email.get(email_key)
            if empfaenger_id is None:
                empfaenger_id = self._id_factory()
                if empfaenger_id in daten["recipients"]:
                    raise ValueError("Eine Empfängerkennung kommt mehrfach vor.")
                daten["recipients"][empfaenger_id] = {
                    "email_key": email_key,
                    "source_hash": _source_hash(grundtext),
                    "qa_blocked": bool(grundtext.get("_qa_blocked")),
                    "qa_reason": grundtext.get("_qa_reason") or None,
                    "steps": {schritt: _leerer_schritt() for schritt in SCHRITTE},
                }
                ids_nach_email[email_key] = empfaenger_id
                geaendert = True

            empfaenger = daten["recipients"][empfaenger_id]
            for schritt in SCHRITTE:
                empfaenger["steps"].setdefault(schritt, _leerer_schritt())
            neuer_source_hash = _source_hash(grundtext)
            if empfaenger.get("source_hash") != neuer_source_hash:
                empfaenger["source_hash"] = neuer_source_hash
                if grundtext.get("_qa_blocked"):
                    empfaenger["qa_blocked"] = True
                    empfaenger["qa_reason"] = grundtext.get("_qa_reason") or None
                geaendert = True
            wirksam = self._mit_overrides(grundtext, empfaenger)

            for schritt in SCHRITTE:
                schrittstand = empfaenger["steps"][schritt]
                aktueller_hash = inhalts_hash(wirksam, schritt)
                if schrittstand.get("approved") and schrittstand.get("content_hash") != aktueller_hash:
                    schrittstand.update({
                        "approved": False,
                        "approved_at": None,
                        "approved_by": None,
                        "content_hash": None,
                    })
                    geaendert = True
                if legacy_bootstrap and alte_freigabe:
                    schrittstand.update({
                        "approved": True,
                        "approved_at": alte_freigabe.get("am"),
                        "approved_by": alte_freigabe.get("von"),
                        "content_hash": aktueller_hash,
                    })
                    geaendert = True
            aktiv.append((grundtext, {"id": empfaenger_id, **empfaenger}))
        return aktiv, geaendert

    def ansicht(self, texte: list[dict], alte_freigabe: dict | None = None) -> dict:
        with self.lock:
            legacy_bootstrap = not self.pfad.exists()
            daten = self._laden()
            aktiv, geaendert = self._abgleichen(
                daten,
                texte,
                alte_freigabe=alte_freigabe,
                legacy_bootstrap=legacy_bootstrap,
            )
            if geaendert or legacy_bootstrap:
                _atomar_speichern(self.pfad, daten)

            recipients = []
            for grundtext, empfaenger in aktiv:
                recipients.append({
                    "id": empfaenger["id"],
                    "email": grundtext["email"],
                    "qa_blocked": bool(empfaenger.get("qa_blocked")),
                    "qa_reason": empfaenger.get("qa_reason"),
                    "steps": {
                        schritt: {
                            "approved": bool(empfaenger["steps"][schritt].get("approved")),
                            "approved_at": empfaenger["steps"][schritt].get("approved_at"),
                            "approved_by": empfaenger["steps"][schritt].get("approved_by"),
                        }
                        for schritt in SCHRITTE
                    },
                })
            return {
                "revision": _revision(daten, texte),
                "recipients": recipients,
                "all_approved": bool(recipients) and all(
                    not e["qa_blocked"]
                    and all(s["approved"] for s in e["steps"].values())
                    for e in recipients
                ),
            }

    def _stand_fuer_mutation(
        self, texte: list[dict], revision: str
    ) -> tuple[dict, list[tuple[dict, dict]]]:
        daten = self._laden()
        aktiv, geaendert = self._abgleichen(
            daten,
            texte,
            alte_freigabe=None,
            legacy_bootstrap=False,
        )
        aktuelle_revision = _revision(daten, texte)
        if geaendert:
            _atomar_speichern(self.pfad, daten)
        if revision != aktuelle_revision:
            raise VeralteterStand("Die E-Mail-Runde wurde inzwischen geändert.")
        return daten, aktiv

    def bestaetigungen_setzen(
        self,
        texte: list[dict],
        recipient_ids: list[str],
        *,
        actor: str,
        approved: bool,
        revision: str,
        step: str | None,
    ) -> dict:
        if step is not None and step not in SCHRITTE:
            raise ValueError("Unbekannter E-Mail-Schritt.")
        ids = list(dict.fromkeys(recipient_ids))
        if not ids:
            raise ValueError("Bitte mindestens einen Empfänger auswählen.")

        with self.lock:
            daten, aktiv = self._stand_fuer_mutation(texte, revision)
            aktive_nach_id = {e["id"]: e for _, e in aktiv}
            if any(empfaenger_id not in aktive_nach_id for empfaenger_id in ids):
                raise ValueError("Ein ausgewählter Empfänger ist nicht mehr vorhanden.")
            if approved and any(aktive_nach_id[i].get("qa_blocked") for i in ids):
                raise ValueError("Für mindestens einen Empfänger ist noch Nacharbeit offen.")

            zeit = self._jetzt()
            approved_at = zeit.isoformat() if hasattr(zeit, "isoformat") else str(zeit)
            for empfaenger_id in ids:
                empfaenger = daten["recipients"][empfaenger_id]
                grundtext = next(t for t, e in aktiv if e["id"] == empfaenger_id)
                wirksam = self._mit_overrides(grundtext, empfaenger)
                for schritt in (SCHRITTE if step is None else (step,)):
                    schrittstand = empfaenger["steps"][schritt]
                    schrittstand.update({
                        "approved": approved,
                        "approved_at": approved_at if approved else None,
                        "approved_by": actor if approved else None,
                        "content_hash": inhalts_hash(wirksam, schritt) if approved else None,
                    })
            _atomar_speichern(self.pfad, daten)
            return self.ansicht(texte)

    def override_setzen(
        self,
        texte: list[dict],
        recipient_id: str,
        step: str,
        override: dict,
        revision: str,
        *,
        qa_cleared: bool = False,
        qa_reason: str | None = None,
    ) -> dict:
        if step not in SCHRITTE:
            raise ValueError("Unbekannter E-Mail-Schritt.")
        erwartete_felder = {"betreff", "text"} if step == "mail_1" else {"text"}
        if set(override) != erwartete_felder or any(
            not isinstance(override.get(feld), str) or not override[feld].strip()
            for feld in erwartete_felder
        ):
            raise ValueError("Der neu erzeugte E-Mail-Schritt ist unvollständig.")
        bereinigt = {feld: override[feld].strip() for feld in erwartete_felder}

        with self.lock:
            daten, aktiv = self._stand_fuer_mutation(texte, revision)
            aktive_ids = {e["id"] for _, e in aktiv}
            if recipient_id not in aktive_ids:
                raise ValueError("Der ausgewählte Empfänger ist nicht mehr vorhanden.")
            empfaenger = daten["recipients"][recipient_id]
            empfaenger["steps"][step].update({
                "override": bereinigt,
                "approved": False,
                "approved_at": None,
                "approved_by": None,
                "content_hash": None,
            })
            if qa_cleared:
                empfaenger["qa_blocked"] = False
                empfaenger["qa_reason"] = None
            elif qa_reason is not None:
                empfaenger["qa_blocked"] = True
                empfaenger["qa_reason"] = qa_reason
            _atomar_speichern(self.pfad, daten)
            return self.ansicht(texte)

    def materialisieren(self, texte: list[dict]) -> list[dict]:
        with self.lock:
            daten = self._laden()
            aktiv, geaendert = self._abgleichen(
                daten,
                texte,
                alte_freigabe=None,
                legacy_bootstrap=False,
            )
            if geaendert:
                _atomar_speichern(self.pfad, daten)
            return [self._mit_overrides(grundtext, daten["recipients"][e["id"]])
                    for grundtext, e in aktiv]

    def alles_bestaetigt(self, texte: list[dict]) -> bool:
        return self.ansicht(texte)["all_approved"]
