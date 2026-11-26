"""Jede Anfrage eine Einheit (BF-49, core/database.py): eigene Verbindung, gebucht am Ende, zurückgerollt bei einer Ausnahme
oder einer Antwort ab 400. So bleibt von einer gescheiterten Anfrage nichts halb Geändertes übrig, das ein fremder Aufruf
mitbucht.

Eine reine ASGI-Schicht, weil die Einheit der Aufgabe gehört, in der die Anfrage läuft: eine BaseHTTPMiddleware darunter
würde die App in einer anderen Aufgabe ausführen, die dann nicht mehr in die Einheit schreibt (weitere Schichten deshalb
später hinzufügen, dann liegen sie außen). Den Körper einer gestreamten Antwort erzeugt Starlette in einer eigenen Aufgabe;
dort gilt jede Anweisung für sich, mehrere zusammen in `db.einheit()`."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.core.database import db


class Einheiten:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        async with db.einheit() as einheit:
            async def senden(nachricht: Message) -> None:
                if nachricht["type"] == "http.response.start" and nachricht["status"] >= 400:
                    einheit.verwerfen = True
                await send(nachricht)

            await self.app(scope, receive, senden)
