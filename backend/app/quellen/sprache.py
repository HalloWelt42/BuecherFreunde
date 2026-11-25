"""Sprachen einheitlich als zweibuchstabiges Kürzel, gleich wie die Quelle sie nennt."""

from __future__ import annotations

_KUERZEL = {
    "de": "ger deu deutsch german", "en": "eng englisch english", "fr": "fre fra französisch french", "es": "spa spanisch spanish", "it": "ita italienisch italian",
    "nl": "dut nld niederländisch dutch", "la": "lat latein latin", "pt": "por portugiesisch portuguese", "ru": "rus russisch russian", "pl": "pol polnisch polish",
    "sv": "swe schwedisch swedish", "da": "dan dänisch danish", "no": "nor nob nno norwegisch norwegian", "fi": "fin finnisch finnish", "cs": "cze ces tschechisch czech",
    "hu": "hun ungarisch hungarian", "tr": "tur türkisch turkish", "ja": "jpn japanisch japanese", "zh": "chi zho chinesisch chinese", "ar": "ara arabisch arabic",
    "el": "gre ell griechisch greek", "uk": "ukr ukrainisch ukrainian", "ro": "rum ron rumänisch romanian", "hr": "hrv scr kroatisch croatian", "sr": "srp scc serbisch serbian",
    "he": "heb hebräisch hebrew", "ko": "kor koreanisch korean", "ca": "cat katalanisch catalan", "grc": "altgriechisch",
}
_NACH_NAME = {name: kuerzel for kuerzel, namen in _KUERZEL.items() for name in (kuerzel, *namen.split())}
_OHNE = {"und", "mul", "zxx", "mis"}


def kuerzel(wert: str | None) -> str:
    """"ger", "deu", "Deutsch", "de-DE" -> "de"; Unbekanntes bleibt, wie es kam, Leeres bleibt leer."""
    w = (wert or "").strip()
    klein = w.lower().rsplit("/", 1)[-1]
    if not w or klein in _OHNE:
        return ""
    return _NACH_NAME.get(klein) or _NACH_NAME.get(klein.replace("_", "-").split("-")[0]) or w
