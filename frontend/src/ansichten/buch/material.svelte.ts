// Begleitmaterial eines Buchs (BF-81): Liste und Funde vom Server, Umbenennen, Entfernen nach der Folgenvorschau, Funde mit
// Ja oder Nein. Hinzugefügt wird über die Annahme (Hochladen in Teilen, Fortschritt bei den Aufträgen); ist eine Datei
// angekommen, lädt die Liste neu.
import { ApiError } from "../../lib/api/client";
import { benenneMaterialUm, entferneMaterial, ladeMaterial, lehneFundAb, materialfolgen, nimmFundAn, type Fund, type Material, type Materialfolgen, type Materialliste } from "../../lib/api/material";
import { anzahl, groesse } from "../../lib/format";
import { annahme } from "../../lib/stand/annahme.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";
import { frage } from "../../lib/stand/rueckfrage.svelte";

/** Was beim Entfernen geschieht, als ganze Sätze */
export function materialfolgensaetze(f: Materialfolgen): string[] {
  const wo = `${f.pfad}, ${groesse(f.groesse)}`;
  return [
    f.papierkorb ? `Die Datei kommt in den Papierkorb der Kellerwolke und lässt sich dort zurückholen: ${wo}.` : `Die Datei liegt nur auf diesem Gerät und ist danach endgültig fort: ${wo}.`,
    ...(f.suche ? [`Die Suche findet ihren Text nicht mehr${f.seiten ? ` (${anzahl(f.seiten, "Seite", "Seiten")})` : ""}.`] : []),
    "Das Buch und das übrige Material bleiben.",
  ];
}

/** Name ohne Endung und die Endung mit Punkt; die Endung bleibt beim Umbenennen */
export function namensteile(name: string): { stamm: string; endung: string } {
  const punkt = name.lastIndexOf(".");
  return punkt > 0 ? { stamm: name.slice(0, punkt), endung: name.slice(punkt) } : { stamm: name, endung: "" };
}

export class Materialstand {
  liste = $state<Materialliste | null>(null);
  fehler = $state("");
  /** Kennung des Materials, das gerade umbenannt wird */
  benennt = $state("");
  arbeitet = $state(false);

  material = $derived<Material[]>(this.liste?.material ?? []);
  funde = $derived<Fund[]>(this.liste?.funde ?? []);
  /** Woran man sieht, dass eine Datei für dieses Buch bei der Annahme weitergekommen ist */
  kennung = $derived(annahme.eintraege.filter((e) => e.material_fuer === this.buch).map((e) => `${e.id}:${e.stand}`).join("|"));
  /** Was für dieses Buch gerade hochgeladen, gelesen oder ausgepackt wird */
  unterwegs = $derived(
    annahme.hochladungen.filter((h) => h.ziel.art === "material" && h.ziel.buch === this.buch && h.lage !== "beim_server" && !h.eintrag).length +
      annahme.eintraege.filter((e) => e.material_fuer === this.buch && ["wartet", "laedt", "liest", "angaben", "entpacken"].includes(e.stand)).length,
  );

  constructor(public readonly buch: number) {}

  async laden(): Promise<void> {
    try {
      this.liste = await ladeMaterial(this.buch);
      this.fehler = "";
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
    }
  }

  hinzufuegen(dateien: File[], entpacken: boolean): void {
    if (!dateien.length) return;
    annahme.materialHinzu(this.buch, dateien, entpacken);
    melde.info(`${anzahl(dateien.length, "Datei kommt", "Dateien kommen")} dazu, der Fortschritt steht bei den Aufträgen.`);
  }

  async umbenennen(m: Material, stamm: string): Promise<boolean> {
    const neu = `${stamm.trim()}${namensteile(m.name).endung}`;
    if (!stamm.trim() || neu === m.name) {
      this.benennt = "";
      return true;
    }
    this.arbeitet = true;
    try {
      const geaendert = await benenneMaterialUm(this.buch, m.id, neu);
      if (this.liste) this.liste = { ...this.liste, material: this.liste.material.map((x) => (x.id === m.id ? geaendert : x)) };
      this.benennt = "";
      return true;
    } catch (e) {
      melde.schlecht(e, "Nicht umbenannt");
      return false;
    } finally {
      this.arbeitet = false;
    }
  }

  /** Fragt mit den Folgen vom Server und entfernt erst nach dem Ja; hat sich seither etwas geändert, nicht */
  async entfernen(m: Material): Promise<void> {
    let f: Materialfolgen;
    try {
      f = await materialfolgen(this.buch, m.id);
    } catch (e) {
      return melde.schlecht(e, "Folgen nicht ermittelt, nichts entfernt");
    }
    const ja = await frage({ titel: "Begleitmaterial entfernen?", text: `${f.name}, zu ${f.titel}`, folgen: materialfolgensaetze(f), ja: f.papierkorb ? "Entfernen" : "Endgültig entfernen" });
    if (!ja) return;
    this.arbeitet = true;
    try {
      await entferneMaterial(this.buch, m.id, f.stand);
      melde.gut(f.papierkorb ? `${f.name} liegt im Papierkorb der Kellerwolke.` : `${f.name} entfernt.`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) melde.info("Inzwischen hat sich etwas geändert. Bitte die Folgen noch einmal ansehen.");
      else melde.schlecht(e, "Nicht entfernt");
    } finally {
      this.arbeitet = false;
      await this.laden();
    }
  }

  /** Ja: die Datei neben dem Original wird Begleitmaterial; Nein: sie bleibt, wo sie ist, und kommt nicht wieder */
  async fund(f: Fund, ja: boolean): Promise<void> {
    this.arbeitet = true;
    try {
      if (ja) {
        const m = await nimmFundAn(this.buch, f.knoten);
        melde.gut(`${m.name} ist jetzt Begleitmaterial.`);
      } else {
        await lehneFundAb(this.buch, f.knoten);
      }
    } catch (e) {
      melde.schlecht(e, ja ? "Nicht übernommen" : "Nicht abgelehnt");
    } finally {
      this.arbeitet = false;
      await this.laden();
    }
  }
}
