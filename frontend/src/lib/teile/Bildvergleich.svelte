<script lang="ts">
  // Kleines Bild einer Vergleichszeile; beim Überfahren oder Antippen groß
  import { beiEsc } from "../flucht";

  let { adresse, name }: { adresse: string; name: string } = $props();
  const BREITE = 280;
  let offen = $state(false);
  let kaputt = $state("");
  let knopf: HTMLElement | undefined = $state();

  $effect(() => {
    if (offen) return beiEsc(() => (offen = false));
  });

  function anDieApp(knoten: HTMLElement) {
    const app = knoten.closest(".app");
    if (!app || !knopf) return;
    app.appendChild(knoten);
    const setze = () => {
      const r = knopf!.getBoundingClientRect();
      const a = app.getBoundingClientRect();
      const rechts = r.right - a.left + 10;
      const links = rechts + BREITE > a.width - 8 ? r.left - a.left - BREITE - 10 : rechts;
      knoten.style.left = `${Math.max(8, Math.min(links, a.width - BREITE - 8))}px`;
      knoten.style.top = `${Math.max(8, Math.min(r.top - a.top, a.height - knoten.offsetHeight - 8))}px`;
    };
    setze();
    knoten.querySelector("img")?.addEventListener("load", setze);
    return { destroy: () => knoten.remove() };
  }
</script>

{#if kaputt === adresse}
  <span class="leise">Bild nicht erreichbar</span>
{:else}
  <button type="button" class="bild" bind:this={knopf} aria-label="{name}, vergrößern" aria-expanded={offen} onpointerenter={(e) => e.pointerType === "mouse" && (offen = true)} onpointerleave={() => (offen = false)} onclick={() => (offen = !offen)} onblur={() => (offen = false)}>
    <img src={adresse} alt={name} onerror={() => (kaputt = adresse)} />
  </button>
  {#if offen}<div class="gross glas dicht" style:width="{BREITE}px" use:anDieApp><img src={adresse} alt="" /></div>{/if}
{/if}

<style>
  .bild {
    display: block;
    border-radius: var(--r1);
    cursor: zoom-in;
  }
  .bild img {
    display: block;
    height: 5.5rem;
    width: auto;
    max-width: 100%;
    object-fit: contain;
    border-radius: var(--r1);
    box-shadow: 0 0 0 1px var(--linie);
  }
  .gross {
    position: absolute;
    z-index: 46;
    padding: 0.5rem;
    pointer-events: none;
  }
  .gross img {
    display: block;
    width: 100%;
    height: auto;
    border-radius: var(--r1);
  }
</style>
