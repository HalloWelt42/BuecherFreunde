<script lang="ts">
  // Eine Sammlung mit ihren Büchern, nach Bandnummer; der Schnellfilter steht als q in der Adresse
  import { listeBooks } from "../../lib/api/books";
  import { holeSammlung } from "../../lib/api/collections";
  import { anzahl, vonGesamt } from "../../lib/format";
  import { navigate, route } from "../../lib/router.svelte";
  import { rollstand } from "../../lib/rollstand";
  import Schnellfilterchip from "../../lib/schale/Schnellfilterchip.svelte";
  import Suchfeld from "../../lib/schale/Suchfeld.svelte";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { schnellfilter, type Filterziel } from "../../lib/stand/schnellfilter.svelte";
  import { suche } from "../../lib/stand/suche.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { Buch, Sammlung } from "../../lib/typen";
  import { regalansicht, regalarten } from "../bibliothek/ansicht.svelte";
  import Detailliste from "../bibliothek/Detailliste.svelte";
  import Liste from "../bibliothek/Liste.svelte";
  import Regal from "../bibliothek/Regal.svelte";
  import { BUCHHINWEIS } from "../bibliothek/schnellfilter";
  import { nachBand } from "./reihenfolge";

  let { params }: { params: Record<string, string> } = $props();

  const JE_SEITE = 100;
  let id = $derived(Number(params.id));
  let sammlung = $state<Sammlung | null>(null);
  let liste = $state<Buch[]>([]);
  /** Wie viele Bücher die Sammlung ohne Schnellfilter hat */
  let ohneSuche = $state(0);
  let fehler = $state("");
  let geladen = $state(false);
  let art = $derived(regalansicht.art);
  let wort = $derived((route.params as Record<string, string>).q ?? "");

  const sammlungsfilter: Filterziel = {
    get wort() {
      return wort;
    },
    hinweis: BUCHHINWEIS,
    get treffer() {
      return geladen ? liste.length : null;
    },
    get gesamt() {
      return geladen ? ohneSuche : null;
    },
    filtere(neu) {
      navigate(neu ? `/collection/${id}?${new URLSearchParams({ q: neu })}` : `/collection/${id}`, !!neu && !!wort);
    },
  };

  $effect(() => {
    const [nummer, such] = [id, wort];
    void lade(nummer, such);
    return bestand.beiAenderung(() => void lade(nummer, such));
  });
  $effect(() => wahl.falls(liste[0]));
  $effect(() => schnellfilter.biete(sammlungsfilter));

  async function lade(nummer: number, such: string) {
    fehler = "";
    try {
      const [s, buecher] = await Promise.all([holeSammlung(nummer), alleBuecher(nummer, such)]);
      if (nummer !== id || such !== wort) return;
      sammlung = s;
      liste = nachBand(buecher.liste);
      ohneSuche = buecher.ohneSuche;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      geladen = true;
    }
  }

  async function alleBuecher(nummer: number, such: string): Promise<{ liste: Buch[]; ohneSuche: number }> {
    const seite = (n: number) => listeBooks({ sammlung: nummer, suche: such, seite: n, pro_seite: JE_SEITE, sortierung: "titel", richtung: "asc" });
    const erste = await seite(1);
    const weitere = await Promise.all(Array.from({ length: Math.max(0, erste.seiten_gesamt - 1) }, (_, n) => seite(n + 2)));
    return { liste: [erste, ...weitere].flatMap((t) => t.buecher), ohneSuche: erste.gesamt_ohne_suche ?? erste.gesamt };
  }
</script>

<div class="werkzeug">
  <Suchfeld id="suchfeld-m" klasse="suchfeld-mobil" />
  {#if sammlung}<span class="sammlungsfarbe" style:background={sammlung.color}></span>{/if}
  <h1>{sammlung?.name ?? "Sammlung"}</h1>
  {#if geladen && sammlung}<span class="leise zahl">{wort ? vonGesamt(liste.length, ohneSuche) : anzahl(liste.length, "Buch", "Bücher")}</span>{/if}
  <Schnellfilterchip ziel={sammlungsfilter} />
  <span class="reihe schiebt">
    <Knopf text="In der Bibliothek filtern" symbol="filter" klein href="/?sammlung={id}" />
    <Knopf text="Verwalten" symbol="gear" klein href="/settings/sammlungen" />
    <Segment name="Ansicht" nurSymbole werte={regalarten} wert={art} onwahl={(w) => (regalansicht.art = w)} />
  </span>
</div>

<div class="inhalt rollen" use:rollstand={`/collection/${id}`}>
  {#if sammlung?.description}<p>{sammlung.description}</p>{/if}
  {#if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade(id, wort)} />
  {:else if !geladen}
    <Zustand art="laedt" text="Sammlung wird geladen" />
  {:else if !liste.length && wort}
    <Zustand text={`Kein Buch passt zu "${wort}".`}>
      <Knopf text="Filter leeren" symbol="xmark" klein onclick={() => schnellfilter.leere(sammlungsfilter)} />
      <Knopf text="In allen Büchern suchen" symbol="magnifying-glass" klein onclick={() => suche.suche(wort)} />
    </Zustand>
  {:else if !liste.length}
    <Zustand text="In dieser Sammlung steht noch kein Buch. Auf der Buchseite lässt sich eines einsortieren."><Knopf text="Zur Bibliothek" symbol="book-bookmark" klein href="/" /></Zustand>
  {:else if art === "list"}<Liste {liste} sortierbar={false} />
  {:else if art === "detail-list"}<Detailliste {liste} />
  {:else}<Regal {liste} {art} />{/if}
</div>
