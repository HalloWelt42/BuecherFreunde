"""Für alle Tests: keine Quelle im Netz fragen. Wer Antworten braucht, nimmt `netz` (Mitschnitte)."""

import pytest

from backend.app.quellen import abruf as quellen_abruf
from backend.app.quellen.abruf import Abruf
from tests.quellen_netz import Netz, abruf_mit


async def _gesperrt(anfrage):
    raise AssertionError(f"Tests fragen nie das Netz: {anfrage.adresse}")


@pytest.fixture(autouse=True)
def kein_netz():
    """Frischer Abruf je Test, der nichts hinauslässt."""
    vorher = quellen_abruf.einsetzen(Abruf(_gesperrt))
    yield
    quellen_abruf.einsetzen(vorher)


@pytest.fixture
def netz(kein_netz) -> Netz:
    """Ein Netz aus Mitschnitten statt der echten Quellen, ohne Wartezeiten."""
    n = Netz()
    quellen_abruf.einsetzen(abruf_mit(n))
    return n
