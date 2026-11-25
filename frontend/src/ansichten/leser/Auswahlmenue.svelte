<script lang="ts">
  // Schwebt an der Auswahl: markieren, kopieren, vorlesen, in Schnellnotiz oder Buchnotiz
  import { beiEsc } from "../../lib/flucht";
  import { alsZitat, type Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import { verbindungen } from "../../lib/stand/verbindungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Farbreihe from "./Farbreihe.svelte";

  let { sitzung, rahmen, onabwahl }: { sitzung: Lesesitzung; rahmen: HTMLElement; onabwahl: () => void } = $props();

  const NOTIZEN_HOECHSTENS = 6;
  let schritt = $state<"tun" | "notiz">("tun");
  let a = $derived(sitzung.auswahl!);
  let breite = $state(0);
  let hoehe = $state(0);

  // Über der Auswahl, sonst darunter, immer im Rahmen
  let ort = $derived.by(() => {
    const r = rahmen.getBoundingClientRect();
    const links = Math.max(8, Math.min(r.width - breite - 8, a.x - r.left - breite / 2));
    const oben = a.oben - r.top - hoehe - 10;
    const unten = Math.min(r.height - hoehe - 8, a.unten - r.top + 10);
    return { links, oben: oben > 60 ? oben : Math.max(8, unten) };
  });

  $effect(() => beiEsc(zu));

  function zu() {
    sitzung.auswahl = null;
    onabwahl();
  }

  async function tun(arbeit: () => unknown, text = "") {
    await arbeit();
    if (text) melde.gut(text);
    zu();
  }

  function lies() {
    vorlesen.entsperre();
    vorlesen.lies(a.text, "Auswahl");
    zu();
  }
</script>

<!-- Ein Druck auf das Menü darf die Auswahl im Text nicht aufheben -->
<div class="auswahlmenue glas dicht" role="dialog" tabindex="-1" aria-label="Auswahl" bind:offsetWidth={breite} bind:offsetHeight={hoehe} style:left="{ort.links}px" style:top="{ort.oben}px" style:visibility={breite ? "visible" : "hidden"} onmousedown={(e) => e.preventDefault()}>
  {#if schritt === "tun"}
    {#if a.cfi}<Farbreihe name="Markieren" wert={sitzung.stift ? sitzung.stiftfarbe : ""} onwahl={(f) => void tun(() => sitzung.markiere(a, f))} />{/if}
    <div class="reihe knoepfe">
      <Knopf text="Kopieren" symbol="copy" klein frei onclick={() => void tun(() => navigator.clipboard.writeText(a.text), "Kopiert")} />
      <Knopf text="Vorlesen" symbol="volume-low" klein frei onclick={lies} />
      <Knopf text="Schnellnotiz" symbol="note-sticky" klein frei titel="An die Schnellnotiz anhängen" onclick={() => void tun(() => sitzung.anSchnellnotiz(alsZitat(a)))} />
      <Knopf text="Schnellnotiz ersetzen" symbol="right-left" nur klein frei onclick={() => void tun(() => sitzung.ersetzeSchnellnotiz(alsZitat(a)))} />
      <Knopf text="Buchnotiz" symbol="pen" klein frei onclick={() => (schritt = "notiz")} />
      {#if verbindungen.assistent}<Knopf text="Im Assistenten fragen" symbol="comments" klein frei extern href={verbindungen.frageAdresse(a.text)} />{/if}
    </div>
  {:else}
    <div class="reihe knoepfe">
      <Knopf text="Zurück" symbol="arrow-left" nur klein frei onclick={() => (schritt = "tun")} />
      <Knopf text="Neue Buchnotiz" symbol="plus" klein onclick={() => void tun(async () => { if (await sitzung.neueNotiz(alsZitat(a), a.ort)) melde.gut("Buchnotiz angelegt"); })} />
    </div>
    <div class="stellenliste">
      {#each sitzung.notizen.slice(0, NOTIZEN_HOECHSTENS) as n (n.id)}
        <div class="notizwahl">
          <span class="kurz">{n.content.slice(0, 60)}</span>
          <Knopf text="Anhängen" symbol="plus" nur klein frei onclick={() => void tun(() => sitzung.setzeNotiz(n, `${n.content}\n\n${alsZitat(a)}`), "Angehängt")} />
          <Knopf text="Ersetzen" symbol="right-left" nur klein frei onclick={() => void tun(() => sitzung.setzeNotiz(n, alsZitat(a)), "Ersetzt")} />
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .knoepfe {
    gap: 0;
  }
  .notizwahl {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    padding-left: 0.5rem;
  }
  .kurz {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.875rem;
  }
</style>
