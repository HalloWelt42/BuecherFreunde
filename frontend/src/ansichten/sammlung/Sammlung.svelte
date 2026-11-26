<script lang="ts">
  // Eine Sammlung als eigenes Regal (BF-66): nach Band, auf dem Schild "Band N" und der Titel ohne Reihennamen.
  // Der Schnellfilter steht als q in der Adresse. Mit der Fähigkeit "luecken" (BF-75) stehen die Bände je Sprache in eigenen
  // Reihen, fehlende als Platzhalter; Dateien kommen über die Vorschau in eine Lücke oder als Stapel in die Sammlung.
  import { listeBooks } from "../../lib/api/books";
  import { holeSammlung } from "../../lib/api/collections";
  import { vonGesamt } from "../../lib/format";
  import { navigate, route } from "../../lib/router.svelte";
  import { rollstand } from "../../lib/rollstand";
  import Schnellfilterchip from "../../lib/schale/Schnellfilterchip.svelte";
  import Suchfeld from "../../lib/schale/Suchfeld.svelte";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { alsEintrag } from "../../lib/stand/eintraege";
  import { filter } from "../../lib/stand/filter.svelte";
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
  import { baende } from "../bibliothek/sammlungseintrag";
  import Sammlungsformular from "../einstellungen/Sammlungsformular.svelte";
  import { autorenText, reihenkopf } from "./angaben";
  import { darfAbrufen } from "../../lib/stand/abrufe";
  import { ich } from "../../lib/stand/ich.svelte";
  import { brauchbar, gezogeneDateien } from "../hinzu/dateien";
  import Lueckenregal from "./Lueckenregal.svelte";
  import { Lueckenstand } from "./lueckenstand.svelte";

  let { params }: { params: Record<string, string> } = $props();

  const JE_SEITE = 100;
  let id = $derived(Number(params.id));
  let sammlung = $state<Sammlung | null>(null);
  let liste = $state<Buch[]>([]);
  /** Wie viele Bücher die Sammlung ohne Schnellfilter hat */
  let ohneSuche = $state(0);
  let fehler = $state("");
  let geladen = $state(false);
  let bearbeiten = $state(false);
  let art = $derived(regalansicht.art);
  let wort = $derived((route.params as Record<string, string>).q ?? "");
  let eintraege = $derived(liste.map(alsEintrag));
  /** Was auf dem Schild vor dem Titel wegfällt: der Name der Sammlung und der Kopf, den ihre Titel tragen */
  let reihe = $derived([sammlung?.name ?? "", reihenkopf(liste.map((b) => b.title))]);
  let zahlen = $derived(wort ? vonGesamt(liste.length, ohneSuche) : [baende(liste.length), autorenText(liste)].filter(Boolean).join(", "));

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

  // Lücken (BF-75): mit den Büchern geladen und neu, wenn sich am Bestand etwas ändert; solange nachgeschlagen wird, öfter
  let lueckenstand = $derived(new Lueckenstand(id));
  $effect(() => {
    const l = lueckenstand;
    void l.laden();
    return bestand.beiAenderung(() => void l.laden());
  });
  $effect(() => {
    void lueckenstand.luecken;
    return lueckenstand.nachsehen();
  });
  let mitReihen = $derived(!!lueckenstand.luecken && !wort && art !== "list" && art !== "detail-list");
  let mitHochladen = $derived(darfAbrufen("luecken") && ich.darf("hinzufuegen"));
  let feld: HTMLInputElement | undefined = $state();

  function gewaehlt() {
    const dateien = brauchbar(feld?.files ?? []);
    if (feld) feld.value = "";
    void lueckenstand.hochladen(dateien);
  }

  const mitDateien = (e: DragEvent) => mitHochladen && !!e.dataTransfer?.types.includes("Files");
  async function abgelegt(e: DragEvent) {
    if (e.dataTransfer) await lueckenstand.hochladen(await gezogeneDateien(e.dataTransfer));
  }
  $effect(() => schnellfilter.biete(sammlungsfilter));

  async function lade(nummer: number, such: string) {
    fehler = "";
    try {
      const [s, buecher] = await Promise.all([holeSammlung(nummer), alleBuecher(nummer, such)]);
      if (nummer !== id || such !== wort) return;
      sammlung = s;
      liste = buecher.liste;
      ohneSuche = buecher.ohneSuche;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      geladen = true;
    }
  }

  /** Alle Bände, nach Bandnummer vom Server geordnet */
  async function alleBuecher(nummer: number, such: string): Promise<{ liste: Buch[]; ohneSuche: number }> {
    const seite = (n: number) => listeBooks({ sammlung: nummer, suche: such, seite: n, pro_seite: JE_SEITE, sortierung: "band", richtung: "asc" });
    const erste = await seite(1);
    const weitere = await Promise.all(Array.from({ length: Math.max(0, erste.seiten_gesamt - 1) }, (_, n) => seite(n + 2)));
    return { liste: [erste, ...weitere].flatMap((t) => t.buecher), ohneSuche: erste.gesamt_ohne_suche ?? erste.gesamt };
  }
</script>

<div class="werkzeug">
  <Suchfeld id="suchfeld-m" klasse="suchfeld-mobil" />
  <Knopf text="Bibliothek" symbol="arrow-left" klein href={filter.letzteAdresse} />
  <h1>{sammlung?.name ?? "Sammlung"}</h1>
  {#if geladen && sammlung}<span class="leise zahl">{zahlen}</span>{/if}
  <Schnellfilterchip ziel={sammlungsfilter} />
  <span class="reihe schiebt">
    <Segment name="Ansicht" nurSymbole werte={regalarten} wert={art} onwahl={(w) => (regalansicht.art = w)} />
    {#if mitHochladen}<Knopf text="Hochladen" symbol="cloud-arrow-up" klein gesperrt={!sammlung} titel="Dateien oder eine ZIP in diese Sammlung, über die Vorschau" onclick={() => feld?.click()} />{/if}
    <Knopf text="Zuordnen" symbol="right-left" klein href="/zuordnen/sammlung/{id}" />
    <Knopf text="Bearbeiten" symbol="pen" klein gesperrt={!sammlung} onclick={() => (bearbeiten = true)} />
  </span>
</div>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="inhalt rollen" use:rollstand={`/collection/${id}`} ondragover={(e) => mitDateien(e) && e.preventDefault()} ondrop={(e) => { if (mitDateien(e)) { e.preventDefault(); void abgelegt(e); } }}>
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
    <Zustand text="In dieser Sammlung steht noch kein Buch."><Knopf text="Zuordnen" symbol="right-left" klein href="/zuordnen/sammlung/{id}" /></Zustand>
  {:else if art === "list"}<Liste {eintraege} sortierbar={false} />
  {:else if art === "detail-list"}<Detailliste {eintraege} />
  {:else if mitReihen}<Lueckenregal stand={lueckenstand} {art} {reihe} mitAblegen={mitHochladen} />
  {:else}<Regal {eintraege} {art} {reihe} />{/if}
</div>
{#if mitHochladen}<input type="file" multiple accept=".pdf,.epub,.mobi,.txt,.md,.zip" hidden bind:this={feld} onchange={gewaehlt} />{/if}

{#if bearbeiten && sammlung}<Sammlungsformular {sammlung} onschliessen={() => (bearbeiten = false)} />{/if}
