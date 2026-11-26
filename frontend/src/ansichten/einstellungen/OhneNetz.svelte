<script lang="ts">
  // Ohne Netz lesen: zuletzt geöffnete Bücher auf diesem Gerät behalten, ausdrücklich gewählt, mit Platz und Leeren
  import { anzahl, groesse } from "../../lib/format";
  import { lesestoff } from "../../lib/stand/lesestoff.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  let s = $derived(lesestoff.stand);
  let arbeit = $state(false);
  /** Neu gezeichnet, wenn ein Häkchen gegen den Stand gesetzt wurde (Rückfrage abgebrochen): es zeigt, was gilt */
  let zug = $state(0);

  /** Folgen nennen, erst ein Ja nimmt die Bücher vom Gerät */
  async function bestaetigt(ja: string): Promise<boolean> {
    if (!s?.buecher.length) return true;
    return frage({
      titel: "Bücher von diesem Gerät nehmen?",
      text: `${anzahl(s.buecher.length, "Buch", "Bücher")}, zusammen ${groesse(s.bytes)}. Sie bleiben in der Bibliothek; nur die Kopie auf diesem Gerät geht, ohne Netz gehen sie dann nicht mehr auf.`,
      folgen: s.buecher.map((b) => `${b.titel || `Buch ${b.id}`}, ${groesse(b.bytes)}`),
      ja,
      symbol: "trash",
    });
  }

  async function tun(was: () => Promise<void>, gut: string) {
    arbeit = true;
    try {
      await was();
      if (!lesestoff.stand) melde.schlecht(new Error("Der Dienst im Hintergrund antwortet nicht"));
      else melde.gut(gut);
    } finally {
      arbeit = false;
    }
  }

  async function schalte(an: boolean) {
    if (!an && !(await bestaetigt("Ausschalten und vom Gerät nehmen"))) {
      zug += 1;
      return;
    }
    await tun(() => lesestoff.schalte(an), an ? "Zuletzt geöffnete Bücher bleiben auf diesem Gerät" : "Ausgeschaltet, nichts mehr auf diesem Gerät");
  }

  async function leere() {
    if (await bestaetigt("Vom Gerät nehmen")) await tun(() => lesestoff.leere(), "Vom Gerät genommen");
  }
</script>

{#if s}
  {#key zug}<Haekchen text="Zuletzt geöffnete Bücher auf dem Gerät behalten" an={s.an} gesperrt={arbeit} onwahl={(an) => void schalte(an)} />{/key}
  <p class="leise zahl">Höchstens {anzahl(s.grenzen.buecher, "Buch", "Bücher")}, zusammen {groesse(s.grenzen.bytes)}. {s.buecher.length ? `Belegt: ${anzahl(s.buecher.length, "Buch", "Bücher")}, ${groesse(s.bytes)}.` : "Belegt: nichts."}</p>
  {#if s.buecher.length}
    <ul class="gemerkt">
      {#each s.buecher as b (b.id)}<li><a href="/book/{b.id}">{b.titel || `Buch ${b.id}`}</a><span class="leise zahl">{groesse(b.bytes)}</span></li>{/each}
    </ul>
    <div class="reihe"><Knopf text="Leeren" symbol="trash" klein gesperrt={arbeit} onclick={() => void leere()} /></div>
  {/if}
{/if}

<style>
  .gemerkt {
    display: grid;
  }
  li {
    display: flex;
    gap: 0.75rem;
    justify-content: space-between;
    padding: 0.25rem 0;
    border-top: 1px solid var(--linie);
    overflow-wrap: anywhere;
  }
</style>
