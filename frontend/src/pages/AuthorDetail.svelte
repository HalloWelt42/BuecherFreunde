<script>
  import { holeAutor, autorenFotoUrl, reichereAutorAn, uebernehmAutorenDaten, aktualisiereAutor } from "../lib/api/authors.js";
  import { coverUrl } from "../lib/api/books.js";
  import { getToken } from "../lib/api/client.js";
  import { ui } from "../lib/stores/ui.svelte.js";
  import SvelteMarkdown from "@humanspeak/svelte-markdown";

  let { params } = $props();

  let autor = $state(null);
  let laden = $state(true);
  let fehler = $state(null);
  let fotoError = $state(false);

  // Edit-Mode
  let editMode = $state(false);
  let editData = $state({});
  let editSpeichern = $state(false);

  // Anreicherung
  let enrichLaden = $state(false);
  let enrichVorschlag = $state(null);
  let enrichAktuell = $state(null);
  let enrichFehler = $state("");
  let enrichAuswahl = $state({});
  let enrichBuecherImSystem = $state([]);

  const vergleichsFelder = [
    { key: "name", label: "Name" },
    { key: "biography", label: "Biografie" },
    { key: "beschreibung", label: "Beschreibung" },
    { key: "birth_year", label: "Geburtsjahr" },
    { key: "death_year", label: "Todesjahr" },
    { key: "nationality", label: "Nationalität" },
    { key: "wikidata_id", label: "Wikidata-ID" },
    { key: "wikipedia_url", label: "Wikipedia" },
  ];

  let hatAuswahl = $derived(
    Object.values(enrichAuswahl).some(v => v)
  );

  $effect(() => {
    ladeAutor(Number(params.id));
  });

  async function ladeAutor(id) {
    laden = true;
    fehler = null;
    fotoError = false;
    try {
      autor = await holeAutor(id);
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  function startEdit() {
    editData = {
      name: autor.name || "",
      biography: autor.biography || "",
      birth_year: autor.birth_year || "",
      death_year: autor.death_year || "",
      nationality: autor.nationality || "",
      website: autor.website || "",
    };
    editMode = true;
  }

  function cancelEdit() {
    editMode = false;
    editData = {};
  }

  async function saveEdit() {
    if (editSpeichern) return;
    editSpeichern = true;
    try {
      const daten = {};
      for (const [key, val] of Object.entries(editData)) {
        if (key === "birth_year" || key === "death_year") {
          const num = parseInt(val) || null;
          if (num !== (autor[key] || null)) daten[key] = num;
        } else {
          if (val !== (autor[key] || "")) daten[key] = val;
        }
      }
      if (Object.keys(daten).length > 0) {
        await aktualisiereAutor(autor.id, daten);
        await ladeAutor(autor.id);
      }
      editMode = false;
      editData = {};
    } catch (e) {
      fehler = e.message || "Fehler beim Speichern";
    } finally {
      editSpeichern = false;
    }
  }

  async function anreichern() {
    if (enrichLaden || !autor) return;
    enrichLaden = true;
    enrichFehler = "";
    enrichVorschlag = null;
    enrichAktuell = null;
    enrichAuswahl = {};

    try {
      const result = await reichereAutorAn(autor.id);
      if (!result.angereichert) {
        enrichFehler = result.grund || "Keine Daten gefunden";
        return;
      }
      enrichVorschlag = result.vorschlag;
      enrichAktuell = result.aktuell;
      // Auto-Auswahl für geänderte Felder
      for (const feld of vergleichsFelder) {
        const neu = enrichVorschlag[feld.key] ?? "";
        const alt = enrichAktuell[feld.key] ?? "";
        if (neu && String(neu) !== String(alt)) {
          enrichAuswahl[feld.key] = true;
        }
      }
      if (enrichVorschlag.photo_url) enrichAuswahl.photo = true;
      enrichBuecherImSystem = result.buecher_im_system || [];
    } catch (e) {
      enrichFehler = e.message || "Fehler bei der Suche";
    } finally {
      enrichLaden = false;
    }
  }

  async function datenUebernehmen() {
    if (!enrichVorschlag || enrichLaden || !hatAuswahl) return;
    enrichLaden = true;
    enrichFehler = "";
    try {
      const payload = {};
      for (const feld of vergleichsFelder) {
        if (enrichAuswahl[feld.key]) {
          payload[feld.key] = enrichVorschlag[feld.key];
        }
      }
      if (enrichAuswahl.photo && enrichVorschlag.photo_url) {
        payload.photo_url = enrichVorschlag.photo_url;
      }
      // Werke und Scores mitsenden
      if (enrichVorschlag.werke?.length > 0) {
        payload.werke = enrichVorschlag.werke;
      }
      if (enrichVorschlag.beschreibung) {
        payload.beschreibung = enrichVorschlag.beschreibung;
      }
      if (enrichVorschlag.score) {
        payload.score = enrichVorschlag.score;
      }
      if (enrichVorschlag.konfidenz) {
        payload.konfidenz = enrichVorschlag.konfidenz;
      }
      if (enrichVorschlag.quelle) {
        payload.quelle = enrichVorschlag.quelle;
      }
      await uebernehmAutorenDaten(autor.id, payload);
      await ladeAutor(autor.id);
      enrichVorschlag = null;
      enrichAktuell = null;
      enrichAuswahl = {};
      fotoError = false;
    } catch (e) {
      enrichFehler = e.message || "Fehler beim Übernehmen";
    } finally {
      enrichLaden = false;
    }
  }

  function konfidenzInfo(stufe, score) {
    const erklaerung = [
      `Konfidenz: ${stufe} (${score || 0} Punkte)`,
      "",
      "Scoring:",
      "+10  Beruf: Schriftsteller/Autor",
      "+8   Exakter Namens-Match",
      "+5   Deutscher Wikipedia-Artikel",
      "+1-10 Sitelinks (Bekanntheit)",
      "+15  Werke stimmen mit Bibliothek überein",
      "+30  ISBN-Übereinstimmung",
      "",
      "Konfidenz-Stufen:",
      "Hoch: ab 15 Pkt. oder Buch/ISBN-Treffer",
      "Mittel: 8-14 Pkt.",
      "Niedrig: unter 8 Pkt.",
    ];
    return erklaerung.join("\n");
  }

  function verwerfen() {
    enrichVorschlag = null;
    enrichAktuell = null;
    enrichAuswahl = {};
    enrichFehler = "";
  }
</script>

{#if autor}
  {#if !fotoError && autor.photo_path}
    <div class="bg-cover-blur" style="background-image: url({autorenFotoUrl(autor.id, 'normal')})"></div>
  {:else}
    <div class="bg-cover-blur bg-cover-default" style="background-image: url(/api/config/design/hintergrund/{ui.bgAktuellerDateiname || ''}?token={encodeURIComponent(getToken())})"></div>
  {/if}
  <div class="bg-cover-overlay"></div>
{/if}

<div class="autor-detail">
  <div class="page-header">
    <a href="/authors" class="back-link"><i class="fa-solid fa-arrow-left"></i> Autoren</a>
  </div>

  {#if laden}
    <p class="status-text">Autor wird geladen...</p>
  {:else if fehler}
    <p class="status-text error">Fehler: {fehler}</p>
  {:else if autor}
    <!-- Zwei-Spalten-Layout: Links Steckbrief, Rechts Biografie -->
    <div class="zwei-spalten">
      <!-- LINKE SPALTE: Foto, Name, Meta, Werke, Bücher -->
      <div class="spalte-links">
        {#if !fotoError && autor.photo_path}
          <img
            src={autorenFotoUrl(autor.id, "normal")}
            alt={autor.name}
            class="autor-foto"
            onerror={() => (fotoError = true)}
          />
        {:else}
          <div class="foto-placeholder">
            <i class="fa-solid fa-user"></i>
          </div>
        {/if}

        <h1 class="autor-name">{autor.name}</h1>
        {#if autor.beschreibung}
          <p class="autor-beschreibung">{autor.beschreibung}</p>
        {/if}

        <div class="meta-angaben">
          {#if autor.birth_year || autor.death_year}
            <div class="meta-zeile">
              <i class="fa-solid fa-calendar"></i>
              {autor.birth_year || "?"} - {autor.death_year || ""}
            </div>
          {/if}
          {#if autor.nationality}
            <div class="meta-zeile">
              <i class="fa-solid fa-globe"></i> {autor.nationality}
            </div>
          {/if}
          {#if autor.wikipedia_url}
            <a href={autor.wikipedia_url} target="_blank" rel="noopener" class="meta-zeile link">
              <i class="fa-brands fa-wikipedia-w"></i> Wikipedia
            </a>
          {/if}
          {#if autor.wikidata_id}
            <a href="https://www.wikidata.org/wiki/{autor.wikidata_id}" target="_blank" rel="noopener" class="meta-zeile link">
              <i class="fa-brands fa-wikipedia-w"></i> {autor.wikidata_id}
            </a>
          {/if}
          {#if autor.website}
            <a href={autor.website} target="_blank" rel="noopener" class="meta-zeile link">
              <i class="fa-solid fa-link"></i> Website
            </a>
          {/if}
          {#if autor.konfidenz}
            <div class="meta-zeile konfidenz-{autor.konfidenz}" title={konfidenzInfo(autor.konfidenz, autor.score)}>
              <i class="fa-solid fa-shield-halved"></i>
              {autor.konfidenz}{#if autor.score} ({autor.score} Pkt.){/if}
            </div>
          {/if}
        </div>

        <div class="action-row">
          {#if !editMode}
            <button class="action-btn" onclick={startEdit} title="Autor bearbeiten">
              <i class="fa-solid fa-pen"></i>
            </button>
          {/if}
          <button
            class="action-btn meta-btn"
            class:loading={enrichLaden}
            onclick={anreichern}
            disabled={enrichLaden}
            title="Daten bei Wikipedia/Wikidata suchen"
          >
            {#if enrichLaden}
              <i class="fa-solid fa-spinner fa-spin"></i>
            {:else}
              <i class="fa-brands fa-wikipedia-w"></i>
            {/if}
          </button>
        </div>

        <!-- Werke aus Wikidata -->
        {#if autor.werke && autor.werke.length > 0 && !editMode}
          <div class="links-section">
            <h2 class="section-title">Werke ({autor.werke.length})</h2>
            <div class="werke-detail-liste">
              {#each autor.werke as werk (werk.id)}
                <div class="werk-detail-eintrag" class:im-system={!!werk.book_id}>
                  {#if werk.book_id}
                    <a href="/book/{werk.book_id}" class="werk-detail-link">{werk.titel}</a>
                  {:else}
                    <span class="werk-detail-name">{werk.titel}</span>
                  {/if}
                  {#if werk.wikidata_id}
                    <a href="https://www.wikidata.org/wiki/{werk.wikidata_id}" target="_blank" rel="noopener" class="werk-wikidata">
                      {werk.wikidata_id}
                    </a>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Bücher -->
        {#if autor.books && autor.books.length > 0}
          <div class="links-section">
            <h2 class="section-title">Bücher ({autor.books.length})</h2>
            <div class="buecher-liste">
              {#each autor.books as buch (buch.id)}
                <a href="/book/{buch.id}" class="buch-eintrag">
                  <div class="buch-cover-wrap">
                    {#if buch.cover_path}
                      <img src={coverUrl(buch.id, buch.updated_at)} alt={buch.title} class="buch-cover" loading="lazy" />
                    {:else}
                      <div class="buch-cover-placeholder">
                        <span>{(buch.file_format || "?").toUpperCase()}</span>
                      </div>
                    {/if}
                  </div>
                  <div class="buch-info">
                    <span class="buch-titel">{buch.title}</span>
                    <span class="buch-format">{(buch.file_format || "").toUpperCase()}</span>
                  </div>
                </a>
              {/each}
            </div>
          </div>
        {:else if !laden}
          <div class="links-section">
            <h2 class="section-title">Bücher</h2>
            <p class="leer-text">Keine Bücher zugeordnet</p>
          </div>
        {/if}
      </div>

      <!-- RECHTE SPALTE: Biografie (scrollbar, bold, gross) -->
      <div class="spalte-rechts">
        {#if editMode}
          <div class="edit-form">
            <div class="edit-field">
              <label class="edit-label" for="edit-autor-name">Name</label>
              <input id="edit-autor-name" type="text" class="edit-input" bind:value={editData.name} />
            </div>
            <div class="edit-row">
              <div class="edit-field">
                <label class="edit-label" for="edit-autor-geburt">Geburtsjahr</label>
                <input id="edit-autor-geburt" type="number" class="edit-input" bind:value={editData.birth_year} />
              </div>
              <div class="edit-field">
                <label class="edit-label" for="edit-autor-tod">Todesjahr</label>
                <input id="edit-autor-tod" type="number" class="edit-input" bind:value={editData.death_year} />
              </div>
              <div class="edit-field">
                <label class="edit-label" for="edit-autor-nationalitaet">Nationalität</label>
                <input id="edit-autor-nationalitaet" type="text" class="edit-input" bind:value={editData.nationality} />
              </div>
            </div>
            <div class="edit-field">
              <label class="edit-label" for="edit-autor-website">Website</label>
              <input id="edit-autor-website" type="text" class="edit-input" bind:value={editData.website} />
            </div>
            <div class="edit-field">
              <label class="edit-label" for="edit-autor-bio">Biografie (Markdown)</label>
              <textarea id="edit-autor-bio" class="edit-input edit-textarea" bind:value={editData.biography} rows="20"></textarea>
            </div>
            <div class="edit-aktionen">
              <button class="btn btn-primary btn-sm" onclick={saveEdit} disabled={editSpeichern} title="Änderungen speichern">
                {#if editSpeichern}<i class="fa-solid fa-spinner fa-spin"></i>{/if}
                Speichern
              </button>
              <button class="btn btn-secondary btn-sm" onclick={cancelEdit} title="Bearbeitung abbrechen">Abbrechen</button>
            </div>
          </div>
        {:else if autor.biography}
          <div class="bio-content markdown">
            <SvelteMarkdown source={autor.biography} />
          </div>
        {:else}
          <p class="leer-text">Noch keine Biografie vorhanden. Klicke auf <i class="fa-brands fa-wikipedia-w"></i> um Daten von Wikipedia zu laden.</p>
        {/if}
      </div>
    </div>

    <!-- Enrichment-Dialog (volle Breite unter dem Layout) -->
    {#if enrichFehler}
      <div class="meta-status meta-fehler">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>{enrichFehler}</span>
      </div>
    {/if}

    {#if enrichVorschlag && enrichAktuell}
      <div class="meta-vergleich">
        <div class="enrich-header">
          <h2 class="section-title">Wikipedia-Daten</h2>
          <span class="konfidenz-badge konfidenz-{enrichVorschlag.konfidenz || 'niedrig'}" title={konfidenzInfo(enrichVorschlag.konfidenz, enrichVorschlag.score)}>
            {enrichVorschlag.konfidenz || "niedrig"}
            {#if enrichVorschlag.score}
              <span class="konfidenz-score">({enrichVorschlag.score} Pkt.)</span>
            {/if}
          </span>
        </div>
        <div class="vergleich-tabelle">
          <div class="vergleich-kopf">
            <span class="vergleich-check"></span>
            <span class="vergleich-label"></span>
            <span class="vergleich-spalte">Aktuell</span>
            <span class="vergleich-spalte">Vorschlag</span>
          </div>
          {#each vergleichsFelder as feld}
            {@const alt = enrichAktuell[feld.key] ?? ""}
            {@const neu = enrichVorschlag[feld.key] ?? ""}
            {#if neu || alt}
              {@const geaendert = String(neu) !== String(alt) && !!neu}
              <label class="vergleich-zeile" class:geaendert={geaendert && enrichAuswahl[feld.key]}>
                <span class="vergleich-check">
                  {#if geaendert}
                    <input type="checkbox" bind:checked={enrichAuswahl[feld.key]} />
                  {/if}
                </span>
                <span class="vergleich-label">{feld.label}</span>
                <span class="vergleich-alt" class:leer={!alt}>
                  {feld.key === "biography" || feld.key === "beschreibung"
                    ? (alt ? `${String(alt).slice(0, 80)}...` : "-")
                    : (alt || "-")}
                </span>
                <span class="vergleich-neu" class:leer={!neu} class:abgewaehlt={geaendert && !enrichAuswahl[feld.key]}>
                  {feld.key === "biography" || feld.key === "beschreibung"
                    ? (neu ? `${String(neu).slice(0, 80)}...` : "-")
                    : (neu || "-")}
                </span>
              </label>
            {/if}
          {/each}

          {#if enrichVorschlag.photo_url}
            <label class="vergleich-zeile" class:geaendert={enrichAuswahl.photo}>
              <span class="vergleich-check">
                <input type="checkbox" bind:checked={enrichAuswahl.photo} />
              </span>
              <span class="vergleich-label">Foto</span>
              <span class="vergleich-alt">
                {#if enrichAktuell.hat_foto}
                  <img src={autorenFotoUrl(autor.id, "thumb")} alt="Aktuelles Foto" class="foto-vorschau" />
                {:else}
                  -
                {/if}
              </span>
              <span class="vergleich-neu" class:abgewaehlt={!enrichAuswahl.photo}>
                <div class="foto-vorschau-wrap">
                  <img src={enrichVorschlag.photo_url} alt="Vorgeschlagenes Foto" class="foto-vorschau" />
                  <img src={enrichVorschlag.photo_url} alt="Vorgeschlagenes Foto" class="foto-gross" />
                </div>
              </span>
            </label>
          {/if}
        </div>

        {#if enrichVorschlag.werke && enrichVorschlag.werke.length > 0}
          <div class="werke-section">
            <h3 class="werke-titel">Literaturliste aus Wikidata ({enrichVorschlag.werke.length})</h3>
            <div class="werke-liste">
              {#each enrichVorschlag.werke as werk}
                {@const imSystem = enrichBuecherImSystem.some(b =>
                  b.title.toLowerCase().includes(werk.titel.toLowerCase()) ||
                  werk.titel.toLowerCase().includes(b.title.toLowerCase())
                )}
                <div class="werk-eintrag" class:im-system={imSystem}>
                  <span class="werk-name">{werk.titel}</span>
                  {#if imSystem}
                    <span class="werk-status vorhanden"><i class="fa-solid fa-check"></i> im System</span>
                  {:else}
                    <span class="werk-status fehlend"><i class="fa-solid fa-minus"></i></span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <div class="meta-aktionen">
          <button class="btn btn-primary btn-sm" onclick={datenUebernehmen} disabled={enrichLaden || !hatAuswahl} title="Ausgewählte Daten übernehmen">
            {#if enrichLaden}<i class="fa-solid fa-spinner fa-spin"></i>{/if}
            Ausgewählte übernehmen
          </button>
          <button class="btn btn-secondary btn-sm" onclick={verwerfen} title="Vorschläge verwerfen">
            Verwerfen
          </button>
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  /* Blur-Hintergrund */
  .bg-cover-blur {
    position: fixed;
    inset: 0;
    z-index: 0;
    background-size: cover;
    background-position: center;
    filter: blur(var(--cover-bg-blur)) saturate(var(--cover-bg-saturate));
    transform: scale(var(--cover-bg-scale));
    pointer-events: none;
  }

  .bg-cover-default {
    background-image: var(--cover-bg-default, linear-gradient(135deg, #1a1a2e 0%, #16213e 30%, #0f3460 60%, #533483 100%));
  }

  :global(:root:not(.dark)) .bg-cover-default {
    background-image: var(--cover-bg-default, linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%));
  }

  .bg-cover-overlay {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background: var(--cover-bg-overlay);
  }

  :global(.grid-main:has(.autor-detail)) {
    background: transparent !important;
  }

  /* Layout */
  .autor-detail {
    position: relative;
    z-index: 1;
    width: 100%;
  }

  .page-header {
    margin-bottom: 1rem;
  }

  .back-link {
    color: var(--color-accent);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .status-text {
    color: var(--color-text-muted);
    padding: 2rem 0;
  }

  .status-text.error {
    color: var(--color-error);
  }

  /* Zwei-Spalten: Goldener Schnitt ~38% / ~62% */
  .zwei-spalten {
    display: grid;
    grid-template-columns: 38.2% 1fr;
    gap: 2rem;
    align-items: start;
  }

  /* Linke Spalte: Steckbrief */
  .spalte-links {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    padding: 1rem;
  }

  .autor-foto {
    width: 100%;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .foto-placeholder {
    aspect-ratio: 3 / 4;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--glass-bg-btn-alt);
    backdrop-filter: blur(var(--glass-blur-btn));
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    font-size: 3rem;
    color: var(--color-text-muted);
    opacity: 0.4;
  }

  .autor-name {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
    margin: 0;
  }

  .autor-beschreibung {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    margin: 0;
    font-style: italic;
  }

  /* Meta-Angaben */
  .meta-angaben {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .meta-zeile {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    text-decoration: none;
  }

  .meta-zeile.link {
    color: var(--color-accent);
  }

  .meta-zeile.link:hover {
    text-decoration: underline;
  }

  .meta-zeile.konfidenz-hoch {
    color: #16a34a;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75rem;
  }

  .meta-zeile.konfidenz-mittel {
    color: #d97706;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75rem;
  }

  .meta-zeile.konfidenz-niedrig {
    color: #dc2626;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75rem;
  }

  /* Aktionen */
  .action-row {
    display: flex;
    gap: 0.5rem;
  }

  .action-btn {
    padding: 0.375rem 0.875rem;
    border: 1px solid var(--glass-border-btn);
    border-radius: 6px;
    background: var(--glass-bg-btn-alt);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .action-btn:hover {
    background: var(--glass-bg-btn);
    color: var(--color-text-primary);
  }

  .action-btn.loading {
    opacity: 0.6;
    cursor: wait;
  }

  /* Linke Spalte: Sektionen */
  .links-section {
    border-top: 1px solid var(--glass-border);
    padding-top: 0.75rem;
  }

  .section-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.375rem;
  }

  /* Werke-Liste */
  .werke-detail-liste {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .werk-detail-eintrag {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.25rem 0.375rem;
    border-radius: 4px;
    font-size: 0.75rem;
  }

  .werk-detail-eintrag.im-system {
    background-color: color-mix(in srgb, #22c55e 8%, transparent);
  }

  .werk-detail-link {
    color: var(--color-accent);
    text-decoration: none;
  }

  .werk-detail-link:hover {
    text-decoration: underline;
  }

  .werk-detail-name {
    color: var(--color-text-secondary);
  }

  .werk-wikidata {
    font-size: 0.625rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    text-decoration: none;
  }

  .werk-wikidata:hover {
    color: var(--color-accent);
  }

  /* Bücher-Liste (Flexbox, gleich groß, umbrechen) */
  .buecher-liste {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .buch-eintrag {
    flex: 1 1 80px;
    max-width: 120px;
    display: flex;
    flex-direction: column;
    text-decoration: none;
    border-radius: 4px;
    transition: transform 0.1s;
  }

  .buch-eintrag:hover {
    transform: translateY(-2px);
  }

  .buch-cover-wrap {
    width: 100%;
    aspect-ratio: 3 / 4;
    background: var(--glass-bg-btn-alt);
    border-radius: 4px;
    overflow: hidden;
  }

  .buch-cover {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .buch-cover-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.5625rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }

  .buch-info {
    min-width: 0;
    display: flex;
    flex-direction: column;
    margin-top: 0.25rem;
  }

  .buch-titel {
    font-size: 0.6875rem;
    color: var(--color-text-primary);
    font-weight: 500;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .buch-format {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 0.5rem;
    color: var(--color-text-muted);
  }

  .leer-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    font-style: italic;
  }

  /* Rechte Spalte: Biografie */
  .spalte-rechts {
    max-height: calc(100vh - 6rem);
    overflow-y: auto;
    padding: 1rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 10px;
  }

  .bio-content {
    font-size: 1rem;
    color: var(--color-text-secondary);
    line-height: 1.8;
  }

  .bio-content :global(p) {
    margin: 0 0 0.875rem 0;
  }

  .bio-content :global(h2) {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 1.25rem 0 0.625rem 0;
  }

  .bio-content :global(h3) {
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 1rem 0 0.5rem 0;
  }

  .bio-content :global(a) {
    color: var(--color-accent);
  }

  /* Edit-Form */
  .edit-form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .edit-field {
    display: flex;
    flex-direction: column;
    gap: 0.1875rem;
    flex: 1;
  }

  .edit-label {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
  }

  .edit-input {
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--glass-border);
    border-radius: 4px;
    background: var(--glass-placeholder);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
    font-size: 0.875rem;
    font-family: inherit;
    width: 100%;
  }

  .edit-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .edit-textarea {
    resize: vertical;
    min-height: 6rem;
    font-family: var(--font-mono);
    font-size: 0.8125rem;
  }

  .edit-row {
    display: flex;
    gap: 0.75rem;
  }

  .edit-aktionen {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.625rem 1rem;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    border: none;
    gap: 0.375rem;
    transition: opacity 0.15s;
  }

  .btn:hover { opacity: 0.9; }
  .btn-primary { background-color: var(--color-accent); color: #fff; }
  .btn-secondary { background: var(--glass-bg-btn); backdrop-filter: blur(var(--glass-blur-btn)); color: var(--color-text-primary); border: 1px solid var(--glass-border); }
  .btn-sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; }

  /* Enrichment: Vergleichstabelle */
  .meta-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    margin-top: 1rem;
  }

  .meta-fehler {
    color: var(--color-error);
  }

  .meta-vergleich {
    margin-top: 1rem;
    padding: 0.75rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .enrich-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .konfidenz-badge {
    padding: 0.25rem 0.625rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .konfidenz-score {
    font-weight: 400;
    opacity: 0.8;
    margin-left: 0.25rem;
  }

  .konfidenz-hoch {
    background-color: color-mix(in srgb, #22c55e 15%, transparent);
    color: #16a34a;
  }

  .konfidenz-mittel {
    background-color: color-mix(in srgb, #f59e0b 15%, transparent);
    color: #d97706;
  }

  .konfidenz-niedrig {
    background-color: color-mix(in srgb, #ef4444 15%, transparent);
    color: #dc2626;
  }

  .vergleich-tabelle {
    display: flex;
    flex-direction: column;
  }

  .vergleich-kopf {
    display: grid;
    grid-template-columns: 1.5rem 7rem 1fr 1fr;
    gap: 0.5rem;
    padding: 0.375rem 0;
    border-bottom: 1px solid var(--color-border);
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
  }

  .vergleich-zeile {
    display: grid;
    grid-template-columns: 1.5rem 7rem 1fr 1fr;
    gap: 0.5rem;
    padding: 0.375rem 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
    font-size: 0.8125rem;
    align-items: baseline;
    cursor: default;
  }

  .vergleich-zeile.geaendert {
    background-color: color-mix(in srgb, var(--color-accent) 8%, transparent);
    margin: 0 -0.375rem;
    padding-left: 0.375rem;
    padding-right: 0.375rem;
    border-radius: 4px;
  }

  .vergleich-check {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .vergleich-check input[type="checkbox"] {
    cursor: pointer;
    accent-color: var(--color-accent);
  }

  .vergleich-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .vergleich-alt {
    color: var(--color-text-secondary);
    word-break: break-word;
  }

  .vergleich-alt.leer {
    color: var(--color-text-muted);
    font-style: italic;
  }

  .vergleich-neu {
    color: var(--color-text-primary);
    font-weight: 500;
    word-break: break-word;
  }

  .vergleich-neu.leer,
  .vergleich-neu.abgewaehlt {
    color: var(--color-text-muted);
    font-style: italic;
    font-weight: 400;
    opacity: 0.6;
  }

  .meta-aktionen {
    display: flex;
    gap: 0.5rem;
  }

  /* Foto-Vorschau im Enrichment */
  .foto-vorschau {
    height: 48px;
    border-radius: 3px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
    object-fit: cover;
  }

  .foto-vorschau-wrap {
    position: relative;
    display: inline-block;
  }

  .foto-gross {
    display: none;
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    height: 200px;
    border-radius: 6px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    z-index: 20;
    pointer-events: none;
  }

  .foto-vorschau-wrap:hover .foto-gross {
    display: block;
  }

  /* Werkeliste im Enrichment */
  .werke-section {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }

  .werke-titel {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    margin-bottom: 0.375rem;
  }

  .werke-liste {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-height: 200px;
    overflow-y: auto;
  }

  .werk-eintrag {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.25rem 0.375rem;
    border-radius: 4px;
    font-size: 0.8125rem;
  }

  .werk-eintrag.im-system {
    background-color: color-mix(in srgb, #22c55e 8%, transparent);
  }

  .werk-name {
    color: var(--color-text-primary);
  }

  .werk-status {
    font-size: 0.75rem;
    flex-shrink: 0;
    margin-left: 0.5rem;
  }

  .werk-status.vorhanden {
    color: #16a34a;
  }

  .werk-status.fehlend {
    color: var(--color-text-muted);
    opacity: 0.4;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .zwei-spalten {
      grid-template-columns: 1fr;
    }

    .spalte-rechts {
      max-height: none;
      overflow-y: visible;
      padding: 0;
    }
  }
</style>
