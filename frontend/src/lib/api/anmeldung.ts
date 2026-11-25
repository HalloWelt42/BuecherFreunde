// Anmelden mit der Kellerwolke: Passwort oder Kopplungscode. Antwortet mit der Anmeldung für diesen Browser.
import type { AppAngaben } from "./config";

export async function ladeAppAngaben(): Promise<AppAngaben> {
  const antwort = await fetch("/api/anmeldung/app");
  if (!antwort.ok) throw new Error(`Fehler ${antwort.status}`);
  return antwort.json();
}

async function sende(weg: string, daten: Record<string, string>): Promise<string> {
  let antwort: Response;
  try {
    antwort = await fetch(weg, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(daten) });
  } catch {
    throw new Error("Der Server ist nicht erreichbar");
  }
  const inhalt = await antwort.json().catch(() => ({}));
  if (!antwort.ok) throw new Error(typeof inhalt.detail === "string" ? inhalt.detail : antwort.status === 401 ? "Anmeldung fehlgeschlagen" : `Fehler ${antwort.status}`);
  return inhalt.token;
}

export const meldeAn = (kennung: string, passwort: string): Promise<string> => sende("/api/anmeldung", { kennung, passwort });
export const kopple = (code: string, name: string, art: string): Promise<string> => sende("/api/anmeldung/koppeln", { code, name, art });
