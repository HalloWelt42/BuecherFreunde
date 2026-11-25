<script lang="ts">
  // Markiert und notiert: Stift, Markierungen, Buchnotizen, Etiketten
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { verbindungen } from "../../lib/stand/verbindungen.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Etikettfeld from "./Etikettfeld.svelte";
  import Etikettkarte from "./Etikettkarte.svelte";
  import Farbreihe from "./Farbreihe.svelte";
  import Markierungskarte from "./Markierungskarte.svelte";
  import Notizkarte from "./Notizkarte.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();

  let neu = $state("");
  let istText = $derived(["md", "txt"].includes(sitzung.buch.file_format));
  let benannt = $derived(sitzung.markierungen.filter((m) => m.label_name).length);
  let frage = $derived(sitzung.auswahl?.text ?? `${sitzung.buch.title}, ${sitzung.griffe?.hier().ort ?? ""}`);

  async function lege(e: Event) {
    e.preventDefault();
    const text = neu.trim();
    if (text && (await sitzung.neueNotiz(text))) neu = "";
  }
</script>

<h2>Markiert und notiert</h2>

<Haekchen text="Markierstift: Auswählen markiert sofort" an={sitzung.stift} onwahl={(an) => (sitzung.stift = an)} />
{#if sitzung.stift}<Farbreihe name="Farbe des Stifts" wert={sitzung.stiftfarbe} onwahl={(f) => (sitzung.stiftfarbe = f)} />{/if}

<section>
  <h3>Markierungen <span class="leise zahl">{sitzung.markierungen.length}{benannt ? `, ${benannt} benannt` : ""}</span></h3>
  {#each sitzung.markierungen as m (m.id)}<Markierungskarte {sitzung} {m} />{:else}<p class="leise">Text auswählen, dann eine Farbe antippen.</p>{/each}
</section>

<section>
  <h3>Buchnotizen <span class="leise zahl">{sitzung.notizen.length}</span></h3>
  <form class="neu" onsubmit={lege}>
    <textarea class="eingabe" rows="3" placeholder="Neue Notiz zu dieser Stelle" aria-label="Neue Notiz" bind:value={neu} onkeydown={(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && void lege(e)}></textarea>
    <div class="reihe">
      <Knopf text="Notiz anlegen" symbol="plus" klein art="submit" gesperrt={!neu.trim()} titel="Auch mit Strg und Eingabe" />
      <Knopf text="Kopieren" symbol="copy" nur klein frei gesperrt={!neu.trim()} onclick={() => void navigator.clipboard.writeText(neu)} />
      <Knopf text="An die Schnellnotiz" symbol="note-sticky" nur klein frei gesperrt={!neu.trim()} onclick={() => sitzung.anSchnellnotiz(neu)} />
      <Knopf text="Leeren" symbol="eraser" nur klein frei gesperrt={!neu} onclick={() => (neu = "")} />
    </div>
  </form>
  {#each sitzung.notizen as n (n.id)}<Notizkarte {sitzung} {n} />{/each}
</section>

{#if istText || sitzung.etiketten.length}
  <section>
    <h3>Etiketten <span class="leise zahl">{sitzung.etiketten.length}</span></h3>
    <Etikettfeld {sitzung} />
    {#each sitzung.etiketten as e (e.id)}<Etikettkarte {sitzung} {e} />{/each}
  </section>
{/if}

{#if verbindungen.assistent}<Knopf text="Stelle im Assistenten fragen" symbol="comments" klein extern href={verbindungen.frageAdresse(frage)} />{/if}

<style>
  section,
  .neu {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .neu .reihe {
    gap: 0.25rem;
  }
</style>
