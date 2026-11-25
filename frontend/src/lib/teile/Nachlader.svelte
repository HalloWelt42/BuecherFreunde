<script lang="ts">
  // Rückt diese Stelle in die Nähe des sichtbaren Bereichs, wird die nächste Seite geholt
  import { zahl } from "../format";
  let { geladen, gesamt, laedt = false, onmehr }: { geladen: number; gesamt: number; laedt?: boolean; onmehr: () => void } = $props();
  let stelle: HTMLElement | undefined = $state();

  $effect(() => {
    if (!stelle || geladen >= gesamt || laedt) return;
    const beobachter = new IntersectionObserver((e) => e.some((x) => x.isIntersecting) && onmehr(), { root: stelle.closest(".rollen"), rootMargin: "700px" });
    beobachter.observe(stelle);
    return () => beobachter.disconnect();
  });
</script>

<p class="leise zahl nachlader" bind:this={stelle} aria-live="polite">{zahl(geladen)} von {zahl(gesamt)}</p>
