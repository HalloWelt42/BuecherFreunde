<script lang="ts">
  // Das Regal einer Sammlung mit Lücken (BF-75): je Sprache eine Reihe mit eigener Zählung ab 1, fehlende Bände als
  // Platzhalter an ihrer Stelle. Ohne Platzhalter (in der Sammlung abgeschaltet) stehen die Bücher trotzdem je Sprache.
  import type { Luecke, Platz, Reihe } from "../../lib/api/luecken";
  import { reihenzahl } from "../../lib/luecken";
  import Flagge from "../../lib/teile/Flagge.svelte";
  import Menue from "../../lib/teile/Menue.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Band from "../bibliothek/Band.svelte";
  import type { Regalart } from "../bibliothek/ansicht.svelte";
  import { gezogeneDateien } from "../hinzu/dateien";
  import Lueckenfeld from "./Lueckenfeld.svelte";
  import Platzhalter from "./Platzhalter.svelte";
  import type { Lueckenstand } from "./lueckenstand.svelte";

  let { stand, art, reihe = undefined, mitAblegen = false }: { stand: Lueckenstand; art: Regalart; reihe?: string[]; mitAblegen?: boolean } = $props();
  let offen = $state<{ luecke: Luecke; reihe: Reihe; anker: HTMLElement } | null>(null);
  let reihen = $derived(stand.luecken?.reihen ?? []);

  const schluessel = (p: Platz) => (p.art === "buch" ? `b${p.buch_id}` : `l${p.nummer}`);
  const istOffen = (r: Reihe, l: Luecke) => offen?.reihe.sprache === r.sprache && offen.luecke.nummer === l.nummer;

  async function abgelegt(e: DragEvent, l: Luecke) {
    if (e.dataTransfer) await stand.hochladen(await gezogeneDateien(e.dataTransfer), l);
  }
</script>

{#each reihen as r (r.sprache)}
  <section class="sprachreihe">
    <div class="titelzeile">
      {#if r.sprache}<Flagge sprache={r.sprache} groesse="1.25rem" />{/if}
      <h2>{r.name}</h2>
      <span class="leise zahl">{reihenzahl(r)}</span>
      {#if r.zeile}<span class="marke-text lueckenzeile"><Symbol name="puzzle-piece" />{r.zeile}</span>{/if}
    </div>
    <div class="regal" class:gross={art === "grid-large"} class:nur={art === "covers"}>
      {#each r.eintraege as p (schluessel(p))}
        {#if p.art === "buch" && p.buch}
          <Band buch={p.buch} gross={art === "grid-large"} {reihe} />
        {:else if p.luecke}
          {@const l = p.luecke}
          <Platzhalter luecke={l} autor={stand.luecken?.autor ?? ""} offen={istOffen(r, l)} onoeffnen={(anker) => (offen = istOffen(r, l) ? null : { luecke: l, reihe: r, anker })} onabgelegt={mitAblegen ? (e) => void abgelegt(e, l) : undefined} />
        {/if}
      {/each}
    </div>
  </section>
{/each}

{#if offen}
  {@const o = offen}
  <Menue anker={o.anker} name="Band {o.luecke.nummer} fehlt" breite="21rem" onschliessen={() => (offen = null)}>
    <div class="lueckenfeld"><Lueckenfeld luecke={o.luecke} reihe={o.reihe} {stand} autor={stand.luecken?.autor ?? ""} onschliessen={() => (offen = null)} /></div>
  </Menue>
{/if}
