<script lang="ts">
  // Ein Code in Kästchen, in der Mitte mit Abstand: beim Koppeln und beim Umzug (BF-82). `anzeige` zeigt einen fertigen Code
  // (Vorleseprogramme hören ihn in zwei Hälften); ohne steht ein Eingabefeld darüber (Codefeld), das Kästchen ist dann nur Bild.
  let { code, laenge, aktiv = -1, anzeige = false }: { code: string; laenge: number; aktiv?: number; anzeige?: boolean } = $props();

  const stellen = $derived(Array.from({ length: laenge }, (_, n) => n));
  const haelfte = $derived(laenge / 2);
</script>

<span class="kaestchen" style:--stellen={laenge} role={anzeige ? "img" : undefined} aria-label={anzeige ? `Einmalcode ${code.slice(0, haelfte)} ${code.slice(haelfte)}` : undefined} aria-hidden={anzeige ? undefined : "true"}>
  {#each stellen as n (n)}<span class="k" class:mitte={n === haelfte} class:aktiv={n === aktiv}>{code[n] ?? ""}</span>{/each}
</span>

<style>
  .kaestchen {
    display: grid;
    grid-template-columns: repeat(var(--stellen), minmax(0, 1fr));
    gap: 0.25rem;
  }
  .k {
    height: 3rem;
    display: grid;
    place-items: center;
    border-radius: var(--r1);
    font: 600 1.25rem var(--codeschrift);
    background: var(--vertieft);
    box-shadow:
      inset 0 1px 2px rgb(var(--schatten) / 0.16),
      inset 0 0 0 1px var(--linie);
  }
  .k.mitte {
    margin-left: 0.375rem;
  }
  .k.aktiv {
    box-shadow: inset 0 0 0 2px var(--messing);
  }
</style>
