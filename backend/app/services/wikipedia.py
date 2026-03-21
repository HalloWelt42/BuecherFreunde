"""Wikipedia/Wikidata Metadaten-Service für Buchanreicherung.

Nutzt die Wikidata-API um Buchdaten anhand der ISBN zu finden.
Wikidata enthält strukturierte Daten (Autor, Verlag, Sprache, Genre etc.)
und verlinkt auf Wikipedia-Artikel für Beschreibungen.
"""

import io
import logging

import requests as req

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.wikipedia")

_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
_WIKIPEDIA_API = "https://de.wikipedia.org/w/api.php"
_WIKIPEDIA_EN_API = "https://en.wikipedia.org/w/api.php"

# Retro-Browser User-Agent
_USER_AGENT = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)"


async def _fetch_json(url: str, params: dict, timeout: float = 15.0) -> dict | None:
    """Holt JSON von einer URL. Nutzt requests in Thread für besseres Rate-Limit-Handling."""
    import asyncio
    import time

    def _do_request():
        time.sleep(0.2)
        resp = req.get(url, params=params, headers={"User-Agent": _USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    try:
        return await asyncio.to_thread(_do_request)
    except Exception as e:
        logger.warning("Wikipedia/Wikidata Anfrage fehlgeschlagen: %s - %s", url, e)
        return None


async def _find_wikidata_item(isbn: str) -> str | None:
    """Findet die Wikidata-Entity-ID für eine ISBN."""
    clean_isbn = isbn.replace("-", "").replace(" ", "")

    # SPARQL-Abfrage: Suche nach ISBN-13 oder ISBN-10
    sparql = f"""
    SELECT ?item WHERE {{
      {{ ?item wdt:P212 "{clean_isbn}" . }}
      UNION
      {{ ?item wdt:P957 "{clean_isbn}" . }}
    }} LIMIT 1
    """

    try:
        import asyncio

        def _do_sparql():
            resp = req.get(
                _WIKIDATA_SPARQL,
                params={"query": sparql, "format": "json"},
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/sparql-results+json",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

        data = await asyncio.to_thread(_do_sparql)
        bindings = data.get("results", {}).get("bindings", [])
        if bindings:
            uri = bindings[0]["item"]["value"]
            return uri.split("/")[-1]
    except Exception as e:
        logger.warning("Wikidata SPARQL Fehler: %s", e)

    return None


def _get_claim_values(entity: dict, prop: str) -> list[str]:
    """Extrahiert Werte aus Wikidata-Claims."""
    claims = entity.get("claims", {}).get(prop, [])
    values = []
    for claim in claims:
        mainsnak = claim.get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        dtype = datavalue.get("type", "")

        if dtype == "string":
            values.append(datavalue["value"])
        elif dtype == "wikibase-entityid":
            values.append(datavalue["value"].get("id", ""))
        elif dtype == "quantity":
            values.append(datavalue["value"].get("amount", "").lstrip("+"))
        elif dtype == "time":
            # +2005-00-00T00:00:00Z -> 2005
            time_str = datavalue["value"].get("time", "")
            if time_str:
                year = time_str.lstrip("+").split("-")[0]
                values.append(year)
    return values


async def _resolve_entities(entity_ids: list[str]) -> dict[str, str]:
    """Löst Wikidata-Entity-IDs in Labels auf."""
    if not entity_ids:
        return {}

    ids = "|".join(entity_ids[:20])
    data = await _fetch_json(_WIKIDATA_API, {
        "action": "wbgetentities",
        "ids": ids,
        "props": "labels",
        "languages": "de|en",
        "format": "json",
    })

    if not data:
        return {}

    result = {}
    for eid, entity in data.get("entities", {}).items():
        labels = entity.get("labels", {})
        label = labels.get("de", labels.get("en", {})).get("value", eid)
        result[eid] = label

    return result


def _get_wiki_client(lang: str = "de"):
    """Erstellt einen Wikipedia-API-Client für die gegebene Sprache."""
    import wikipediaapi
    return wikipediaapi.Wikipedia(
        user_agent=_USER_AGENT,
        language=lang,
        extract_format=wikipediaapi.ExtractFormat.WIKI,
    )


_SKIP_SECTIONS = {
    "literatur", "weblinks", "einzelnachweise", "quellen", "anmerkungen",
    "siehe auch", "werke", "bibliografie", "bibliographie", "diskografie",
    "filmografie", "filmographie", "references", "external links",
    "bibliography", "works", "further reading", "notes", "selected works",
    "publications", "discography", "filmography",
}


async def _get_wikipedia_extract(title: str, lang: str = "de") -> str:
    """Holt den Biografietext eines Wikipedia-Artikels.

    Sammelt Einleitung + inhaltliche Abschnitte (Werdegang, Leben etc.),
    ueberspringt aber Literatur, Weblinks, Werke-Listen usw.
    Kein Textlimit -- der volle Inhalt wird gespeichert.
    """
    import asyncio

    def _fetch():
        wiki = _get_wiki_client(lang)
        page = wiki.page(title)
        if not page.exists():
            return ""

        parts = []
        # Einleitung
        if page.summary:
            parts.append(page.summary)

        # Inhaltliche Abschnitte sammeln
        for section in page.sections:
            sec_title = section.title.strip().lower()
            if sec_title in _SKIP_SECTIONS:
                continue
            if section.text and len(section.text.strip()) > 20:
                parts.append(f"## {section.title}\n\n{section.text.strip()}")
            # Unterabschnitte
            for sub in section.sections:
                sub_title = sub.title.strip().lower()
                if sub_title in _SKIP_SECTIONS:
                    continue
                if sub.text and len(sub.text.strip()) > 20:
                    parts.append(f"### {sub.title}\n\n{sub.text.strip()}")

        return "\n\n".join(parts)

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.warning("Wikipedia-Extrakt fehlgeschlagen für '%s': %s", title, e)
        return ""


async def _search_wikipedia_pages(query: str, lang: str = "de", limit: int = 5) -> list[dict]:
    """Sucht Wikipedia-Seiten und gibt Titel + Wikidata-ID zurück."""
    import asyncio

    def _search():
        wiki = _get_wiki_client(lang)
        # Wikipedia-API search liefert Seitenobjekte
        results = []
        # Nutze die MediaWiki-API über requests direkt für Suche
        import requests
        api_url = f"https://{lang}.wikipedia.org/w/api.php"
        resp = requests.get(api_url, params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": 0,
            "srlimit": limit,
            "format": "json",
        }, headers={"User-Agent": _USER_AGENT}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("query", {}).get("search", []):
            results.append({"title": item["title"]})

        if not results:
            return []

        # Wikidata-IDs über pageprops holen
        titles = "|".join(r["title"] for r in results[:5])
        resp2 = requests.get(api_url, params={
            "action": "query",
            "titles": titles,
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "format": "json",
        }, headers={"User-Agent": _USER_AGENT}, timeout=10)
        resp2.raise_for_status()
        data2 = resp2.json()
        enriched = []
        for page in data2.get("query", {}).get("pages", {}).values():
            wikidata_id = page.get("pageprops", {}).get("wikibase_item", "")
            if wikidata_id:
                enriched.append({
                    "id": wikidata_id,
                    "label": page.get("title", ""),
                    "description": f"via Wikipedia ({lang})",
                })
        return enriched

    try:
        return await asyncio.to_thread(_search)
    except Exception as e:
        logger.warning("Wikipedia-Suche fehlgeschlagen für '%s': %s", query, e)
        return []


async def lookup_isbn(isbn: str) -> dict | None:
    """Sucht Buch-Metadaten via Wikidata anhand der ISBN.

    Gibt ein dict mit gemappten und Rohdaten zurück.
    """
    if not settings.wikipedia_enabled or not isbn:
        return None

    # 1. Wikidata-Item finden
    item_id = await _find_wikidata_item(isbn)
    if not item_id:
        logger.info("ISBN %s nicht bei Wikidata gefunden", isbn)
        return None

    # 2. Entity-Daten laden
    data = await _fetch_json(_WIKIDATA_API, {
        "action": "wbgetentities",
        "ids": item_id,
        "props": "labels|descriptions|claims|sitelinks",
        "languages": "de|en",
        "format": "json",
    })

    if not data:
        return None

    entity = data.get("entities", {}).get(item_id)
    if not entity:
        return None

    labels = entity.get("labels", {})
    descriptions = entity.get("descriptions", {})

    titel = labels.get("de", labels.get("en", {})).get("value", "")
    kurzbeschreibung = descriptions.get("de", descriptions.get("en", {})).get("value", "")

    # Properties auslesen
    # P50=Autor, P123=Verlag, P577=Erscheinungsdatum, P1104=Seitenanzahl
    # P407=Sprache, P136=Genre, P921=Hauptthema, P31=ist-ein
    # P212=ISBN-13, P957=ISBN-10, P18=Bild, P856=Website
    autoren_ids = _get_claim_values(entity, "P50")
    verlag_ids = _get_claim_values(entity, "P123")
    sprache_ids = _get_claim_values(entity, "P407")
    genre_ids = _get_claim_values(entity, "P136")
    thema_ids = _get_claim_values(entity, "P921")
    typ_ids = _get_claim_values(entity, "P31")

    jahr_werte = _get_claim_values(entity, "P577")
    seiten_werte = _get_claim_values(entity, "P1104")
    isbn13_werte = _get_claim_values(entity, "P212")
    isbn10_werte = _get_claim_values(entity, "P957")

    # Entity-IDs auflösen
    alle_ids = list(set(
        autoren_ids + verlag_ids + sprache_ids + genre_ids + thema_ids + typ_ids
    ))
    entity_labels = await _resolve_entities([i for i in alle_ids if i.startswith("Q")])

    autoren = [entity_labels.get(a, a) for a in autoren_ids]
    verlage = [entity_labels.get(v, v) for v in verlag_ids]
    sprachen = [entity_labels.get(s, s) for s in sprache_ids]
    genres = [entity_labels.get(g, g) for g in genre_ids]
    themen = [entity_labels.get(t, t) for t in thema_ids]
    typen = [entity_labels.get(t, t) for t in typ_ids]

    # Jahr extrahieren
    jahr = None
    for j in jahr_werte:
        try:
            jahr = int(j)
            break
        except (ValueError, TypeError):
            pass

    # Seitenanzahl
    seiten = None
    for s in seiten_werte:
        try:
            seiten = int(float(s))
            break
        except (ValueError, TypeError):
            pass

    # Wikipedia-Beschreibung holen
    beschreibung = ""
    sitelinks = entity.get("sitelinks", {})
    wiki_title = None
    if "dewiki" in sitelinks:
        wiki_title = sitelinks["dewiki"].get("title", "")
    elif "enwiki" in sitelinks:
        wiki_title = sitelinks["enwiki"].get("title", "")

    if wiki_title:
        beschreibung = await _get_wikipedia_extract(wiki_title)

    # Kategorien aus Genre + Themen zusammensetzen
    kategorien = []
    for g in genres:
        if g and g not in kategorien:
            kategorien.append(g)
    for t in themen:
        if t and t not in kategorien:
            kategorien.append(t)

    # Gemappte Felder
    result = {
        "titel": titel,
        "autor": ", ".join(autoren) if autoren else "",
        "isbn": isbn13_werte[0] if isbn13_werte else isbn.replace("-", "").replace(" ", ""),
        "verlag": verlage[0] if verlage else "",
        "jahr": jahr,
        "seiten": seiten or 0,
        "sprache": sprachen[0] if sprachen else "",
        "beschreibung": beschreibung or kurzbeschreibung,
        "kategorien": kategorien,
        "cover_url": "",
        "quelle": "wikipedia",
    }

    # Rohdaten: alle nicht gemappten Felder
    raw = {
        "wikidata_id": item_id,
        "kurzbeschreibung": kurzbeschreibung,
        "isbn13": isbn13_werte,
        "isbn10": isbn10_werte,
        "autoren": autoren,
        "verlage": verlage,
        "sprachen": sprachen,
        "genres": genres,
        "themen": themen,
        "typen": typen,
        "wikipedia_titel": wiki_title or "",
        "sitelinks": {k: v.get("title", "") for k, v in sitelinks.items()},
    }
    result["raw"] = raw

    return result


async def search_books(query: str, limit: int = 5) -> list[dict]:
    """Sucht Bücher bei Wikidata nach Titel."""
    if not settings.wikipedia_enabled or not query or len(query.strip()) < 3:
        return []

    data = await _fetch_json(_WIKIDATA_API, {
        "action": "wbsearchentities",
        "search": query,
        "language": "de",
        "type": "item",
        "limit": limit,
        "format": "json",
    })

    if not data:
        return []

    results = []
    for item in data.get("search", []):
        results.append({
            "titel": item.get("label", ""),
            "beschreibung": item.get("description", ""),
            "wikidata_id": item.get("id", ""),
        })

    return results


def _normalize_author_name(name: str) -> str:
    """Normalisiert Autorennamen für die Suche.

    Kehrt Komma-Format um: 'Roberts, Nora' -> 'Nora Roberts'.
    Entfernt Suffixe wie 'Hrsg' und bereinigt Semikolons.
    """
    import re
    name = name.strip().rstrip(";").strip()
    # Hrsg., (Hrsg.), Hrsg entfernen
    name = re.sub(r'\s*\(?Hrsg\.?\)?\s*$', '', name, flags=re.IGNORECASE)
    name = name.strip()
    # Komma-Format umkehren: "Nachname, Vorname" -> "Vorname Nachname"
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2 and parts[1]:
            name = f"{parts[1]} {parts[0]}"
    return name.strip()


# Schriftsteller-Berufe (Q-Werte) für die Filterung
_WRITER_OCCUPATIONS = {
    "Q36180",    # Schriftsteller (writer)
    "Q482980",   # Autor (author)
    "Q6625963",  # Romancier (novelist)
    "Q49757",    # Dichter (poet)
    "Q214917",   # Dramatiker (playwright)
    "Q11774202", # Essayist
    "Q4853732",  # Kinder- und Jugendbuchautor
    "Q18844224", # Science-Fiction-Autor
    "Q1930187",  # Journalist
    "Q28389",    # Drehbuchautor
    "Q333634",   # Übersetzer
    "Q201788",   # Historiker
    "Q1622272",  # Universitätsprofessor
    "Q15980158", # Sachbuchautor
    "Q4263842",  # Literaturkritiker
}


_SURNAME_PREFIXES = {
    "le", "la", "de", "del", "di", "du", "von", "van", "der", "den",
    "el", "al", "bin", "ibn", "mc", "mac", "st", "saint", "o'",
}


def _generate_name_variants(name: str) -> list[str]:
    """Erzeugt Suchvarianten eines Autorennamens.

    z.B. "J. K. Rowling" -> ["J. K. Rowling", "JK Rowling"]
    "John le Carré" -> ["John le Carré"]
    """
    variants = [name]
    parts = name.split()

    if len(parts) >= 2:
        # Punkte aus Initialen entfernen: "J. K. Rowling" -> "JK Rowling"
        kompakt = " ".join(p.replace(".", "") for p in parts)
        if kompakt != name:
            variants.append(kompakt)

        # Ohne Initialen: "J.K. Rowling" -> "Rowling" (nur wenn Nachname lang genug)
        ohne_initialen = [p for p in parts if len(p.rstrip(".")) > 1]
        if len(ohne_initialen) >= 2 and " ".join(ohne_initialen) != name:
            variants.append(" ".join(ohne_initialen))

        # Pseudonyme: "J.D. Robb" ist auch "Nora Roberts" - das geht nur über Wikidata-Aliase
        # -> wbsearchentities sucht bereits in Aliase

    # Duplikate entfernen, Reihenfolge beibehalten
    seen = set()
    result = []
    for v in variants:
        if v.lower() not in seen and len(v) >= 2:
            seen.add(v.lower())
            result.append(v)
    return result


async def _search_wikidata_candidates(variants: list[str]) -> list[dict]:
    """Sucht Wikidata-Kandidaten mit allen Namensvarianten in DE und EN."""
    candidates = []
    seen_ids = set()

    for variant in variants:
        for lang in ("de", "en"):
            data = await _fetch_json(_WIKIDATA_API, {
                "action": "wbsearchentities",
                "search": variant,
                "language": lang,
                "uselang": lang,
                "type": "item",
                "limit": 8,
                "format": "json",
            })
            if data:
                for item in data.get("search", []):
                    qid = item.get("id", "")
                    if qid and qid not in seen_ids:
                        seen_ids.add(qid)
                        candidates.append({
                            "id": qid,
                            "label": item.get("label", ""),
                            "description": item.get("description", ""),
                        })
            # Genug Kandidaten? Nicht weitersuchen
            if len(candidates) >= 15:
                return candidates

    return candidates


async def _search_wikipedia_for_author(variants: list[str]) -> list[dict]:
    """Sucht in Wikipedia nach einem Artikel und extrahiert die Wikidata-ID.

    Fallback wenn wbsearchentities nichts findet. Nutzt requests (synchron in Thread)
    statt httpx, um das Rate-Limiting von Wikimedia zu umgehen.
    """
    candidates = []
    seen_ids = set()

    for variant in variants[:2]:
        for lang in ("de", "en"):
            results = await _search_wikipedia_pages(variant, lang=lang, limit=3)
            for r in results:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    candidates.append(r)

    return candidates


async def lookup_author(
    name: str,
    book_titles: list[str] | None = None,
    book_isbns: list[str] | None = None,
) -> dict | None:
    """Sucht Autoren-Daten via Wikidata (2-Stufen: wbsearchentities + wbgetentities).

    1. Name normalisieren (Komma-Format umkehren)
    2. wbsearchentities für Fuzzy-Suche (findet auch Aliase/Pseudonyme)
    3. wbgetentities Batch-Call: P31=Q5 (Mensch) prüfen, Beruf prüfen
    4. Details laden (Lebensdaten, Foto, Wikipedia-Biografie)

    book_titles: Bekannte Buchtitel des Autors zur Validierung.
    book_isbns: ISBNs der Bücher des Autors - höchstes Konfidenz-Signal.
    """
    if not settings.wikipedia_enabled or not name:
        return None

    search_name = _normalize_author_name(name)
    if len(search_name) < 2:
        return None

    logger.info("Autorensuche: '%s' (normalisiert: '%s')", name, search_name)

    # Namensvarianten generieren
    search_variants = _generate_name_variants(search_name)
    logger.info("Suchvarianten: %s", search_variants)

    # Stufe 1: Wikidata-Suche (DE + EN, alle Varianten)
    candidates = await _search_wikidata_candidates(search_variants)

    # Stufe 1b: Fallback - Wikipedia-Artikelsuche -> Wikidata-ID extrahieren
    if len(candidates) < 3:
        wiki_candidates = await _search_wikipedia_for_author(search_variants)
        for wc in wiki_candidates:
            if wc["id"] not in [c["id"] for c in candidates]:
                candidates.append(wc)

    if not candidates:
        logger.info("Keine Wikidata-Kandidaten für '%s'", search_name)
        return None

    # Stufe 2: Batch-Abruf der Kandidaten (max 50 pro Request)
    candidate_ids = [c["id"] for c in candidates[:10]]
    entity_data = await _fetch_json(_WIKIDATA_API, {
        "action": "wbgetentities",
        "ids": "|".join(candidate_ids),
        "props": "claims|labels|descriptions|sitelinks",
        "languages": "de|en",
        "format": "json",
    })

    # Buchtitel und ISBNs normalisieren für Vergleich
    known_titles_lower = {t.lower().strip() for t in (book_titles or []) if t}
    known_isbns = {isbn.replace("-", "").replace(" ", "") for isbn in (book_isbns or []) if isbn and len(isbn) >= 10}

    if not entity_data:
        return None

    # Kandidaten filtern: P31=Q5 (Mensch), bevorzugt mit Schriftsteller-Beruf
    best_match = None
    best_score = -1

    for qid in candidate_ids:
        entity = entity_data.get("entities", {}).get(qid)
        if not entity:
            continue

        claims = entity.get("claims", {})

        # P31 prüfen: muss Mensch (Q5) sein
        p31 = claims.get("P31", [])
        is_human = any(
            c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5"
            for c in p31
        )
        if not is_human:
            continue

        # Bewertung berechnen
        score = 0

        # P106 (Beruf) prüfen
        p106 = claims.get("P106", [])
        occupation_ids = {
            c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
            for c in p106
        }
        if occupation_ids & _WRITER_OCCUPATIONS:
            score += 10  # Schriftsteller = starkes Signal

        # Sitelinks zählen (bekanntere Personen haben mehr)
        sitelinks = entity.get("sitelinks", {})
        score += min(len(sitelinks), 10)

        # Deutsches Wikipedia vorhanden = Bonus
        if "dewiki" in sitelinks:
            score += 5

        # Exakter Name-Match = Bonus
        labels = entity.get("labels", {})
        entity_name = labels.get("de", labels.get("en", {})).get("value", "")
        if entity_name.lower() == search_name.lower():
            score += 8

        # P800 (notable works) gegen unsere Buchtitel abgleichen
        p800 = claims.get("P800", [])
        work_ids = [
            c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
            for c in p800 if c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
        ]
        if work_ids and (known_titles_lower or known_isbns):
            work_labels = await _resolve_entities(work_ids[:20])
            work_titles_lower = {v.lower() for v in work_labels.values()}
            # Fuzzy: prüfe ob ein Buchtitel in einem Werktitel vorkommt oder umgekehrt
            if known_titles_lower:
                werk_treffer = 0
                for kt in known_titles_lower:
                    for wt in work_titles_lower:
                        if kt in wt or wt in kt:
                            werk_treffer += 1
                            break
                if werk_treffer > 0:
                    score += 15  # Starkes Signal: Werke stimmen überein
                    logger.info("Werk-Abgleich: %d Treffer für '%s'", werk_treffer, search_name)

            # ISBN-Abgleich: Werke laden und deren ISBNs prüfen
            if known_isbns and work_ids:
                isbn_treffer = await _check_work_isbns(work_ids[:10], known_isbns)
                if isbn_treffer > 0:
                    score += 30  # Nahezu todsicher: ISBN stimmt überein
                    logger.info("ISBN-Abgleich: %d Treffer für '%s'", isbn_treffer, search_name)

        if score > best_score:
            best_score = score
            best_match = (qid, entity)

    if not best_match:
        logger.info("Kein passender Mensch für '%s' gefunden", search_name)
        return None

    qid, entity = best_match
    claims = entity.get("claims", {})
    labels = entity.get("labels", {})
    descriptions = entity.get("descriptions", {})

    # Details extrahieren
    display_name = labels.get("de", labels.get("en", {})).get("value", name)
    beschreibung = descriptions.get("de", descriptions.get("en", {})).get("value", "")

    # Lebensdaten
    birth_year = _extract_year(claims, "P569")
    death_year = _extract_year(claims, "P570")

    # Foto-URL aus P18 (Commons-Dateiname)
    photo_url = ""
    photo_values = _get_claim_values(entity, "P18")
    if photo_values:
        filename = photo_values[0].replace(" ", "_")
        photo_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width=400"

    # Nationalität
    nationality = ""
    nat_ids = _get_claim_values(entity, "P27")
    if nat_ids:
        nat_labels = await _resolve_entities([n for n in nat_ids if n.startswith("Q")][:1])
        if nat_labels:
            nationality = list(nat_labels.values())[0]

    # Wikipedia-Biografie
    biography = ""
    wikipedia_url = ""
    sitelinks = entity.get("sitelinks", {})
    wiki_title = None
    if "dewiki" in sitelinks:
        wiki_title = sitelinks["dewiki"].get("title", "")
        wikipedia_url = f"https://de.wikipedia.org/wiki/{wiki_title.replace(' ', '_')}"
    elif "enwiki" in sitelinks:
        wiki_title = sitelinks["enwiki"].get("title", "")
        wikipedia_url = f"https://en.wikipedia.org/wiki/{wiki_title.replace(' ', '_')}"

    if wiki_title:
        wiki_lang = "de" if "dewiki" in sitelinks else "en"
        biography = await _get_wikipedia_extract(wiki_title, lang=wiki_lang)

    # Buch-Validierung: Prüfe ob Biografie/Beschreibung Bezug zu bekannten Büchern hat
    konfidenz = "hoch" if best_score >= 15 else "mittel" if best_score >= 8 else "niedrig"

    # ISBN in Biografie = nahezu sicher
    if known_isbns and biography:
        bio_clean = biography.replace("-", "").replace(" ", "")
        isbn_in_bio = sum(1 for isbn in known_isbns if isbn in bio_clean)
        if isbn_in_bio > 0:
            konfidenz = "hoch"
            logger.info("ISBN-Validierung: %d ISBNs in Biografie gefunden", isbn_in_bio)

    if book_titles and biography:
        bio_lower = biography.lower() + " " + beschreibung.lower()
        treffer = sum(1 for t in book_titles if t.lower() in bio_lower)
        if treffer > 0:
            konfidenz = "hoch"
            logger.info("Buch-Validierung: %d von %d Titeln in Biografie gefunden", treffer, len(book_titles))
        elif best_score < 15:
            konfidenz = "niedrig"
            logger.info("Buch-Validierung: Keine Buchtitel in Biografie gefunden, Konfidenz reduziert")

    # Score >= 30 (ISBN-Match) = immer hoch
    if best_score >= 30:
        konfidenz = "hoch"

    # Literaturliste aus P800 (notable works) laden
    werke = []
    p800_claims = claims.get("P800", [])
    werk_ids = [
        c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id", "")
        for c in p800_claims if c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
    ]
    if werk_ids:
        werk_labels = await _resolve_entities(werk_ids[:30])
        werke = [{"wikidata_id": wid, "titel": label} for wid, label in werk_labels.items()]

    logger.info("Autor gefunden: '%s' -> %s (%s, Score: %d, Konfidenz: %s, Werke: %d)", search_name, display_name, qid, best_score, konfidenz, len(werke))

    return {
        "name": display_name,
        "wikidata_id": qid,
        "biography": biography,
        "birth_year": birth_year,
        "death_year": death_year,
        "photo_url": photo_url,
        "wikipedia_url": wikipedia_url,
        "nationality": nationality,
        "beschreibung": beschreibung,
        "konfidenz": konfidenz,
        "score": best_score,
        "werke": werke,
    }


async def _check_work_isbns(work_ids: list[str], known_isbns: set[str]) -> int:
    """Prüft ob Wikidata-Werke (P800) ISBNs haben die mit unseren übereinstimmen.

    Lädt die Werke und prüft P212 (ISBN-13) und P957 (ISBN-10).
    """
    if not work_ids or not known_isbns:
        return 0

    data = await _fetch_json(_WIKIDATA_API, {
        "action": "wbgetentities",
        "ids": "|".join(work_ids),
        "props": "claims",
        "format": "json",
    })

    if not data:
        return 0

    treffer = 0
    for qid in work_ids:
        entity = data.get("entities", {}).get(qid)
        if not entity:
            continue
        # P212 = ISBN-13, P957 = ISBN-10
        for prop in ("P212", "P957"):
            for isbn_val in _get_claim_values(entity, prop):
                clean = isbn_val.replace("-", "").replace(" ", "")
                if clean in known_isbns:
                    treffer += 1
    return treffer


def _extract_year(claims: dict, prop: str) -> int | None:
    """Extrahiert ein Jahr aus einem Wikidata-Datums-Claim."""
    prop_claims = claims.get(prop, [])
    for claim in prop_claims:
        time_val = (
            claim.get("mainsnak", {})
            .get("datavalue", {})
            .get("value", {})
            .get("time", "")
        )
        if time_val:
            try:
                return int(time_val.lstrip("+").split("-")[0])
            except (ValueError, IndexError):
                pass
    return None


async def download_author_photo(photo_url: str) -> dict[str, bytes] | None:
    """Lädt ein Autorenfoto herunter und erzeugt mehrere Größen.

    Gibt ein Dict mit Dateiname -> JPEG-Bytes zurück:
    - foto.jpg: Hauptbild (max 400x600)
    - foto_thumb.jpg: Thumbnail (max 120x180)
    - foto_mini.jpg: Mini-Vorschau (max 48x72)
    """
    if not photo_url:
        return None

    try:
        import asyncio

        def _download():
            resp = req.get(photo_url, headers={"User-Agent": _USER_AGENT}, timeout=20.0)
            resp.raise_for_status()
            return resp.content

        image_data = await asyncio.to_thread(_download)

        if len(image_data) < 500:
            return None

        from PIL import Image
        img = Image.open(io.BytesIO(image_data))

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        sizes = {
            "foto.jpg": (400, 600, 85),
            "foto_thumb.jpg": (120, 180, 80),
            "foto_mini.jpg": (48, 72, 75),
        }

        result = {}
        for filename, (w, h, quality) in sizes.items():
            resized = img.copy()
            resized.thumbnail((w, h), Image.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=quality, optimize=True)
            result[filename] = buffer.getvalue()

        return result

    except Exception as e:
        logger.warning("Autorenfoto-Download fehlgeschlagen: %s - %s", photo_url, e)
        return None


async def check_connection() -> dict:
    """Prüft die Verbindung zu Wikidata."""
    if not settings.wikipedia_enabled:
        return {"erreichbar": False, "grund": "Deaktiviert"}

    try:
        response = req.get(
            _WIKIDATA_API,
            params={"action": "wbgetentities", "ids": "Q1", "format": "json"},
            headers={"User-Agent": _USER_AGENT},
            timeout=5.0,
        )
        return {
            "erreichbar": response.status_code == 200,
            "status_code": response.status_code,
        }
    except Exception as e:
        return {"erreichbar": False, "grund": str(e)}
