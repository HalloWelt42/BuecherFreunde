<script lang="ts">
  // Stimme der Ansagen eines Kindes (BF-78, Entwurf kinder-5 Abschnitt 5): links, wie weit die festen Ansagen sind, rechts
  // "Probe" und die Stimme als Chip. Der Chip öffnet die Stimmenwahl wie im Leser (Auswahl und "Probe hören") mit den Stimmen
  // aus dem Katalog des Sprechdienstes und der Stimme des Geräts für Installationen ohne ihn. Erst "Wählen" speichert, denn mit
  // der Wahl erstellt der Server alle festen Ansagen in dieser Stimme (Auftrag "Ansagen erstellen").
  import { ansageProbe, ansagenStand, GERAETESTIMME, type Ansagenstand, type Profil } from "../../../lib/api/familie";
  import { ladeDienststimmen, type Dienststimmen } from "../../../lib/api/vorlesen";
  import { einstellungenVon } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import { schale } from "../../../lib/stand/schale.svelte";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import { stilleAdresse } from "../../../lib/vorlesen/ton";
  import { setze } from "./aendern";
  import Wertchip from "./Wertchip.svelte";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  /** So oft sieht die Zeile nach, solange die Ansagen entstehen */
  const NACHSEHEN_MS = 3000;
  /** Was das Gerät zur Probe sagt; die Stimmen des Sprechdienstes sprechen den Probesatz des Servers */
  const PROBE_GERAET = "So klingen die Ansagen.";
  const GRUPPE = { eigene: "Eigene Stimmen", weitere: "Weitere Stimmen", eingebaut: "Eingebaute Stimmen" } as const;

  let stimme = $derived(einstellungenVon(profil, familie.stufen.stufen).lesehilfen.stimme ?? "");
  let katalog = $state<Dienststimmen | null>(null);
  let stand = $state<Ansagenstand | null>(null);
  let spielt = $state(false);
  /** In der Wahl gerade gewählt, noch nicht gespeichert */
  let entwurf = $state("");

  let gruppen = $derived.by(() => {
    const aus = new Map<string, [string, string][]>();
    for (const s of katalog?.stimmen ?? []) aus.set(GRUPPE[s.gruppe], [...(aus.get(GRUPPE[s.gruppe]) ?? []), [s.id, s.name]]);
    return [...aus, ["Ohne Sprechdienst", [[GERAETESTIMME, "Stimme des Geräts"]]]] as [string, [string, string][]][];
  });
  let name = $derived(nameVon(stimme));

  function nameVon(id: string): string {
    if (!id) return "";
    if (id === GERAETESTIMME) return "Stimme des Geräts";
    return katalog?.stimmen.find((s) => s.id === id)?.name ?? id.replace(/^katalog:/, "");
  }

  let zeile = $derived.by(() => {
    if (!stimme) return "Noch keine Stimme gewählt";
    if (stimme === GERAETESTIMME) return "Das Gerät spricht die Ansagen selbst";
    if (!stand) return "";
    if (stand.laeuft || stand.fertig < stand.gesamt) return `werden erstellt: ${stand.fertig} von ${stand.gesamt}`;
    return `${stand.gesamt} feste Ansagen fertig, auch ohne Sprechdienst`;
  });
  let entsteht = $derived(!!stand && stimme !== GERAETESTIMME && (stand.laeuft || stand.fertig < stand.gesamt));

  $effect(() => {
    ladeDienststimmen().then((k) => (katalog = k)).catch(() => (katalog = { da: false, stimmen: [], hinweis: "" }));
  });

  // Stand der festen Ansagen; solange sie entstehen, wieder und wieder
  $effect(() => {
    const s = stimme;
    stand = null;
    if (!s || s === GERAETESTIMME) return;
    let uhr: ReturnType<typeof setTimeout> | undefined;
    let aus = false;
    const frage = async () => {
      try {
        const neu = await ansagenStand(s);
        if (aus) return;
        stand = neu;
        if (neu.laeuft || neu.fertig < neu.gesamt) uhr = setTimeout(() => void frage(), NACHSEHEN_MS);
      } catch {
        // ohne Antwort bleibt die Zeile ohne Stand; die nächste Wahl fragt neu
      }
    };
    void frage();
    return () => {
      aus = true;
      clearTimeout(uhr);
    };
  });

  /** Im Tippen freigegeben, sonst bleibt das Telefon stumm; der Ton kommt danach in dasselbe Element */
  async function probe(s: string) {
    if (!s || spielt) return;
    if (s === GERAETESTIMME) {
      speechSynthesis.cancel();
      const satz = new SpeechSynthesisUtterance(PROBE_GERAET);
      satz.lang = "de-DE";
      speechSynthesis.speak(satz);
      return;
    }
    const ton = new Audio(stilleAdresse());
    void ton.play().catch(() => undefined);
    spielt = true;
    try {
      const adresse = URL.createObjectURL(await ansageProbe(s));
      ton.src = adresse;
      ton.onended = ton.onerror = () => {
        URL.revokeObjectURL(adresse);
        spielt = false;
      };
      await ton.play();
    } catch (e) {
      spielt = false;
      melde.schlecht(e, "Probe nicht abgespielt");
    }
  }

  async function waehle(s: string, zu: () => void) {
    zu();
    if (s === stimme) return;
    // Der Server erstellt danach alle festen Ansagen in dieser Stimme; die Zeile zeigt, wie weit
    await setze(profil, "lesehilfen", { stimme: s });
  }
</script>

<div class="elternzeile">
  <span>Stimme der Ansagen{#if zeile}<small>{zeile}{#if entsteht}{" "}<button type="button" class="unterwahl" onclick={() => schale.umschalten("auftraege")}>Auftrag</button>{/if}</small>{/if}</span>
  <span class="reihe stimmtasten">
    <Knopf text="Probe" symbol="play" klein laeuft={spielt} gesperrt={!stimme} titel={stimme ? `Probe mit ${name}` : undefined} onclick={() => void probe(stimme)} />
    <Wertchip text={name || "Stimme wählen"} name="Stimme der Ansagen" gesperrt={!aendert} breite="19rem">
      {#snippet children(zu)}
        {@const wahl = entwurf || stimme || gruppen[0]?.[1][0]?.[0] || GERAETESTIMME}
        <div class="stimmwahl">
          <Auswahl name="Stimme" {gruppen} wert={wahl} onwahl={(w) => (entwurf = w)} />
          <Knopf text="Probe hören" symbol="play" nur klein laeuft={spielt} onclick={() => void probe(wahl)} />
        </div>
        {#if katalog?.hinweis}<p class="leise">{katalog.hinweis}</p>{/if}
        {#if wahl === GERAETESTIMME}<p class="leise">Nur für Installationen ohne Sprechdienst: jedes Gerät spricht mit seiner eigenen Stimme.</p>{/if}
        <Knopf text="Wählen" symbol="check" haupt klein gesperrt={wahl === stimme} onclick={() => void waehle(wahl, zu)} />
      {/snippet}
    </Wertchip>
  </span>
</div>

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
