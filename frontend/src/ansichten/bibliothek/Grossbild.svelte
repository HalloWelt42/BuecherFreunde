<script lang="ts">
  // Großer Umschlag neben dem Mauszeiger, bleibt im Fenster
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Buch } from "../../lib/typen";

  let { buch, an }: { buch: Buch; an: HTMLElement } = $props();
  const BREITE = 280;
  const WARTE_MS = 350;

  function anDieApp(knoten: HTMLElement) {
    const uhr = setTimeout(() => {
      const app = knoten.closest(".app") ?? document.querySelector(".app");
      if (!app) return;
      app.appendChild(knoten);
      const r = an.getBoundingClientRect();
      const rahmen = app.getBoundingClientRect();
      const rechts = r.right - rahmen.left + 10;
      const links = rechts + BREITE > rahmen.width - 8 ? r.left - rahmen.left - BREITE - 10 : rechts;
      const hoehe = knoten.offsetHeight;
      knoten.style.left = `${Math.max(8, links)}px`;
      knoten.style.top = `${Math.max(8, Math.min(r.top - rahmen.top, rahmen.height - hoehe - 8))}px`;
      knoten.classList.add("da");
    }, WARTE_MS);
    return {
      destroy() {
        clearTimeout(uhr);
        knoten.remove();
      },
    };
  }
</script>

{#key buch.id}
  <div class="grossbild glas dicht" style:width="{BREITE}px" use:anDieApp aria-hidden="true">
    <Umschlag {buch} sofort />
    <b>{buch.title}</b>
    <span class="leise">{buch.author}</span>
  </div>
{/key}

<style>
  .grossbild {
    position: absolute;
    z-index: 35;
    padding: 0.625rem;
    display: grid;
    gap: 0.375rem;
    visibility: hidden;
    pointer-events: none;
  }
  .grossbild:global(.da) {
    visibility: visible;
  }
  .grossbild b {
    font: 600 1rem/1.25 var(--buchschrift);
  }
</style>
