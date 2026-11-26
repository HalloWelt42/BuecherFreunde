<!-- Private Notizen zu einer Stelle im Buch (ab Stufe Schule): eine Liste und ein Feld. Gespeichert wie im normalen Leser
     (POST /api/books/{id}/notes mit page_reference); der Server hält sie je Profil, die Eltern sehen sie nicht. Löschen erst nach
     einer Rückfrage, die den Wortlaut zeigt. Klein: groß und einfach als Dialog über dem Blatt. seitlich (Gestaltung groß, BF-88):
     rechts neben dem Blatt, nichts liegt darüber; nur die Liste rollt. -->
<script lang="ts">
  import { aktualisiereNotiz, erstelleNotiz, loescheNotiz, notizenFuerBuch } from "../../lib/api/notes";
  import type { Notiz } from "../../lib/typen";

  let { buch, ort, seitlich = false, onschliessen }: { buch: number; ort: string; seitlich?: boolean; onschliessen: () => void } = $props();

  let alle = $state.raw<Notiz[]>([]);
  let text = $state("");
  let bearbeitet = $state<Notiz | null>(null);
  let weg = $state<Notiz | null>(null);
  let fehler = $state("");
  let hier = $derived(alle.filter((n) => String(n.page_reference ?? "") === ort));

  $effect(() => {
    notizenFuerBuch(buch).then((n) => (alle = n)).catch((e) => (fehler = e instanceof Error ? e.message : String(e)));
  });

  async function speichere() {
    const inhalt = text.trim();
    if (!inhalt) return;
    fehler = "";
    try {
      if (bearbeitet) {
        const neu = await aktualisiereNotiz(bearbeitet.id, { content: inhalt });
        alle = alle.map((n) => (n.id === neu.id ? neu : n));
      } else alle = [...alle, await erstelleNotiz(buch, { content: inhalt, page_reference: ort })];
      text = "";
      bearbeitet = null;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  async function loesche(n: Notiz) {
    fehler = "";
    try {
      await loescheNotiz(n.id);
      alle = alle.filter((x) => x.id !== n.id);
      weg = null;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  const aendere = (n: Notiz) => ((bearbeitet = n), (text = n.content));
</script>

<!-- Neben dem Blatt nimmt Escape erst die Rückfrage zurück, dann schließt es -->
<svelte:window onkeydown={(e) => e.key === "Escape" && (seitlich && weg ? (weg = null) : onschliessen())} />

{#if seitlich}
  <aside class="g-notizen platte" class:fragt={!!weg} aria-label="Notizen">
    <div class="g-notizkopf">
      <i class="fa-solid fa-note-sticky" aria-hidden="true"></i><b>Notizen, {ort}</b>
      <button class="knopf nur frei" type="button" aria-label="Schließen" title="Schließen" onclick={onschliessen}><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>
    </div>
    {#if weg}
      <span>Diese Notiz löschen? Sie ist danach weg.</span>
      <blockquote class="g-notiz"><span>{weg.content}</span><span></span></blockquote>
      <div class="g-zwei">
        <button class="knopf" type="button" onclick={() => (weg = null)}><i class="fa-solid fa-arrow-left" aria-hidden="true"></i><span>Behalten</span></button>
        <button class="knopf" type="button" onclick={() => void loesche(weg!)}><i class="fa-solid fa-trash" aria-hidden="true"></i><span>Löschen</span></button>
      </div>
    {:else}
      <div class="rollen g-notizliste">
        {#each hier as n (n.id)}
          <div class="g-notiz">
            <span>{n.content}</span>
            <span>
              <button class="knopf nur frei" type="button" aria-label="Ändern" title="Ändern" aria-pressed={bearbeitet?.id === n.id} onclick={() => aendere(n)}><i class="fa-solid fa-pen" aria-hidden="true"></i></button>
              <button class="knopf nur frei" type="button" aria-label="Löschen" title="Löschen" onclick={() => (weg = n)}><i class="fa-solid fa-trash" aria-hidden="true"></i></button>
            </span>
          </div>
        {/each}
      </div>
      <textarea class="eingabe" bind:value={text} rows="3" placeholder="Was ich mir merken will" aria-label="Notiz"></textarea>
      <button class="knopf haupt" type="button" disabled={!text.trim()} onclick={() => void speichere()}><i class="fa-solid fa-check" aria-hidden="true"></i><span>{bearbeitet ? "Ändern" : "Speichern"}</span></button>
    {/if}
    {#if fehler}<p class="schlecht" role="alert">{fehler}</p>{/if}
  </aside>
{:else}
  <div class="k-dialog" role="dialog" aria-modal="true" aria-label="Notizen">
    <div>
      <div class="k-dialogkopf">
        <i class="fa-solid fa-note-sticky" aria-hidden="true"></i><span>Notizen, {ort}</span>
        <button class="k-schloss" type="button" aria-label="Schließen" onclick={onschliessen}><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>
      </div>
      {#if weg}
        <p>Diese Notiz löschen? Sie ist danach weg.</p>
        <blockquote class="k-notiz">{weg.content}</blockquote>
        <div class="k-wahl">
          <button class="k-taste quer" type="button" onclick={() => (weg = null)}><i class="fa-solid fa-arrow-left" aria-hidden="true"></i>Behalten</button>
          <button class="k-taste quer" type="button" onclick={() => void loesche(weg!)}><i class="fa-solid fa-trash" aria-hidden="true"></i>Löschen</button>
        </div>
      {:else}
        {#each hier as n (n.id)}
          <div class="k-notiz">
            <span>{n.content}</span>
            <span class="k-wahl">
              <button class="k-taste" type="button" aria-label="Ändern" onclick={() => aendere(n)}><i class="fa-solid fa-pen" aria-hidden="true"></i></button>
              <button class="k-taste" type="button" aria-label="Löschen" onclick={() => (weg = n)}><i class="fa-solid fa-trash" aria-hidden="true"></i></button>
            </span>
          </div>
        {/each}
        <textarea class="k-notizfeld" bind:value={text} rows="4" placeholder="Was ich mir merken will" aria-label="Notiz"></textarea>
        <button class="k-taste quer haupt" type="button" disabled={!text.trim()} onclick={() => void speichere()}><i class="fa-solid fa-check" aria-hidden="true"></i>{bearbeitet ? "Ändern" : "Speichern"}</button>
      {/if}
      {#if fehler}<p class="k-fehler">{fehler}</p>{/if}
    </div>
  </div>
{/if}
