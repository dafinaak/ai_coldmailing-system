"""Ein fertiger Lauf muss auch als fertig gelten.

Gefunden im echten Probelauf am 12.08.2026: Der Lauf war durch, die
Freigabe-Tabelle gefuellt - aber die Uebersicht blieb leer und der
Zustand stand ewig auf "laeuft". Grund: der Web-Server startet die
Laeufe, holt die beendeten Kinder aber nie ab. Sie bleiben als Zombie
in der Prozessliste stehen, und os.kill(pid, 0) meldet sie als
lebendig. Betrifft nicht nur den Assistenten, sondern jeden Lauf, der
ueber die Oberflaeche gestartet wurde.
"""
import os
import subprocess
import sys
import time

from web.laufmanager import _ist_zombie, _pid_lebt


def test_laufender_prozess_gilt_als_lebendig():
    prozess = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert _pid_lebt(prozess.pid) is True
    finally:
        prozess.kill()
        prozess.wait()


def test_beendetes_kind_gilt_als_tot_und_nicht_als_zombie():
    # Genau der Fall aus dem Probelauf: Kind fertig, Elternteil holt es
    # nie ab. Ohne die Reparatur meldet _pid_lebt hier True.
    prozess = subprocess.Popen([sys.executable, "-c", "pass"])
    for _ in range(50):                       # auf das Ende warten, ohne
        if _ist_zombie(prozess.pid):          # es abzuholen
            break
        time.sleep(0.1)

    assert _pid_lebt(prozess.pid) is False

    try:
        prozess.wait(timeout=5)
    except Exception:
        pass


def test_niemals_vergebene_pid_gilt_als_tot():
    assert _pid_lebt(999999) is False


def test_eigener_prozess_gilt_als_lebendig():
    assert _pid_lebt(os.getpid()) is True
