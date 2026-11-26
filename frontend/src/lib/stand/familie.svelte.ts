// Die Familie (BF-78): welche Profile es gibt, ob beim Start gewählt werden muss, die Wahl selbst und der Wechsel.
// Nach der Anmeldung des Geräts fragt der Start GET /api/familie: mit gültigem Schlüssel oder nur einem Profil ohne PIN
// geht es gleich weiter, sonst kommt "Wer liest?". Ein an ein Kind gebundenes Gerät öffnet dieses Profil direkt.
import { getProfil, oeffneInhalte, setProfil } from "../api/client";
import {
  bindeGeraet, ladeFamilie, ladeStufen, loeseGeraet, verlasseProfil, waehleProfil, type Familie, type Nachweis, type Profil, type Stufen, type Wahl,
} from "../api/familie";
import { sprich } from "../hintergrund";
import { ich } from "./ich.svelte";

export type Phase = "laedt" | "wahl" | "bereit" | "fehler";

const OHNE_STUFEN: Stufen = { stufen: [], lesezeit: [] };

class Familienstand {
  phase = $state<Phase>("laedt");
  familie = $state<Familie | null>(null);
  fehler = $state("");
  stufen = $state<Stufen>(OHNE_STUFEN);

  profile = $derived<Profil[]>(this.familie?.profile ?? []);
  /** Das Kind, an das dieses Gerät gebunden ist; null: keins */
  gebunden = $derived(this.familie?.geraet.gebunden_an ?? null);
  /** Was "Wer liest?" zeigt: auf einem gebundenen Gerät nur dieses Profil */
  waehlbar = $derived(this.gebunden ? this.profile.filter((p) => p.id === this.gebunden) : this.profile);
  /** Ein Wechsel hat nur Sinn mit mehr als einem Profil oder einer PIN */
  wechselbar = $derived(this.profile.length > 1 || this.profile.some((p) => p.hat_pin || p.hat_bild_pin));
  /** Mit nur einem Profil sieht niemand sonst etwas; "Nur für mich" hätte keine Wirkung */
  mehrere = $derived(this.profile.length > 1);

  profil(id: string): Profil | undefined {
    return this.profile.find((p) => p.id === id);
  }

  async starte(): Promise<void> {
    this.phase = "laedt";
    this.fehler = "";
    try {
      const f = await ladeFamilie();
      this.familie = f;
      if (!f.braucht_wahl) {
        const einzig = f.profile.length === 1 ? f.profile[0] : null;
        // Wie bisher mit einem Profil ohne PIN: trotzdem einen Schlüssel holen, damit ein zweites Profil später nicht aussperrt
        if (!getProfil() && einzig && !einzig.hat_pin && !einzig.hat_bild_pin) await this.#nimm(await waehleProfil(einzig.id));
        else await ich.laden();
        this.phase = "bereit";
        return;
      }
      // Der gemerkte Schlüssel gilt nicht mehr (gewechselt, gelöscht, abgelaufen)
      setProfil("");
      if (f.geraet.gebunden_an && (await this.#oeffneGebunden(f.geraet.gebunden_an))) return;
      this.phase = "wahl";
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
      this.phase = "fehler";
    }
  }

  /** Das gebundene Kind ohne Bild-PIN öffnen; verlangt der Server sie doch, kommt die Wahl mit nur diesem Profil */
  async #oeffneGebunden(id: string): Promise<boolean> {
    try {
      await this.#nimm(await waehleProfil(id));
      this.phase = "bereit";
      return true;
    } catch {
      return false;
    }
  }

  /** Wählt ein Profil mit PIN oder Bild-PIN; ein Fehler (falsche PIN, Wartezeit) geht an die Profilwahl */
  async waehle(id: string, nachweis: Nachweis = {}): Promise<void> {
    await this.#nimm(await waehleProfil(id, nachweis));
    this.phase = "bereit";
  }

  async #nimm(wahl: Wahl): Promise<void> {
    setProfil(wahl.schluessel);
    ich.setze(wahl.profil);
    // Bilder, Dateien und Ereignisströme gehören ab jetzt diesem Profil
    await oeffneInhalte();
  }

  /**
   * Profil wechseln: verlässt das Profil am Server, vergisst Schlüssel und Lesestoff und beginnt die Seite neu, damit nichts
   * vom bisherigen Profil stehen bleibt; danach kommt "Wer liest?".
   */
  async wechseln(): Promise<void> {
    await verlasseProfil();
    await this.neuBeginnen();
  }

  /**
   * Ein gebundenes Gerät verlassen (das Schloss im Kinderbereich): mit der PIN eines Elternteils löst es die Bindung und
   * verlässt das Kind, sonst öffnete das Gerät gleich wieder dieses Profil.
   */
  async verlassenGebunden(elternPin: string): Promise<void> {
    await loeseGeraet(elternPin);
    await verlasseProfil(elternPin);
    await this.neuBeginnen();
  }

  /** Dieses Gerät fest auf ein Kind stellen und es ihm übergeben: danach öffnet es nur noch dieses Profil */
  async binde(kindId: string, elternPin: string): Promise<void> {
    await bindeGeraet(kindId, elternPin);
    await verlasseProfil(elternPin);
    await this.neuBeginnen();
  }

  /**
   * Nach dem Verlassen eines Profils: Schlüssel und Lesestoff vergessen, die Seite beginnt neu mit "Wer liest?" und danach
   * in der Bibliothek, denn wer jetzt liest, sieht vielleicht nicht, was eben offen war.
   */
  async neuBeginnen(): Promise<void> {
    setProfil("");
    await sprich({ art: "abgemeldet" });
    location.replace("/");
  }

  /** Ein geändertes Profil an seine Stelle, ohne alles neu zu laden */
  ersetze(p: Profil): void {
    if (!this.familie) return;
    this.familie = { ...this.familie, profile: this.familie.profile.map((alt) => (alt.id === p.id ? p : alt)) };
  }

  /** Nach Änderungen im Elternbereich: Profile und Bindung neu */
  async laden(): Promise<void> {
    this.familie = await ladeFamilie();
  }

  async ladeStufen(): Promise<void> {
    if (this.stufen.stufen.length) return;
    this.stufen = await ladeStufen();
  }
}

export const familie = new Familienstand();
