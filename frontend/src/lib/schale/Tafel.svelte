<script lang="ts">
  // Untere Leiste am Telefon
  import { zuletztGelesen } from "../api/user-data";
  import { navigate, route } from "../router.svelte.js";
  import { melde } from "../stand/meldungen.svelte";
  import { schale } from "../stand/schale.svelte";
  import Symbol from "../teile/Symbol.svelte";

  const punkte = [["/", "Regal", "book-bookmark"], ["/search", "Suche", "magnifying-glass"], ["/lesen", "Lesen", "book-open"], ["/import", "Hinzufügen", "plus"]] as const;

  function hier(ziel: string): boolean {
    if (schale.leisteOffen) return false;
    return ziel === "/lesen" ? route.path.endsWith("/read") : route.path === ziel;
  }

  async function zumLesen() {
    schale.schliesseAlles();
    try {
      const [buch] = await zuletztGelesen(1);
      if (buch) navigate(`/book/${buch.id}/read`);
      else melde.info("Noch kein Buch angefangen");
    } catch (e) {
      melde.schlecht(e);
    }
  }
</script>

<nav class="tafel glas klar" aria-label="Bereiche">
  {#each punkte as [ziel, text, symbol] (ziel)}
    {#if ziel === "/lesen"}
      <button type="button" aria-current={hier(ziel) ? "page" : undefined} onclick={zumLesen}><Symbol name={symbol} />{text}</button>
    {:else}
      <a href={ziel} aria-current={hier(ziel) ? "page" : undefined} onclick={() => schale.schliesseAlles()}><Symbol name={symbol} />{text}</a>
    {/if}
  {/each}
  <button type="button" aria-current={schale.leisteOffen ? "page" : undefined} aria-expanded={schale.leisteOffen} onclick={() => schale.leisteUmschalten()}><Symbol name="ellipsis" />Mehr</button>
</nav>
