<script lang="ts">
  // Ein Profil im Elternbereich: Kopf mit Bild, Rolle und PIN, dazu "Profil" (Name, Bild, PIN, Löschen) und bei Kindern
  // "Dieses Gerät fest auf ...", gedrückt, solange das Gerät es ist: dann löst ein Tipp die Bindung (als Verwaltung nach der
  // Rückfrage, sonst mit der PIN der Eltern). Ein Kind hat darunter seine Felder: Stufe, Freigegeben, Lesezeit, Einblick,
  // Lesehilfen, Katze.
  import type { Profil } from "../../../lib/api/familie";
  import { profilZeile } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import { ich } from "../../../lib/stand/ich.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import { frage } from "../../../lib/stand/rueckfrage.svelte";
  import { profilformular } from "../../../lib/stand/profilformular.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Profilbild from "../../../lib/teile/Profilbild.svelte";
  import Einblickfeld from "./Einblickfeld.svelte";
  import Freigabefeld from "./Freigabefeld.svelte";
  import Geraetfenster from "./Geraetfenster.svelte";
  import Katzenfeld from "./Katzenfeld.svelte";
  import Lesehilfenfeld from "./Lesehilfenfeld.svelte";
  import Lesezeitfeld from "./Lesezeitfeld.svelte";
  import Stufenfeld from "./Stufenfeld.svelte";

  let { profil }: { profil: Profil } = $props();

  let kind = $derived(profil.rolle === "kind");
  let aendert = $derived(ich.darfAendern(profil));
  let fenster = $state<"binden" | "loesen" | null>(null);
  let festHier = $derived(familie.festAuf === profil.id);

  async function geraet() {
    if (!festHier) {
      fenster = "binden";
      return;
    }
    if (!ich.darf("profile")) {
      fenster = "loesen";
      return;
    }
    const ja = await frage({ titel: "Dieses Gerät lösen?", folgen: [`Beim Start öffnet es dann nicht mehr von selbst ${profil.name}, sondern zeigt alle Profile zur Wahl.`], ja: "Lösen", symbol: "lock-open", gefahr: false });
    if (!ja) return;
    try {
      await familie.loese();
      melde.gut("Gerät gelöst");
    } catch (e) {
      melde.schlecht(e, "Nicht gelöst");
    }
  }
</script>

<section class="profilansicht platte" aria-label="Profil {profil.name}">
  <div class="profilkopf">
    <Profilbild {profil} groesse="3rem" />
    <div><b>{profil.name}</b><br /><span class="leise">{profilZeile(profil)}</span></div>
    {#if aendert || (kind && ich.darfFreigeben(profil))}
      <span class="tasten">
        {#if aendert}<Knopf text="Profil" symbol="pen" klein titel="Name, Bild und PIN von {profil.name}" onclick={() => profilformular.oeffne({ profil })} />{/if}
        {#if kind && ich.darfFreigeben(profil)}<Knopf text="Dieses Gerät fest auf {profil.name}" titel={festHier ? "Gerät lösen" : undefined} symbol="tablet-screen-button" klein gedrueckt={festHier} onclick={() => void geraet()} />{/if}
      </span>
    {/if}
  </div>
  {#if kind}
    <div class="elternfelder">
      <Stufenfeld {profil} {aendert} />
      <Freigabefeld {profil} />
      <Lesezeitfeld {profil} {aendert} />
      <Einblickfeld {profil} />
      <Lesehilfenfeld {profil} {aendert} />
      <Katzenfeld {profil} {aendert} />
    </div>
  {/if}
</section>

{#if fenster}<Geraetfenster kind={profil} art={fenster} onschliessen={() => (fenster = null)} />{/if}
