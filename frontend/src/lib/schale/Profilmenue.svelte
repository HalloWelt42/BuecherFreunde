<script lang="ts">
  // Das Menü am Bild im Kopf (BF-78): wer gerade liest, das eigene Profil (Name, Bild, PIN) und der Wechsel zu "Wer liest?".
  // Darunter steht wie bisher das Konto des Geräts.
  import { rollenText } from "../familie";
  import { familie } from "../stand/familie.svelte";
  import { ich } from "../stand/ich.svelte";
  import { melde } from "../stand/meldungen.svelte";
  import { profilformular } from "../stand/profilformular.svelte";
  import { schale } from "../stand/schale.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Profilbild from "../teile/Profilbild.svelte";

  let laeuft = $state(false);

  $effect(() => void familie.ladeStufen().catch(() => undefined));

  function bearbeiten() {
    if (!ich.profil) return;
    schale.schliesseAlles();
    profilformular.oeffne({ profil: ich.profil });
  }

  async function wechseln() {
    laeuft = true;
    try {
      await familie.wechseln();
    } catch (e) {
      melde.schlecht(e, "Nicht gewechselt");
      laeuft = false;
    }
  }
</script>

{#if ich.profil}
  <div class="wer">
    <Profilbild profil={ich.profil} groesse="2.75rem" />
    <span><b>{ich.profil.name}</b><small>{rollenText(ich.profil, familie.stufen.stufen)}</small></span>
  </div>
  <div class="tasten">
    <Knopf text="Mein Profil" symbol="pen" onclick={bearbeiten} />
    {#if familie.wechselbar}<Knopf text="Profil wechseln" symbol="users" {laeuft} onclick={() => void wechseln()} />{/if}
  </div>
{/if}

<style>
  .wer {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.625rem;
    align-items: center;
    padding-bottom: 0.625rem;
  }
  .wer b {
    display: block;
    overflow-wrap: anywhere;
  }
  small {
    display: block;
    color: var(--tinte-3);
    font-size: 0.8125rem;
  }
  .tasten {
    display: grid;
    gap: 0.375rem;
    grid-template-columns: repeat(auto-fit, minmax(min(7.5rem, 100%), 1fr));
    padding-bottom: 0.75rem;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--linie);
  }
</style>
