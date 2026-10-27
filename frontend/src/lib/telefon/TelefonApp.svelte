<script>
  // Eigene Oberfläche für Telefon und Tablet: Suche, Buch und Leser. Alles Weitere (Verwaltung, Import,
  // Einstellungen) bleibt am Rechner; solche Adressen zeigen hier einen kurzen Hinweis.
  import { route, matchRoute } from "../router.svelte.js";
  import Reader from "../../pages/Reader.svelte";
  import TelefonSuche from "./TelefonSuche.svelte";
  import TelefonBuch from "./TelefonBuch.svelte";
  import TelefonHinweis from "./TelefonHinweis.svelte";

  const seiten = [
    { muster: "/book/:id/read", seite: Reader },
    { muster: "/book/:id", seite: TelefonBuch },
    { muster: "/search", seite: TelefonSuche },
    { muster: "/", seite: TelefonSuche },
  ];

  let aktuell = $derived.by(() => {
    for (const { muster, seite } of seiten) {
      const params = matchRoute(muster, route.path);
      if (params !== null) return { seite, params };
    }
    return { seite: TelefonHinweis, params: {} };
  });
</script>

<div class="telefon">
  {#key route.path}
    <aktuell.seite params={aktuell.params} telefon />
  {/key}
</div>

<style>
  .telefon {
    --lesbreite: 720px;
    height: 100vh;
    height: 100dvh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 17px;
  }
</style>
