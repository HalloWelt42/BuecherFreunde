<script lang="ts">
  import SvelteMarkdown, { buildUnsupportedHTML } from "@humanspeak/svelte-markdown";
  import { holeAutor, reichereAutorAn, type Anreicherung, type Autoreneinzeln } from "../../lib/api/authors";
  import { farbenAusBild } from "../../lib/farben";
  import { rollstand } from "../../lib/rollstand";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import AutorBearbeiten from "./AutorBearbeiten.svelte";
  import Autorkopf from "./Autorkopf.svelte";
  import AutorVergleich from "./AutorVergleich.svelte";

  let { params }: { params: Record<string, string> } = $props();

  let id = $derived(Number(params.id));
  let autor = $state<Autoreneinzeln | null>(null);
  let fehler = $state("");
  let bearbeitet = $state(false);
  let sucht = $state(false);
  let suchgrund = $state("");
  let antwort = $state<Anreicherung | null>(null);

  // Nur Markdown, kein HTML aus fremden Texten
  const darsteller = { html: buildUnsupportedHTML() };

  $effect(() => {
    void lade(id);
    return () => (wahl.geliehen = null);
  });

  // Ohne Foto leiht das erste Buch sein Licht, sobald sein Umschlag geladen ist
  $effect(() => {
    if (autor && !autor.photo_path && autor.books[0]) wahl.geliehen = wahl.farbenVon(autor.books[0].id) ?? null;
  });

  async function lade(nummer: number) {
    fehler = "";
    try {
      const neu = await holeAutor(nummer);
      if (nummer === id) autor = neu;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  async function sucheImLexikon() {
    sucht = true;
    suchgrund = "";
    antwort = null;
    try {
      const a = await reichereAutorAn(id);
      if (a.angereichert) antwort = a;
      else suchgrund = a.grund || "Kein passender Eintrag gefunden";
    } catch (e) {
      suchgrund = e instanceof Error ? e.message : String(e);
    } finally {
      sucht = false;
    }
  }

  async function uebernommen() {
    antwort = null;
    await lade(id);
  }
</script>

<div class="werkzeug">
  <Knopf text="Autoren" symbol="arrow-left" klein href="/authors" />
  {#if autor}
    <span class="reihe schiebt">
      <Knopf text="Lexikon" symbol="book-atlas" klein laeuft={sucht} titel="In Normdatei und Lexikon nachsehen, danach vergleichen" onclick={() => void sucheImLexikon()} />
      <Knopf text="Bearbeiten" symbol="pen" klein gedrueckt={bearbeitet} onclick={() => (bearbeitet = !bearbeitet)} />
    </span>
  {/if}
</div>

<div class="inhalt rollen" use:rollstand={`/author/${id}`}>
  {#if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade(id)} />
  {:else if !autor}
    <Zustand art="laedt" text="Autor wird geladen" />
  {:else}
    <Autorkopf {autor} onbild={(bild) => (wahl.geliehen = farbenAusBild(bild))} />

    {#if suchgrund}<div class="platte karte" role="status"><p class="marke-text warn"><Symbol name="circle-info" />{suchgrund}</p></div>{/if}
    {#if bearbeitet}<AutorBearbeiten {autor} onfertig={(neu) => { autor = neu; bearbeitet = false; }} onabbruch={() => (bearbeitet = false)} />{/if}
    {#if antwort}<AutorVergleich {autor} {antwort} onfertig={() => void uebernommen()} onverwerfen={() => (antwort = null)} />{/if}

    <Karte titel="Bücher" symbol="book" breit>
      {#if autor.books.length}
        <div class="regal nur">
          {#each autor.books as buch (buch.id)}
            <div class="band"><a class="flaeche" href="/book/{buch.id}" title={[buch.title, buch.year, buch.file_format.toUpperCase()].filter(Boolean).join(", ")} aria-label={buch.title}><span class="stand"><Umschlag buch={{ ...buch, author: autor.name }} /></span><span class="boden"></span></a></div>
          {/each}
        </div>
      {:else}<p class="leise">Keinem Buch zugeordnet.</p>{/if}
    </Karte>

    <div class="raster">
      <Karte titel="Biografie" symbol="feather" breit={!autor.werke.length}>
        {#if autor.biography}
          <div class="biografie"><SvelteMarkdown source={autor.biography} renderers={darsteller} /></div>
        {:else}<p class="leise">Noch keine Biografie. Oben unter Bearbeiten schreiben oder aus dem Lexikon holen.</p>{/if}
      </Karte>
      {#if autor.werke.length}
        <Karte titel="Werke" symbol="list-ul">
          <ul class="werkliste">
            {#each autor.werke as werk (werk.id)}
              <li>
                {#if werk.book_id}<a href="/book/{werk.book_id}">{werk.titel}</a>{:else}<span>{werk.titel}</span>{/if}
                {#if werk.book_id}<span class="marke-text gut"><Symbol name="check" />im Bestand</span>{/if}
                {#if werk.wikidata_id}<a class="leise" href="https://www.wikidata.org/wiki/{werk.wikidata_id}" target="_blank" rel="noopener">{werk.wikidata_id}</a>{/if}
              </li>
            {/each}
          </ul>
        </Karte>
      {/if}
    </div>
  {/if}
</div>
