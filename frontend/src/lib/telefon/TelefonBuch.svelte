<script>
  // Buch am Telefon: Umschlag, Titel, Autor, ein großer Knopf zum Lesen und die Beschreibung. Bearbeiten bleibt am Rechner.
  import { holeBuch, coverUrl, dateiUrl } from "../api/books.js";
  import { parseProgress } from "../utils/reading.js";
  import { navigate } from "../router.svelte.js";

  let { params } = $props();

  let buch = $state(null);
  let fehler = $state("");

  $effect(() => {
    lade(Number(params.id));
  });

  async function lade(id) {
    fehler = "";
    try {
      buch = await holeBuch(id);
    } catch (e) {
      fehler = e.message;
    }
  }

  let prozent = $derived(buch ? parseProgress(buch.reading_position, buch.page_count) : 0);
  let angefangen = $derived(!!buch?.reading_position);

  let eckdaten = $derived(
    buch
      ? [
          buch.year,
          buch.file_format?.toUpperCase(),
          buch.page_count > 0 ? `${buch.page_count} Seiten` : "",
          buch.publisher,
        ].filter(Boolean)
      : [],
  );

  function zurueck() {
    if (history.length > 1) history.back();
    else navigate("/");
  }
</script>

<header class="kopf">
  <button class="zurueck" onclick={zurueck} aria-label="Zurück">
    <i class="fa-solid fa-arrow-left"></i>
  </button>
  <span class="kopf-titel">{buch?.title || ""}</span>
</header>

<main class="inhalt">
  {#if fehler}
    <p class="meldung">Buch konnte nicht geladen werden: {fehler}</p>
  {:else if buch}
    <div class="oben">
      <img class="umschlag" src={coverUrl(buch.id, buch.updated_at)} alt=""
        onerror={(e) => (e.currentTarget.style.visibility = "hidden")} />
      <div class="angaben">
        <h1 class="titel">{buch.title}</h1>
        <p class="autor">{buch.author || "Unbekannt"}</p>
        {#if eckdaten.length > 0}
          <p class="eckdaten">{eckdaten.join(" · ")}</p>
        {/if}
      </div>
    </div>

    <a class="lesen" href="/book/{buch.id}/read">
      <i class="fa-solid fa-book-open"></i>
      {angefangen ? `Weiterlesen${prozent > 0 ? ` (${prozent} %)` : ""}` : "Lesen"}
    </a>
    {#if angefangen}
      <a class="nebenknopf" href="/book/{buch.id}/read?restart=1">
        <i class="fa-solid fa-backward-step"></i> Von vorn
      </a>
    {/if}
    <a class="nebenknopf" href={dateiUrl(buch.id)} download={buch.file_name || buch.title}>
      <i class="fa-solid fa-download"></i> Herunterladen
    </a>

    {#if buch.description}
      <h2 class="abschnitt">Beschreibung</h2>
      <p class="beschreibung">{buch.description}</p>
    {/if}
  {/if}
</main>

<style>
  .kopf {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: env(safe-area-inset-top) 0.5rem 0;
    min-height: calc(56px + env(safe-area-inset-top));
    background: var(--color-bg-secondary);
    border-bottom: 1px solid var(--color-border);
  }

  .zurueck {
    width: 44px;
    height: 44px;
    border: none;
    background: none;
    color: var(--color-text-primary);
    font-size: 1.125rem;
  }

  .kopf-titel {
    flex: 1;
    min-width: 0;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .inhalt {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: clip;
    padding: 1rem max(1rem, calc((100% - var(--lesbreite)) / 2)) 2rem;
  }

  .meldung {
    color: var(--color-error);
  }

  .oben {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
  }

  .umschlag {
    flex-shrink: 0;
    width: 110px;
    height: 160px;
    object-fit: cover;
    border-radius: 6px;
    background: var(--color-bg-tertiary);
  }

  .angaben {
    flex: 1;
    min-width: 0;
  }

  .titel {
    font-size: 1.25rem;
    line-height: 1.3;
    font-weight: 700;
    overflow-wrap: anywhere;
  }

  .autor {
    margin-top: 0.375rem;
    color: var(--color-text-secondary);
  }

  .eckdaten {
    margin-top: 0.5rem;
    font-size: 15px;
    color: var(--color-text-muted);
  }

  .lesen,
  .nebenknopf {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.625rem;
    width: 100%;
    height: 52px;
    margin-top: 1rem;
    border-radius: 12px;
    font-weight: 600;
  }

  .lesen {
    margin-top: 1.25rem;
    background: var(--color-accent);
    color: #fff;
    font-size: 1.125rem;
  }

  .nebenknopf {
    height: 48px;
    margin-top: 0.625rem;
    border: 1px solid var(--color-border);
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
  }

  .abschnitt {
    margin: 1.5rem 0 0.5rem;
    font-size: 15px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-secondary);
  }

  .beschreibung {
    line-height: 1.55;
    white-space: pre-line;
    overflow-wrap: anywhere;
  }
</style>
