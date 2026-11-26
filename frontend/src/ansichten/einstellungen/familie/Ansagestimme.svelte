<script lang="ts">
  // Stimme der Ansagen eines Kindes (BF-78, Entwurf kinder-6 Abschnitt 5): links, wie weit die festen Ansagen sind, rechts
  // "Probe" und die Stimme als Chip. Ohne eigene Wahl gilt die Stimme der Familie ("wie die Familie"); gibt es keine, schweigen
  // die Ansagen und der Chip bittet um eine Wahl. Solange weder Hinweise noch Tasten angesagt werden (in der Gestaltung groß
  // anfangs), bewirkt die Stimme nichts und ist gesperrt (Entwurf kinder-7).
  import { ansagenStand, GERAETESTIMME, type Ansagenstand, type Profil } from "../../../lib/api/familie";
  import { einstellungenVon } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import { schale } from "../../../lib/stand/schale.svelte";
  import { setze } from "./aendern";
  import Stimmwahl from "./Stimmwahl.svelte";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  /** So oft sieht die Zeile nach, solange die Ansagen entstehen */
  const NACHSEHEN_MS = 3000;

  let hilfen = $derived(einstellungenVon(profil, familie.stufen.stufen).lesehilfen);
  let eigene = $derived(hilfen.stimme ?? "");
  /** Die Stimme spricht nur, wenn Hinweise oder Tasten angesagt werden */
  let wirkt = $derived(hilfen.hinweise_sprechen || hilfen.tasten_ansagen);
  let familienstimme = $derived(familie.stimme);
  /** Was wirklich spricht */
  let stimme = $derived(eigene || familienstimme);
  let stand = $state<Ansagenstand | null>(null);
  let entsteht = $derived(!!stand && (stand.stand === "wartet" || stand.stand === "laeuft"));

  let zeile = $derived.by(() => {
    if (!wirkt) return "wirkt, sobald Hinweise oder Tasten an sind";
    if (!stimme) return "Noch keine Stimme gewählt, die Ansagen schweigen";
    if (stimme === GERAETESTIMME) return "Das Gerät spricht die Ansagen selbst";
    if (!stand) return "";
    if (stand.stand === "fehler") return stand.grund || "Die Ansagen entstehen gerade nicht";
    if (entsteht) return `werden erstellt: ${stand.fertig} von ${stand.gesamt}`;
    return `${stand.gesamt} feste Ansagen fertig, auch ohne Sprechdienst`;
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
        if (!neu || neu.stand === "wartet" || neu.stand === "laeuft") uhr = setTimeout(() => void frage(), NACHSEHEN_MS);
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
</script>

<div class="elternzeile" class:ohne-wirkung={!wirkt}>
  <span>Stimme der Ansagen{#if zeile}<small>{zeile}{#if wirkt && (entsteht || stand?.stand === "fehler")}{" "}<button type="button" class="unterwahl" onclick={() => schale.umschalten("auftraege")}>Auftrag</button>{/if}</small>{/if}</span>
  <Stimmwahl stimme={eigene} familie={familienstimme} name="Stimme der Ansagen" gesperrt={!aendert} stumm={!wirkt} onwahl={(s) => setze(profil, "lesehilfen", { stimme: s })} />
</div>
