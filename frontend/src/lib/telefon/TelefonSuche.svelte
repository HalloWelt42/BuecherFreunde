<script>
  // Startseite am Telefon: Suchfeld oben, darunter die Treffer; ohne Suchbegriff "Weiterlesen" und der Suchverlauf.
  import { route, navigate } from "../router.svelte.js";
  import { suche } from "../api/search.js";
  import { coverUrl } from "../api/books.js";
  import { zuletztGelesen } from "../api/user-data.js";
  import { parseProgress } from "../utils/reading.js";
  import { ladeVerlauf, merkeBegriff, vergissBegriff } from "../utils/suchverlauf.js";
  import SearchSnippet from "../components/search/SearchSnippet.svelte";

  const SEITENGROESSE = 20;
  const WEITERLESEN_ANZAHL = 8;

  let begriff = $derived(route.params.q || "");
  let eingabe = $state(route.params.q || "");
  let verlauf = $state(ladeVerlauf());

  let treffer = $state([]);
  let gesamt = $state(0);
  let laedt = $state(false);
  let fehler = $state("");

  let weiterlesen = $state([]);

  $effect(() => {
    eingabe = begriff;
    if (begriff) ladeTreffer(begriff, 0);
    else ladeWeiterlesen();
  });

  async function ladeTreffer(q, ab) {
    laedt = true;
    fehler = "";
    try {
      const antwort = await suche(q, { limit: SEITENGROESSE, offset: ab });
      treffer = ab === 0 ? antwort.treffer : [...treffer, ...antwort.treffer];
      gesamt = antwort.gesamt;
    } catch (e) {
      fehler = e.message;
      if (ab === 0) treffer = [];
    } finally {
      laedt = false;
    }
  }

  async function ladeWeiterlesen() {
    try {
      weiterlesen = await zuletztGelesen(WEITERLESEN_ANZAHL);
    } catch {
      weiterlesen = [];
    }
  }

  function suchen(text) {
    const q = text.trim();
    if (!q) return;
    verlauf = merkeBegriff(verlauf, q);
    document.activeElement?.blur();
    navigate(`/search?q=${encodeURIComponent(q)}`);
  }

  function absenden(e) {
    e.preventDefault();
    suchen(eingabe);
  }

  function leeren() {
    eingabe = "";
    if (begriff) navigate("/");
  }
</script>

<header class="kopf">
  <form class="suchfeld" onsubmit={absenden} role="search">
    <i class="fa-solid fa-magnifying-glass lupe"></i>
    <input
      type="search"
      enterkeyhint="search"
      placeholder="Bücher durchsuchen"
      aria-label="Suchbegriff"
      bind:value={eingabe}
    />
    {#if eingabe}
      <button type="button" class="leeren" onclick={leeren} aria-label="Suchbegriff löschen">
        <i class="fa-solid fa-xmark"></i>
      </button>
    {/if}
  </form>
</header>

<main class="inhalt">
  {#if begriff}
    {#if fehler}
      <p class="meldung fehler">Suche fehlgeschlagen: {fehler}</p>
    {:else if !laedt && treffer.length === 0}
      <p class="meldung">Keine Treffer für "{begriff}".</p>
    {:else}
      <p class="zaehler">{gesamt} Treffer</p>
      <ul class="liste">
        {#each treffer as t (t.book_id)}
          <li>
            <a class="eintrag" href="/book/{t.book_id}">
              <img class="umschlag" src={coverUrl(t.book_id)} alt="" loading="lazy"
                onerror={(e) => (e.currentTarget.style.visibility = "hidden")} />
              <div class="text">
                <span class="titel">{t.titel}</span>
                <span class="autor">{t.autor || "Unbekannt"}</span>
                {#if t.snippet}
                  <div class="auszug"><SearchSnippet snippet={t.snippet} /></div>
                {/if}
              </div>
            </a>
          </li>
        {/each}
      </ul>
      {#if treffer.length < gesamt}
        <button class="mehr" disabled={laedt} onclick={() => ladeTreffer(begriff, treffer.length)}>
          {laedt ? "Lädt ..." : `Weitere laden (${gesamt - treffer.length})`}
        </button>
      {:else if laedt}
        <p class="meldung">Suche läuft ...</p>
      {/if}
    {/if}
  {:else}
    {#if weiterlesen.length > 0}
      <h2 class="abschnitt">Weiterlesen</h2>
      <ul class="liste">
        {#each weiterlesen as b (b.id)}
          {@const prozent = parseProgress(b.reading_position, b.page_count)}
          <li>
            <a class="eintrag" href="/book/{b.id}/read">
              <img class="umschlag" src={coverUrl(b.id)} alt="" loading="lazy"
                onerror={(e) => (e.currentTarget.style.visibility = "hidden")} />
              <div class="text">
                <span class="titel">{b.title}</span>
                <span class="autor">{b.author || "Unbekannt"}</span>
                {#if prozent > 0}
                  <span class="fortschritt"><span style="width: {prozent}%"></span></span>
                {/if}
              </div>
              <i class="fa-solid fa-book-open-reader lesen-zeichen"></i>
            </a>
          </li>
        {/each}
      </ul>
    {/if}

    {#if verlauf.length > 0}
      <h2 class="abschnitt">Zuletzt gesucht</h2>
      <ul class="verlauf">
        {#each verlauf.slice(0, 12) as b (b)}
          <li>
            <button class="verlauf-begriff" onclick={() => suchen(b)}>
              <i class="fa-solid fa-clock-rotate-left"></i>
              <span>{b}</span>
            </button>
            <button class="verlauf-weg" onclick={() => (verlauf = vergissBegriff(verlauf, b))} aria-label="{b} aus dem Verlauf entfernen">
              <i class="fa-solid fa-xmark"></i>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</main>

<style>
  .kopf {
    flex-shrink: 0;
    padding: calc(0.75rem + env(safe-area-inset-top)) 1rem 0.75rem;
    background: var(--color-bg-secondary);
    border-bottom: 1px solid var(--color-border);
  }

  .suchfeld {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    height: 48px;
    padding: 0 0.25rem 0 0.875rem;
    border-radius: 12px;
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
  }

  .suchfeld:focus-within {
    border-color: var(--color-accent);
  }

  .lupe {
    color: var(--color-text-muted);
  }

  .suchfeld input {
    flex: 1;
    min-width: 0;
    height: 100%;
    border: none;
    outline: none;
    background: none;
    color: var(--color-text-primary);
    font: inherit;
    font-size: 17px;
  }

  .suchfeld input::-webkit-search-cancel-button {
    display: none;
  }

  .leeren {
    width: 44px;
    height: 44px;
    border: none;
    background: none;
    color: var(--color-text-secondary);
    font-size: 1.125rem;
  }

  .inhalt {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: clip;
    padding: 0.5rem 1rem 2rem;
  }

  .abschnitt {
    margin: 1rem 0 0.5rem;
    font-size: 15px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-secondary);
  }

  .zaehler,
  .meldung {
    margin: 0.75rem 0;
    font-size: 15px;
    color: var(--color-text-secondary);
  }

  .meldung.fehler {
    color: var(--color-error);
  }

  .liste {
    list-style: none;
    display: flex;
    flex-direction: column;
  }

  .eintrag {
    display: flex;
    align-items: flex-start;
    gap: 0.875rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--color-border);
    color: inherit;
  }

  .umschlag {
    flex-shrink: 0;
    width: 56px;
    height: 80px;
    object-fit: cover;
    border-radius: 4px;
    background: var(--color-bg-tertiary);
  }

  .text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .titel {
    font-weight: 600;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    overflow-wrap: anywhere;
  }

  .autor {
    font-size: 15px;
    color: var(--color-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .auszug {
    margin-top: 0.25rem;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    overflow-wrap: anywhere;
  }

  .auszug :global(.snippet) {
    font-size: 15px;
  }

  .fortschritt {
    margin-top: 0.5rem;
    height: 4px;
    border-radius: 2px;
    background: var(--color-bg-tertiary);
    overflow: hidden;
  }

  .fortschritt span {
    display: block;
    height: 100%;
    background: var(--color-accent);
  }

  .lesen-zeichen {
    align-self: center;
    color: var(--color-accent);
    font-size: 1.25rem;
    padding: 0 0.25rem;
  }

  .mehr {
    width: 100%;
    height: 48px;
    margin-top: 1rem;
    border: 1px solid var(--color-border);
    border-radius: 12px;
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
    font: inherit;
  }

  .verlauf {
    list-style: none;
  }

  .verlauf li {
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--color-border);
  }

  .verlauf-begriff {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-height: 48px;
    border: none;
    background: none;
    color: var(--color-text-primary);
    font: inherit;
    text-align: left;
  }

  .verlauf-begriff i {
    color: var(--color-text-muted);
  }

  .verlauf-begriff span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .verlauf-weg {
    width: 44px;
    height: 44px;
    border: none;
    background: none;
    color: var(--color-text-muted);
  }
</style>
