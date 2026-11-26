// Die Familie (BF-78): welche Profile es gibt, ob beim Start gewählt werden muss, die Wahl selbst, der Wechsel und die
// Bindung des Geräts an ein Kind. Nach der Anmeldung des Geräts fragt der Start GET /api/familie: gilt der gemerkte Schlüssel
// (aktiv) oder gibt es nur ein Profil ohne PIN, geht es gleich weiter, sonst kommt "Wer liest?". Ein an ein Kind gebundenes
// Gerät öffnet dieses Profil direkt; nach der PIN der Eltern ist die Wahl dort eine Weile offen, die Bindung bleibt.
import { getProfil, setProfil } from "../api/client";
import {
  bindeGeraet, ladeFamilie, ladeStufen, loeseGeraet, verlasseProfil, waehleProfil, type Familie, type Nachweis, type Profil, type Stufen,
  type Wahl, type Zugang,
} from "../api/familie";
import { OHNE_ZUGANG } from "../familie";
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
  /** Das Kind, dessen Profil dieses Gerät gerade nur öffnet; null: keins, auch solange die Wahl offen ist */
  gebunden = $derived(this.familie?.geraet.gebunden_an ?? null);
  /** Worauf das Gerät fest gestellt ist, auch während die Wahl offen ist */
  festAuf = $derived(this.familie?.geraet.fest_auf ?? null);
  /** Nach der PIN der Eltern darf auf dem gebundenen Gerät eine Weile jemand anders wählen */
  offen = $derived(!!this.familie?.geraet.offen);
  /** Was "Wer liest?" zeigt: auf einem gebundenen Gerät schickt der Server nur dieses Profil */
  waehlbar = $derived(this.gebunden ? this.profile.filter((p) => p.id === this.gebunden) : this.profile);
  /** Ein Wechsel hat nur Sinn mit mehr als einem Profil oder einer PIN */
  wechselbar = $derived(this.profile.length > 1 || this.profile.some((p) => p.hat_pin || p.hat_bild_pin));
  /** Mit nur einem Profil sieht niemand sonst etwas; "Nur für mich" hätte keine Wirkung */
  mehrere = $derived(this.profile.length > 1);
  /** PIN und Bild-PIN, wie der Server sie annimmt */
  zugang = $derived<Zugang>(this.stufen.zugang ?? OHNE_ZUGANG);

  profil(id: string): Profil | undefined {
    return this.profile.find((p) => p.id === id);
  }

  async starte(): Promise<void> {
    this.phase = "laedt";
    this.fehler = "";
    try {
      const [f] = await Promise.all([ladeFamilie(), this.ladeStufen()]);
      this.familie = f;
      // Der gemerkte Schlüssel gilt noch: gleich weiter
      if (f.aktiv && getProfil()) {
        await ich.laden();
        this.phase = "bereit";
        return;
      }
      setProfil("");
      // Wie bisher mit einem Profil ohne PIN: trotzdem einen Schlüssel holen, damit ein zweites Profil später nicht aussperrt
      const einzig = f.profile.length === 1 ? f.profile[0] : null;
      if (!f.braucht_wahl && einzig) {
        await this.waehle(einzig.id);
        return;
      }
      if (f.geraet.gebunden_an && (await this.#oeffneGebunden(f.geraet.gebunden_an))) return;
      this.phase = "wahl";
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
      this.phase = "fehler";
    }
  }

  /** Das gebundene Kind ohne Bild-PIN öffnen; hat es eine, kommt die Wahl mit nur diesem Profil */
  async #oeffneGebunden(id: string): Promise<boolean> {
    const kind = this.profil(id);
    if (kind?.hat_pin || kind?.hat_bild_pin) return false;
    try {
      await this.waehle(id);
      return true;
    } catch {
      return false;
    }
  }

  /** Wählt ein Profil mit PIN oder Bild-PIN; ein Fehler (falsche PIN, Wartezeit) geht an die Profilwahl */
  async waehle(id: string, nachweis: Nachweis = {}): Promise<void> {
    this.#nimm(await waehleProfil(id, nachweis));
    this.phase = "bereit";
  }

  /** Die Wahl setzt am Server auch das Cookie für Bilder, Dateien und Ströme */
  #nimm(wahl: Wahl): void {
    setProfil(wahl.schluessel);
    ich.setze(wahl.profil);
  }

  /** Der Server verlangt ein Profil (401 profil_waehlen): der Schlüssel gilt nicht mehr, also neu wählen, nie abmelden */
  profilFehlt(): void {
    if (this.phase === "bereit") void this.neuBeginnen();
  }

  /**
   * Profil wechseln: verlässt das Profil am Server, vergisst Schlüssel und Lesestoff und beginnt die Seite neu, damit nichts
   * vom bisherigen Profil stehen bleibt; danach kommt "Wer liest?". Auf einem gebundenen Gerät öffnet es danach wieder das Kind.
   */
  async wechseln(): Promise<void> {
    await verlasseProfil();
    await this.neuBeginnen();
  }

  /**
   * Das Kind eines gebundenen Geräts verlassen (das Schloss im Kinderbereich): mit der PIN eines Elternteils ist die Wahl auf
   * diesem Gerät danach eine Weile offen, die Bindung bleibt.
   */
  async verlassenGebunden(elternPin: string): Promise<void> {
    await verlasseProfil(elternPin);
    await this.neuBeginnen();
  }

  /** Dieses Gerät fest auf ein Kind stellen und es ihm übergeben: danach öffnet es nur noch dieses Profil */
  async binde(kindId: string, elternPin: string): Promise<void> {
    await bindeGeraet(kindId, elternPin);
    await verlasseProfil();
    await this.neuBeginnen();
  }

  /** Die Bindung lösen: mit der PIN eines Elternteils, als Verwaltung ohne sie */
  async loese(elternPin?: string): Promise<void> {
    await loeseGeraet(elternPin);
    await this.laden();
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

  /** Nach Änderungen im Elternbereich oder nach einer Antwort wie PIN vergessen: Profile und Bindung neu */
  async laden(neu?: Familie): Promise<void> {
    this.familie = neu ?? (await ladeFamilie());
  }

  async ladeStufen(): Promise<void> {
    if (this.stufen.stufen.length) return;
    this.stufen = await ladeStufen();
  }
}

export const familie = new Familienstand();
