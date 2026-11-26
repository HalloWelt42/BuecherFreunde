<script lang="ts">
  // Die Katze im Kinderbereich: an oder aus (in der Gestaltung groß anfangs aus, dann klein am Rand), ihr Name (gibt sonst das
  // Kind selbst), Schnurren nur auf Wunsch
  import type { Profil } from "../../../lib/api/familie";
  import { einstellungenVon } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Schalter from "../../../lib/teile/Schalter.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import { setze } from "./aendern";
  import Wertchip from "./Wertchip.svelte";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  const NAME_HOECHSTENS = 24;
  let einstellungen = $derived(einstellungenVon(profil, familie.stufen.stufen));
  let katze = $derived(einstellungen.katze);
  let name = $state("");

  function benenne(e: SubmitEvent, zu: () => void) {
    e.preventDefault();
    const neu = name.trim();
    if (neu && neu !== katze.name) void setze(profil, "katze", { name: neu });
    zu();
  }
</script>

<section class="elternfeld platte">
  <h3><Symbol name="cat" />Katze</h3>
  <div class="elternzeile">
    <span>Katze im Bereich{#if einstellungen.gestaltung === "gross"}<small>in Groß klein am Rand</small>{/if}</span>
    <Schalter an={katze.an} name="Katze im Bereich" gesperrt={!aendert} onwahl={(an) => void setze(profil, "katze", { an })} />
  </div>
  <div class="elternzeile">
    <span>Name{#if !katze.name}<small>{profil.name} gibt ihr selbst einen</small>{/if}</span>
    <Wertchip text={katze.name || "Ohne Namen"} name="Name der Katze" gesperrt={!aendert || !katze.an}>
      {#snippet children(zu)}
        <form class="benennen" onsubmit={(e) => benenne(e, zu)}>
          <label class="feld">Name der Katze<input class="eingabe" data-fokus maxlength={NAME_HOECHSTENS} placeholder={katze.name} bind:value={name} /></label>
          <Knopf text="Speichern" symbol="check" art="submit" klein gesperrt={!name.trim()} />
        </form>
      {/snippet}
    </Wertchip>
  </div>
  <div class="elternzeile">
    <span>Schnurren beim Streicheln</span>
    <Schalter an={katze.schnurren} name="Schnurren beim Streicheln" gesperrt={!aendert || !katze.an} onwahl={(schnurren) => void setze(profil, "katze", { schnurren })} />
  </div>
</section>

<style>
  .benennen {
    display: grid;
    gap: 0.5rem;
    justify-items: start;
  }
  .benennen .feld {
    justify-self: stretch;
  }
</style>
