"""HTML-zu-Markdown-Konvertierung für Buchbeschreibungen."""

import re


def html_to_markdown(html: str) -> str:
    """Konvertiert einfaches HTML in Markdown.

    Wird verwendet für Beschreibungen aus Google Books, Open Library
    und anderen Quellen die HTML liefern.
    """
    if not html:
        return ""
    text = html
    # Block-Elemente in Absaetze wandeln
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<div[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<span[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</span>", "", text, flags=re.IGNORECASE)
    # Überschriften
    for level in range(6, 0, -1):
        prefix = "#" * level + " "
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, p=prefix: f"\n{p}{m.group(1).strip()}\n",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    # Inline-Formatierung
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(
        r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=re.IGNORECASE | re.DOTALL)
    # Restliche Tags entfernen
    text = re.sub(r"<[^>]+>", "", text)
    # HTML-Entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Mehrfache Leerzeilen bereinigen
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
