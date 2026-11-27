// BF-78: Kein Stand ruft einen Weg, den das aktive Profil nicht darf. Die Stufe Jugend nutzt die Oberfläche der Erwachsenen,
// ohne Katalog, KI, Bearbeiten, Hinzufügen und Einstellungen; ihre Schale fragt nur, was sie darf.
import { render, screen } from "@testing-library/svelte";
import type { Faehigkeit, Ich, Profil } from "../src/lib/api/familie";
import { ABRUFE, darfAbrufen, mitAuftraegen } from "../src/lib/stand/abrufe";
import { annahme } from "../src/lib/stand/annahme.svelte";
import { auftraege } from "../src/lib/stand/auftraege.svelte";
import { bestand } from "../src/lib/stand/bestand.svelte";
import { ich } from "../src/lib/stand/ich.svelte";
import { uebersetzungen } from "../src/lib/stand/uebersetzungen.svelte";
import { verbindungen } from "../src/lib/stand/verbindungen.svelte";
import { werkarten } from "../src/lib/stand/werkarten.svelte";
import Kopf from "../src/lib/schale/Kopf.svelte";

const JUGEND: Faehigkeit[] = ["lesen", "vorlesen", "lesezeichen", "suche", "favoriten", "sammeln", "markierungen", "notizen", "etiketten", "privat", "ausfuehren"];
const VERWALTUNG: Faehigkeit[] = [...JUGEND, "nachschlagen", "katalog", "hinzufuegen", "bearbeiten", "freigeben", "ki", "loeschen", "einstellungen", "profile", "luecken"];
/** Die Wege, die die Stufe Jugend bisher mit 403 beantwortet bekam */
const VERBOTEN = ["/api/katalog", "/api/verbindungen", "/api/config/update-check", "/api/einordnung/stand", "/api/books/rescan/status", "/api/annahme", "/api/fassungen", "/api/einrichtung/auftraege"];

const profil = (rolle: Profil["rolle"]): Profil => ({ id: "p-7", name: "Malve", zeichen: "feather", farbe: "#6366f1", rolle, stufe: rolle === "kind" ? "jugend" : null, hat_pin: false, hat_bild_pin: false });

function ichAls(rolle: Profil["rolle"], faehigkeiten: Faehigkeit[]): Ich {
  return {
    profil: profil(rolle), faehigkeiten, darstellung: {}, lesehilfen: null, einblick: [], katze: { an: false, name: "", schnurren: false },
    lesezeit: { an: false, heute_s: 0, grenze_s: null, rest_s: null, ruht: false, ruhe_bis: null, hinweis_ab_s: null },
  } as unknown as Ich;
}

function server() {
  const f = vi.fn((weg: string) => {
    const pfad = weg.split("?")[0];
    const leer = ["/api/categories", "/api/collections", "/api/verbindungen", "/api/fassungen", "/api/einrichtung/auftraege"].includes(pfad) ? [] : {};
    const daten = pfad === "/api/annahme" ? { eintraege: [], zaehler: { alle: 0, laeuft: 0, klaeren: 0, da: 0, fertig: 0 } } : leer;
    return Promise.resolve(new Response(JSON.stringify(daten), { status: 200 }));
  });
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

/** Alles, was die Schale beim Start anstößt (lib/schale/Schale.svelte) */
async function schaleStartet(): Promise<void> {
  await Promise.all([bestand.laden(), annahme.starte(), verbindungen.laden()]);
  auftraege.starte();
  werkarten.starte();
  uebersetzungen.starte();
  await new Promise((r) => setTimeout(r, 0));
}

function anhalten(): void {
  annahme.halte();
  auftraege.halte();
  werkarten.halte();
  uebersetzungen.halte();
  verbindungen.halte();
}

const gerufen = (f: ReturnType<typeof server>) => f.mock.calls.map(([weg]) => String(weg).split("?")[0]);

afterEach(() => {
  anhalten();
  ich.setze(null);
});

describe("Abrufe nach den Fähigkeiten (BF-78)", () => {
  it("nennt für jeden Abruf eine Fähigkeit, die es gibt", () => {
    expect(Object.values(ABRUFE).every((f) => VERWALTUNG.includes(f))).toBe(true);
  });

  it("ruft für die Stufe Jugend keinen Weg, den sie nicht darf", async () => {
    ich.setze(ichAls("kind", JUGEND));
    const f = server();
    await schaleStartet();
    const wege = gerufen(f);
    expect(wege).toContain("/api/config/stats");
    for (const weg of VERBOTEN) expect(wege).not.toContain(weg);
    expect(Object.keys(ABRUFE).some((a) => darfAbrufen(a as keyof typeof ABRUFE))).toBe(false);
  });

  it("ruft mit allen Fähigkeiten alle diese Wege", async () => {
    ich.setze(ichAls("verwaltung", VERWALTUNG));
    const f = server();
    await schaleStartet();
    const wege = gerufen(f);
    for (const weg of VERBOTEN) expect(wege).toContain(weg);
  });

  it("zeigt die Taste Aufträge nur, wenn es Aufträge zu sehen gibt", () => {
    server();
    ich.setze(ichAls("kind", JUGEND));
    expect(mitAuftraegen()).toBe(false);
    const ohne = render(Kopf);
    expect(screen.queryByRole("button", { name: /Aufträge|läuft|laufen/ })).toBeNull();
    ohne.unmount();
    ich.setze(ichAls("verwaltung", VERWALTUNG));
    expect(mitAuftraegen()).toBe(true);
    render(Kopf);
    expect(screen.getByRole("button", { name: "Aufträge" })).toBeTruthy();
  });
});
