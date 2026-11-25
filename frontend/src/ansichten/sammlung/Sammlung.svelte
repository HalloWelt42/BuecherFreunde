<script lang="ts">
  // Eine Sammlung mit ihren Büchern, nach Bandnummer
  import { listeBooks } from "../../lib/api/books";
  import { holeSammlung } from "../../lib/api/collections";
  import { anzahl } from "../../lib/format";
  import { rollstand } from "../../lib/rollstand";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { Buch, Sammlung } from "../../lib/typen";
  import { regalansicht, regalarten } from "../bibliothek/ansicht.svelte";
  import Detailliste from "../bibliothek/Detailliste.svelte";
  import Liste from "../bibliothek/Liste.svelte";
  import Regal from "../bibliothek/Regal.svelte";
  import { nachBand } from "./reihenfolge";

  let { params }: { params: Record<string, string> } = $props();

  const JE_SEITE = 100;
  let id = $derived(Number(params.id));
  let sammlung = $state<Sammlung | null>(null);
  let liste = $state<Buch[]>([]);
  let fehler = $state("");
  let geladen = $state(false);
  let art = $derived(regalansicht.art);

  $effect(() => {
    void lade(id);
    return bestand.beiAenderung(() => void lade(id));
  });
  $effect(() => wahl.falls(liste[0]));

  async function lade(nummer: number) {
    fehler = "";
    try {
      const [s, buecher] = await Promise.all([holeSammlung(nummer), alleBuecher(nummer)]);
      if (nummer !== id) return;
      sammlung = s;
      liste = nachBand(buecher);
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      geladen = true;
    }
  }

  async function alleBuecher(nummer: number): Promise<Buch[]> {
    const seite = (n: number) => listeBooks({ sammlung: nummer, seite: n, pro_seite: JE_SEITE, sortierung: "titel", richtung: "asc" });
    const erste = await seite(1);
    const weitere = await Promise.all(Array.from({ length: Math.max(0, erste.seiten_gesamt - 1) }, (_, n) => seite(n + 2)));
    return [erste, ...weitere].flatMap((t) => t.buecher);
  }
</script>

<div class="werkzeug">
  {#if sammlung}<span class="sammlungsfarbe" style:background={sammlung.color}></span>{/if}
  <h1>{sammlung?.name ?? "Sammlung"}</h1>
  {#if geladen && sammlung}<span class="leise zahl">{anzahl(liste.length, "Buch", "Bücher")}</span>{/if}
  <span class="reihe schiebt">
    <Knopf text="In der Bibliothek filtern" symbol="filter" klein href="/?sammlung={id}" />
    <Knopf text="Verwalten" symbol="gear" klein href="/settings/sammlungen" />
    <Segment name="Ansicht" nurSymbole werte={regalarten} wert={art} onwahl={(w) => (regalansicht.art = w)} />
  </span>
</div>

<div class="inhalt rollen" use:rollstand={`/collection/${id}`}>
  {#if sammlung?.description}<p>{sammlung.description}</p>{/if}
  {#if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade(id)} />
  {:else if !geladen}
    <Zustand art="laedt" text="Sammlung wird geladen" />
  {:else if !liste.length}
    <Zustand text="In dieser Sammlung steht noch kein Buch. Auf der Buchseite lässt sich eines einsortieren."><Knopf text="Zur Bibliothek" symbol="book-bookmark" klein href="/" /></Zustand>
  {:else if art === "list"}<Liste {liste} sortierbar={false} />
  {:else if art === "detail-list"}<Detailliste {liste} />
  {:else}<Regal {liste} {art} />{/if}
</div>
