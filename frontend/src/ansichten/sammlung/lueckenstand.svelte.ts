// Lücken einer Sammlung (BF-75) für ihr Regal: Reihen je Sprache vom Server, Ausblenden, Hochladen in eine Lücke oder als
// Stapel in die Sammlung über die Vorschau (BF-80), ein gemeinfreies Buch in die Lücke holen oder bei den gemeinfreien Büchern
// zeigen (BF-98). Nur mit der Fähigkeit "luecken" (lib/stand/abrufe.ts).
import { angabenAus, holeInDieLuecke } from "../../lib/api/gutenberg";
import { blendeLueckeAus, ladeLuecken, type Ausblendgrund, type Luecke, type Reihe, type Sammlungsluecken } from "../../lib/api/luecken";
import { lueckenvorgabe } from "../../lib/luecken";
import { navigate } from "../../lib/router.svelte";
import { darfAbrufen } from "../../lib/stand/abrufe";
import { annahme } from "../../lib/stand/annahme.svelte";
import { gutenberg } from "../../lib/stand/gutenberg.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";

/** Solange eine Sprache nachgeschlagen wird, fragt das Regal so oft nach */
const NACHSEHEN_MS = 5000;

export class Lueckenstand {
  luecken = $state<Sammlungsluecken | null>(null);
  fehler = $state("");
  arbeitet = $state(false);

  /** Wird eine Sprache gerade bei den Quellen nachgeschlagen (und ruht nicht mit Grund)? */
  offen = $derived(this.luecken?.reihen.some((r) => r.nachschlagen.stand === "offen" && !r.nachschlagen.grund) ?? false);

  constructor(public readonly sammlung: number) {}

  async laden(): Promise<void> {
    if (!darfAbrufen("luecken")) return;
    try {
      this.luecken = await ladeLuecken(this.sammlung);
      this.fehler = "";
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
    }
  }

  /** Nachsehen, solange nachgeschlagen wird; liefert das Aufräumen */
  nachsehen(): () => void {
    if (!this.offen) return () => {};
    const uhr = setTimeout(() => void this.laden(), NACHSEHEN_MS);
    return () => clearTimeout(uhr);
  }

  /** "Gibt es nicht" oder "Brauche ich nicht": der Platzhalter verschwindet, zurückholen geht unter Bearbeiten */
  async ausblenden(l: Luecke, r: Reihe, grund: Ausblendgrund): Promise<boolean> {
    this.arbeitet = true;
    try {
      this.luecken = await blendeLueckeAus(this.sammlung, l.sprache, l.nummer, grund);
      melde.gut(`Band ${l.nummer}, ${r.name}, ausgeblendet. Zurückholen geht unter Bearbeiten.`);
      return true;
    } catch (e) {
      melde.schlecht(e, "Nicht ausgeblendet");
      return false;
    } finally {
      this.arbeitet = false;
    }
  }

  /** Das gemeinfreie Buch einer Lücke holen: wie jedes gemeinfreie Buch, dann in der Vorschau mit Sammlung, Band und Sprache der
   * Lücke, wie beim Hochladen in die Lücke */
  async holeGemeinfrei(l: Luecke): Promise<void> {
    if (!l.gemeinfrei) return;
    try {
      const { vorschau } = await holeInDieLuecke(angabenAus(l.gemeinfrei), this.sammlung, String(l.nummer), l.sprache);
      await annahme.auffrischen();
      navigate(`/import/vorschau/${vorschau}`);
    } catch (e) {
      melde.schlecht(e, "Nicht geholt");
    }
  }

  /** Bei den gemeinfreien Büchern zeigen: dort ist die Suche gefüllt und die Vorschläge stehen da */
  zeigeGemeinfrei(l: Luecke): void {
    if (!l.gemeinfrei) return;
    gutenberg.oeffnen(l.gemeinfrei.titel, l.sprache);
    navigate("/import");
  }

  /** In eine Lücke oder, ohne Lücke, als Stapel in die Sammlung; immer über die Vorschau */
  async hochladen(dateien: File[], l: Luecke | null = null): Promise<void> {
    if (!dateien.length) return;
    try {
      const vorschau = await annahme.nimmAn(dateien, false, l ? lueckenvorgabe(this.sammlung, l) : { sammlung_id: this.sammlung });
      navigate(`/import/vorschau/${vorschau}`);
    } catch (e) {
      melde.schlecht(e, "Nicht hochgeladen");
    }
  }
}
