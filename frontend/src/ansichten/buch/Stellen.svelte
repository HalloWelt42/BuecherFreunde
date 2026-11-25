<script lang="ts">
  // Markierungen und Buchnotizen eines Buchs
  import { highlightsFuerBuch } from "../../lib/api/highlights";
  import { erstelleNotiz, notizenFuerBuch } from "../../lib/api/notes";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { BuchEinzeln, Markierung, Notiz } from "../../lib/typen";
  import Markierungszeile from "./Markierungszeile.svelte";
  import Notizzeile from "./Notizzeile.svelte";

  let { buch }: { buch: BuchEinzeln } = $props();

  let markierungen = $state<Markierung[]>([]);
  let notizen = $state<Notiz[]>([]);
  let geladen = $state(false);
  let neu = $state<{ text: string; seite: string } | null>(null);
  let speichert = $state(false);

  $effect(() => {
    const id = buch.id;
    let gilt = true;
    Promise.allSettled([highlightsFuerBuch(id), notizenFuerBuch(id)]).then(([m, n]) => {
      if (!gilt) return;
      markierungen = m.status === "fulfilled" ? m.value : [];
      notizen = n.status === "fulfilled" ? n.value : [];
      geladen = true;
    });
    return () => (gilt = false);
  });

  async function lege(e: SubmitEvent) {
    e.preventDefault();
    if (!neu?.text.trim()) return;
    speichert = true;
    try {
      const notiz = await erstelleNotiz(buch.id, { content: neu.text.trim(), page_reference: neu.seite.trim() || null });
      notizen = [notiz, ...notizen];
      neu = null;
    } catch (grund) {
      melde.schlecht(grund, "Notiz nicht gespeichert");
    } finally {
      speichert = false;
    }
  }

  function taste(e: KeyboardEvent) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) (e.currentTarget as HTMLTextAreaElement).form?.requestSubmit();
  }

  const fokussiere = (knoten: HTMLElement) => knoten.focus();
</script>

<Karte titel="Markiert und notiert" symbol="highlighter">
  <div>
    {#each markierungen as m (m.id)}
      <Markierungszeile {buch} {m} ongeloescht={() => (markierungen = markierungen.filter((x) => x.id !== m.id))} />
    {/each}
    {#each notizen as n (n.id)}
      <Notizzeile {buch} {n} ongeloescht={() => (notizen = notizen.filter((x) => x.id !== n.id))} />
    {/each}
    {#if geladen && !markierungen.length && !notizen.length}<p class="leise">Noch nichts markiert oder notiert.</p>{/if}
  </div>
  {#if neu}
    <form class="neu" onsubmit={lege}>
      <label class="feld">Notiz<textarea class="eingabe" rows="4" bind:value={neu.text} onkeydown={taste} use:fokussiere></textarea></label>
      <label class="feld">Seite oder Stelle<input class="eingabe" bind:value={neu.seite} placeholder="etwa 41" /></label>
      <div class="reihe"><Knopf text="Speichern" symbol="check" klein haupt art="submit" laeuft={speichert} gesperrt={!neu.text.trim()} /><Knopf text="Abbrechen" klein onclick={() => (neu = null)} /></div>
    </form>
  {:else}
    <div class="reihe"><Knopf text="Neue Notiz" symbol="plus" klein onclick={() => (neu = { text: "", seite: "" })} /></div>
  {/if}
</Karte>

<style>
  .neu {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: minmax(0, 1fr);
  }
</style>
