<script lang="ts" generics="T">
  // Lange Listen in einer rollenden Fläche (.rollen): ab vielen Einträgen in Stücken, und nur die Stücke nahe dem Blick stehen
  // im Dokument. Die übrigen halten ihre Höhe frei, gemessen oder geschätzt, so rollt die Liste wie zuvor. Ein Stück, in dem
  // gerade geschrieben wird, bleibt stehen. Bei wenigen Einträgen steht alles da wie immer (BF-47).
  import type { Snippet } from "svelte";
  import { SvelteSet } from "svelte/reactivity";

  interface Eigenschaften {
    eintraege: readonly T[];
    schluessel: (e: T) => string | number;
    karte: Snippet<[T]>;
    /** Ab so vielen Einträgen in Stücken */
    ab?: number;
    stueck?: number;
    /** Höhe eines Eintrags in Pixeln, bis einer gemessen ist */
    schaetzung?: number;
  }
  let { eintraege, schluessel, karte, ab = 60, stueck = 20, schaetzung = 120 }: Eigenschaften = $props();

  let stuecke = $derived(eintraege.length < ab ? [] : Array.from({ length: Math.ceil(eintraege.length / stueck) }, (_, i) => eintraege.slice(i * stueck, (i + 1) * stueck)));
  /** Nahe dem Blick; am Anfang das erste, damit beim Öffnen nichts leer aufblitzt */
  const nah = new SvelteSet<number>([0]);
  /** Mit dem Fokus darin */
  const gehalten = new SvelteSet<number>();
  /** Gemessene Höhe je Stück, solange es nicht dasteht */
  const gemessen = new Map<number, number>();
  /** Mittlere Höhe eines Eintrags aus allen Messungen */
  let mittel = $state(0);
  let liste: HTMLElement | undefined = $state();

  const frei = (i: number, anzahl: number) => gemessen.get(i) ?? anzahl * (mittel || schaetzung);

  function merke(i: number, hoehe: number) {
    gemessen.set(i, hoehe);
    let summe = 0;
    let zahl = 0;
    for (const [nr, h] of gemessen) {
      summe += h;
      zahl += stuecke[nr]?.length ?? 0;
    }
    mittel = zahl ? summe / zahl : 0;
  }

  $effect(() => {
    if (!liste || !stuecke.length) return;
    const beobachter = new IntersectionObserver(
      (meldungen) => {
        for (const m of meldungen) {
          const i = Number((m.target as HTMLElement).dataset.stueck);
          if (m.isIntersecting) nah.add(i);
          else if (nah.has(i)) {
            if (m.boundingClientRect.height) merke(i, m.boundingClientRect.height);
            nah.delete(i);
          }
        }
      },
      { root: liste.closest(".rollen"), rootMargin: "100% 0px" },
    );
    for (const e of liste.querySelectorAll(":scope > .stueck")) beobachter.observe(e);
    return () => beobachter.disconnect();
  });

  function fokus(i: number, e: FocusEvent) {
    if (e.type === "focusin") gehalten.add(i);
    else if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node | null)) gehalten.delete(i);
  }
</script>

{#if !stuecke.length}
  {#each eintraege as e (schluessel(e))}{@render karte(e)}{/each}
{:else}
  <div class="sichtliste" bind:this={liste}>
    {#each stuecke as teil, i (i)}
      {@const da = nah.has(i) || gehalten.has(i)}
      <div class="stueck" data-stueck={i} style:height={da ? undefined : `${frei(i, teil.length)}px`} onfocusin={(e) => fokus(i, e)} onfocusout={(e) => fokus(i, e)}>
        {#if da}{#each teil as e (schluessel(e))}{@render karte(e)}{/each}{/if}
      </div>
    {/each}
  </div>
{/if}

<style>
  .sichtliste,
  .stueck {
    display: grid;
    gap: inherit;
    grid-template-columns: minmax(0, 1fr);
    align-content: start;
  }
</style>
