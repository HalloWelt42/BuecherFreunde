<script lang="ts">
  // Schwebendes Feld an einem Knopf. Hängt an der App statt an der Bühne, damit nichts es abschneidet.
  import type { Snippet } from "svelte";
  import { beiEsc } from "../flucht";

  let { anker, name, breite = "20rem", onschliessen, children }: { anker: HTMLElement | null; name: string; breite?: string; onschliessen: () => void; children: Snippet } = $props();
  let feld: HTMLElement | undefined = $state();

  function anDieApp(knoten: HTMLElement) {
    (knoten.closest(".app") ?? document.body).appendChild(knoten);
    setze(knoten);
    // Erst nach dem Umhängen: vorher ginge der Fokus verloren. Am Telefon bleibt die Tastatur zu.
    if (matchMedia("(hover: hover)").matches) knoten.querySelector<HTMLElement>("[data-fokus]")?.focus();
    return { destroy: () => knoten.remove() };
  }

  function setze(knoten: HTMLElement) {
    const rahmen = knoten.parentElement?.getBoundingClientRect();
    const a = anker?.getBoundingClientRect();
    if (!rahmen || !a) return;
    const b = knoten.offsetWidth;
    const h = knoten.offsetHeight;
    const links = Math.max(8, Math.min(a.left - rahmen.left, rahmen.width - b - 8));
    const unten = a.bottom - rahmen.top + 6;
    const oben = unten + h > rahmen.height - 8 ? Math.max(8, a.top - rahmen.top - h - 6) : unten;
    knoten.style.setProperty("--links", `${links}px`);
    knoten.style.setProperty("--oben", `${oben}px`);
  }

  $effect(() => {
    const ab = beiEsc(() => onschliessen());
    const daneben = (e: Event) => {
      const z = e.target as Node;
      if (!feld?.contains(z) && !anker?.contains(z)) onschliessen();
    };
    const neu = () => feld && setze(feld);
    document.addEventListener("pointerdown", daneben, true);
    addEventListener("resize", neu);
    return () => {
      ab();
      document.removeEventListener("pointerdown", daneben, true);
      removeEventListener("resize", neu);
    };
  });
</script>

<div class="schwebe menue glas dicht" style:--breite={breite} role="dialog" aria-label={name} bind:this={feld} use:anDieApp><div class="rollen">{@render children()}</div></div>
