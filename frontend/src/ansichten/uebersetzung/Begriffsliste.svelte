<script lang="ts">
  // Begriffsliste eines Buchs (BF-71, Entwurf Abschnitt 5): Suche und Neu bleiben stehen, nur die Liste rollt. Eine Änderung
  // übersetzt nur die Stellen neu, in denen der Begriff vorkommt.
  import { untrack } from "svelte";
  import { holeBegriffe, loescheBegriff } from "../../lib/api/uebersetzung";
  import { anzahl } from "../../lib/format";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import { uebersetzungen } from "../../lib/stand/uebersetzungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { Begriff, Herkunft } from "../../lib/uebersetzung/typen";
  import Begriffsformular from "./Begriffsformular.svelte";
  import { Buchuebersetzung } from "./fassung.svelte";

  let { params }: { params: Record<string, string> } = $props();

  const bezug = new Buchuebersetzung(untrack(() => Number(params.id)));
  let liste = $state<Begriff[] | null>(null);
  let fehler = $state("");
  let suche = $state("");
  /** offenes Formular: null zu, "neu" oder der Begriff */
  let formular = $state<Begriff | "neu" | null>(null);

  const HERKUNFT: Record<Herkunft, [string, string]> = { regel: ["Regel", "ruler-combined"], ki: ["KI", "robot"], hand: ["du", "user"], vorgabe: ["Standard", "gear"] };

  async function hole() {
    try {
      liste = await holeBegriffe(bezug.id);
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void Promise.all([bezug.laden(), hole()]));

  let gezeigt = $derived.by(() => {
    const s = suche.trim().toLowerCase();
    return (liste ?? []).filter((b) => !s || [b.englisch, b.deutsch, b.grund].some((t) => t.toLowerCase().includes(s)));
  });
  let vorhanden = $derived(new Set((liste ?? []).map((b) => b.englisch.toLowerCase())));

  function gespeichert(b: Begriff) {
    const da = (liste ?? []).some((x) => x.id === b.id);
    liste = da ? (liste ?? []).map((x) => (x.id === b.id ? b : x)) : [...(liste ?? []), b].sort((x, y) => x.englisch.localeCompare(y.englisch, "de"));
    melde.gut(da ? "Begriff geändert" : "Begriff aufgenommen");
    formular = null;
    if (bezug.deutsch) uebersetzungen.angestossen();
  }

  async function entfernen(b: Begriff) {
    const folgen = [`"${b.englisch}" steht danach nicht mehr in der Begriffsliste dieses Buchs.`];
    if (bezug.deutsch && b.stellen) folgen.push(`${anzahl(b.stellen, "Stelle", "Stellen")} mit dem Begriff ${b.stellen === 1 ? "wird" : "werden"} neu übersetzt; was du von Hand gesetzt oder angenommen hast, bleibt.`);
    if (!(await frage({ titel: "Begriff entfernen?", folgen, ja: "Entfernen" }))) return;
    try {
      await loescheBegriff(b.id);
      liste = (liste ?? []).filter((x) => x.id !== b.id);
      melde.gut("Begriff entfernt");
      if (bezug.deutsch) uebersetzungen.angestossen();
    } catch (e) {
      melde.schlecht(e, "Nicht entfernt");
    }
  }
</script>

<div class="werkzeug">
  <Knopf text="Zum Buch" symbol="arrow-left" klein href="/book/{bezug.id}" />
  <h1>Begriffsliste</h1>
  {#if bezug.buch}<span class="leise">{bezug.buch.title}</span>{/if}
</div>

<div class="inhalt rollen">
  {#if fehler && !liste}
    <Zustand art="fehler" text={fehler} onerneut={() => void hole()} />
  {:else if !liste}
    <Zustand art="laedt" text="Begriffsliste wird geladen" />
  {:else}
    <section class="laufkarte platte fuellt" aria-label="Begriffsliste">
      <div class="reihe">
        <input class="eingabe begriffsuche" type="search" placeholder="Begriff suchen ({liste.length})" aria-label="Begriff suchen" bind:value={suche} />
        <Knopf text="Begriff" symbol="plus" klein onclick={() => (formular = "neu")} />
        <span class="leise">Eine Änderung übersetzt nur die betroffenen Stellen neu.</span>
      </div>
      <div class="begriffsliste rollen" role="table" aria-label="Begriffe">
        <div class="begriffzeile kopf" role="row"><span>Englisch</span><span>Deutsch</span><span>Herkunft</span><span class="zahl">Stellen</span><span>Grund</span><span></span></div>
        {#each gezeigt as b (b.id)}
          {@const [herkunft, zeichen] = HERKUNFT[b.herkunft] ?? [b.herkunft, "circle"]}
          <div class="begriffzeile" role="row">
            <code>{b.englisch}</code>
            <span>{#if b.bleibt}<span class="leise">bleibt englisch</span>{:else}{b.deutsch}{/if}</span>
            <span class="leise"><Symbol name={zeichen} /> {herkunft}</span>
            <span class="zahl leise">{b.stellen}</span>
            <span class="grund">{b.grund}</span>
            <span class="reihe">
              <Knopf text="Bearbeiten" symbol="pen" nur klein frei onclick={() => (formular = b)} />
              <Knopf text="Entfernen" symbol="trash" nur klein frei onclick={() => void entfernen(b)} />
            </span>
          </div>
        {:else}
          <p class="leise">{liste.length ? "Kein Begriff passt zur Suche." : "Noch keine Begriffe. Beim Übersetzen schlagen Regeln und KI welche vor."}</p>
        {/each}
      </div>
    </section>
  {/if}
</div>

{#if formular}
  <Begriffsformular buch={bezug.id} begriff={formular === "neu" ? null : formular} {vorhanden} onschliessen={() => (formular = null)} ongespeichert={gespeichert} />
{/if}
