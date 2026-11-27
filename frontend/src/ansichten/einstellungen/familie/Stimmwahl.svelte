<script lang="ts" module>
  import { ladeDienststimmen, type Dienststimmen } from "../../../lib/api/vorlesen";

  /** Die Stimmen der Vertonung, einmal je Seite für alle Zeilen */
  let katalogLaeuft: Promise<Dienststimmen> | null = null;
  function katalogHolen(): Promise<Dienststimmen> {
    katalogLaeuft ??= ladeDienststimmen().catch(() => {
      katalogLaeuft = null;
      return { da: false, stimmen: [], bereiche: [], hinweis: "" };
    });
    return katalogLaeuft;
  }
</script>

<script lang="ts">
  // Eine Stimme der Ansagen wählen (BF-78, Entwurf kinder-6 Abschnitt 5): "Probe" und die Stimme als Chip. Der Chip öffnet die
  // Stimmenwahl wie im Leser (Auswahl und "Probe hören") mit den Stimmen der Vertonung in Gruppen nach ihren Bereichen (privat,
  // fremd, eingebaut; BF-14) und der Stimme des Geräts für Installationen ohne sie; für ein Kind steht oben "wie die Familie".
  // Gibt die Vertonung keine privaten Stimmen frei, steht darunter der Grund und wo man sie freigibt. Erst "Wählen" speichert,
  // denn danach erstellt der Server alle festen Ansagen in dieser Stimme. Gebraucht für die Stimme der Familie und je Kind.
  import { ansageProbe, GERAETESTIMME } from "../../../lib/api/familie";
  import { freigabeHinweis, stimmgruppen } from "../../../lib/api/vorlesen";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import { stilleAdresse } from "../../../lib/vorlesen/ton";
  import Wertchip from "./Wertchip.svelte";

  interface Eigenschaften {
    /** Was gespeichert ist; leer: keine eigene Wahl */
    stimme: string;
    /** Nur beim Kind: die Stimme der Familie, die ohne eigene Wahl gilt; undefined: kein Eintrag "wie die Familie" */
    familie?: string;
    name: string;
    gesperrt?: boolean;
    /** Die Ansagen sind aus, die Stimme bewirkt gerade nichts: Probe und Wahl ruhen (BF-88) */
    stumm?: boolean;
    /** Probe nur als Zeichen (Liste der Profile) */
    nurSymbol?: boolean;
    onwahl: (stimme: string) => Promise<void>;
  }
  let { stimme, familie = undefined, name, gesperrt = false, stumm = false, nurSymbol = false, onwahl }: Eigenschaften = $props();

  /** Steht für "wie die Familie" in der Auswahl; gespeichert wird leer */
  const WIE_FAMILIE = "familie";

  let katalog = $state<Dienststimmen | null>(null);
  let spielt = $state(false);
  /** Gefragt, aber noch nicht zu hören: der Knopf dreht, bis die Probe spielt (BF-113) */
  let laedt = $state(false);
  let entwurf = $state<string | null>(null);
  let mitFamilie = $derived(familie !== undefined);
  /** Was wirklich spricht: die eigene Wahl, sonst die der Familie */
  let wirkt = $derived(stimme || familie || "");

  let gruppen = $derived.by(() => {
    const alle = [...stimmgruppen(katalog), ["Ohne Vertonung", [[GERAETESTIMME, "Stimme des Geräts"]]]] as [string, [string, string][]][];
    return mitFamilie ? ([["Vorgabe", [[WIE_FAMILIE, "wie die Familie"]]], ...alle] as [string, [string, string][]][]) : alle;
  });
  let freigabe = $derived(freigabeHinweis(katalog));

  /** Ist eine gewählte Klonstimme nicht mehr im Angebot (etwa nicht mehr freigegeben), steht sie als Klonstimme da */
  function nameVon(id: string): string {
    if (id === GERAETESTIMME) return "Stimme des Geräts";
    return katalog?.stimmen.find((s) => s.id === id)?.name ?? (id.startsWith("katalog:") ? id.slice("katalog:".length) : "Klonstimme");
  }

  let chip = $derived(stimme ? nameVon(stimme) : mitFamilie && familie ? "wie die Familie" : "Stimme wählen");

  $effect(() => {
    void katalogHolen().then((k) => (katalog = k));
  });

  /** Im Tippen freigegeben, sonst bleibt das Telefon stumm; der Ton kommt danach in dasselbe Element */
  async function probe(s: string) {
    if (!s || spielt) return;
    const ton = new Audio(stilleAdresse());
    void ton.play().catch(() => undefined);
    spielt = laedt = true;
    try {
      const satz = await ansageProbe(s);
      if (!satz.url) {
        // Die Stimme des Geräts spricht den Probesatz selbst
        speechSynthesis.cancel();
        const sprich = new SpeechSynthesisUtterance(satz.text);
        sprich.lang = "de-DE";
        sprich.onstart = () => (laedt = false);
        sprich.onend = sprich.onerror = () => (spielt = laedt = false);
        speechSynthesis.speak(sprich);
        return;
      }
      ton.src = satz.url;
      ton.onplaying = () => (laedt = false);
      ton.onended = ton.onerror = () => (spielt = laedt = false);
      await ton.play();
    } catch (e) {
      spielt = laedt = false;
      melde.schlecht(e, "Probe nicht abgespielt");
    }
  }

  /** Was in der Auswahl steht: der Entwurf, sonst die gespeicherte Wahl */
  function auswahlWert(): string {
    if (entwurf !== null) return entwurf;
    if (!stimme) return mitFamilie ? WIE_FAMILIE : (gruppen[0]?.[1][0]?.[0] ?? GERAETESTIMME);
    return stimme;
  }

  async function waehle(wert: string, zu: () => void) {
    zu();
    entwurf = null;
    const neu = wert === WIE_FAMILIE ? "" : wert;
    if (neu !== stimme) await onwahl(neu);
  }
</script>

<span class="reihe stimmtasten">
  <Knopf text="Probe" symbol="play" klein nur={nurSymbol} laeuft={laedt} gesperrt={!wirkt || stumm || spielt} titel={wirkt && !stumm ? `Probe mit ${nameVon(wirkt)}` : undefined} onclick={() => void probe(wirkt)} />
  <Wertchip text={chip} {name} gesperrt={gesperrt || stumm} breite="19rem">
    {#snippet children(zu)}
      {@const wert = auswahlWert()}
      {@const hoeren = wert === WIE_FAMILIE ? (familie ?? "") : wert}
      <div class="stimmwahl">
        <Auswahl name="Stimme" {gruppen} {wert} onwahl={(w) => (entwurf = w)} />
        <Knopf text="Probe hören" symbol="play" nur klein laeuft={laedt} gesperrt={!hoeren || spielt} onclick={() => void probe(hoeren)} />
      </div>
      {#if katalog?.hinweis}<p class="leise">{katalog.hinweis}</p>{/if}
      {#if freigabe}<p class="leise">{freigabe}</p>{/if}
      {#if wert === GERAETESTIMME}<p class="leise">Nur für Installationen ohne Vertonung: jedes Gerät spricht mit seiner eigenen Stimme.</p>{/if}
      {#if wert === WIE_FAMILIE && !familie}<p class="leise">Die Familie hat noch keine Stimme; bis dahin schweigen die Ansagen.</p>{/if}
      <Knopf text="Wählen" symbol="check" haupt klein gesperrt={(wert === WIE_FAMILIE ? "" : wert) === stimme} onclick={() => void waehle(wert, zu)} />
    {/snippet}
  </Wertchip>
</span>

<style>
  .stimmtasten {
    gap: 0.375rem;
    flex-wrap: nowrap;
    justify-content: flex-end;
  }
  .stimmwahl {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.5rem;
    align-items: center;
  }
  .stimmwahl :global(.auswahl) {
    width: 100%;
  }
</style>
