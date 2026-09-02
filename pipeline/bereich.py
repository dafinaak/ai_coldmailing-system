"""Entscheider-Bereich: in welchem Bereich entscheidet diese Person?

Olivers Feld heisst "A) Entscheider-Bereich (fuer welches Produkt)". Es
besteht aus zwei Teilen, und nur einer laesst sich aus unseren Daten
beantworten:

  1. Der BEREICH der Person - Geschaeftsfuehrung, IT, Vertrieb, Einkauf,
     Finanzen, Personal. Der steht in ihrer Rolle, also wird er hier
     abgeleitet.

  2. Fuer welches PRODUKT sie zustaendig ist. Das haengt an unserem
     Angebot, nicht an der Firma des Empfaengers. Solange es nur ein
     Angebot gibt, gibt es dazu nichts zu unterscheiden - kommen mehrere
     dazu, braucht es eine Produktliste und eine Zuordnungsregel.

Bei unseren Daten faellt fast alles auf "Geschaeftsfuehrung": wir lesen
das Impressum, und das nennt die gesetzlichen Vertreter. Bei einer kleinen
IT-Firma ist das auch die Wahrheit - dort entscheidet der Inhaber alles.
"""
from __future__ import annotations

# Reihenfolge zaehlt: "Leiter IT-Vertrieb" ist Vertrieb, nicht IT, und
# "Geschaeftsfuehrer IT" bleibt Geschaeftsfuehrung. Deshalb wird die
# Leitungsebene zuerst geprueft.
_REGELN = (
    ("Aufsichtsrat", ("aufsichtsrat", "beirat")),
    ("Geschäftsführung", ("geschaeftsfuehr", "geschaeftsleit", "inhaber",
                          "inh.", "eigentuem", "vorstand", "ceo",
                          "managing director", "gruender", "founder",
                          "gesellschafter", "komplementaer", "gf",
                          "vertreten durch", "vertretungsberechtigt")),
    ("Vertrieb", ("vertrieb", "sales", "account", "kundenbetreu")),
    ("Marketing", ("marketing", "kommunikation", "werbung")),
    ("Einkauf", ("einkauf", "beschaffung", "procurement")),
    ("Finanzen", ("finanz", "buchhalt", "controlling", "cfo", "kaufmaenn")),
    ("Personal", ("personal", "human resources", "hr-", "recruit")),
    ("IT", ("it-", "edv", "informat", "technik", "cto", "entwicklung",
            "systemadmin", "netzwerk")),
)


def _norm(text: object) -> str:
    wert = str(text or "").casefold()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        wert = wert.replace(a, b)
    return wert


def aus_rolle(rolle: object) -> str:
    """Bereich aus der Funktionsbezeichnung. Unbekannt -> leer.

    Es wird nichts geraten: wer keine erkennbare Funktion nennt, bekommt
    auch keinen Bereich zugewiesen.
    """
    text = _norm(rolle)
    if not text.strip():
        return ""
    for name, begriffe in _REGELN:
        if any(b in text for b in begriffe):
            return name
    return ""
