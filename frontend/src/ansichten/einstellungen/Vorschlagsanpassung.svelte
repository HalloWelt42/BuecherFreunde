<script lang="ts">
  // Bücher anpassen (BF-66): Bücher eines Vorschlags abwählen und den Namen ändern, dann anlegen
  import { untrack } from "svelte";
  import { vonGesamt } from "../../lib/format";
  import Buchzeile from "../../lib/teile/Buchzeile.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { Sammlungsvorschlag } from "../../lib/typen";
  import { bandText } from "../sammlung/angaben";
  import { vorschlaege } from "./sammlungsvorschlaege.svelte";

  let { vorschlag, onschliessen }: { vorschlag: Sammlungsvorschlag; onschliessen: () => void } = $props();

  let name = $state(untrack(() => vorschlag.name));
  let gewaehlt = $state<ReadonlySet<number>>(untrack(() => new Set(vorschlag.buecher.map((b) => b.id))));
  let laeuft = $state(false);
  let ids = $derived(vorschlag.buecher.filter((b) => gewaehlt.has(b.id)).map((b) => b.id));

  function waehle(id: number, an: boolean) {
    const neu = new Set(gewaehlt);
    if (an) neu.add(id);
    else neu.delete(id);
    gewaehlt = neu;
  }

  async function lege(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    const ok = await vorschlaege.anlegen(vorschlag, { name: name.trim(), book_ids: ids });
    laeuft = false;
    if (ok) onschliessen();
  }
</script>

<Fenster titel="Bücher anpassen" breite="36rem" {onschliessen}>
  <form id="vorschlagsanpassung" class="formular" onsubmit={lege}>
    <label class="feld">Name<input class="eingabe" data-fokus bind:value={name} required maxlength="120" /></label>
    <div class="feld">
      <span>Bücher <span class="leise zahl">{vonGesamt(ids.length, vorschlag.buecher.length)}</span></span>
      <div class="zuordnungszeilen">
        {#each vorschlag.buecher as buch (buch.id)}
          <Buchzeile {buch} band={bandText(buch.band)} an={gewaehlt.has(buch.id)} onwahl={(an) => waehle(buch.id, an)} />
        {/each}
      </div>
    </div>
  </form>
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <button class="knopf haupt" type="submit" form="vorschlagsanpassung" disabled={laeuft || !name.trim() || !ids.length}><Symbol name={laeuft ? "circle-notch" : "check"} dreht={laeuft} /><span>Anlegen</span></button>
    </span>
  {/snippet}
</Fenster>
