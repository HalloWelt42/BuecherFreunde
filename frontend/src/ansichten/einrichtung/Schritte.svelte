<script lang="ts">
  // Fortschritt und der gezeigte Schritt; dieselbe Folge in der Karte vor der Anmeldung und in der Bühne (Wartung). Gibt es
  // schon ein Konto, dieses Gerät ist aber nicht angemeldet, kommt erst die Anmeldung.
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Aenderungen from "./Aenderungen.svelte";
  import Anmelden from "./Anmelden.svelte";
  import Anschlussschritt from "./Anschlussschritt.svelte";
  import Buecherschritt from "./Buecherschritt.svelte";
  import Familienschritt from "./Familienschritt.svelte";
  import Fortschritt from "./Fortschritt.svelte";
  import Katalogschritt from "./Katalogschritt.svelte";
  import Kontoschritt from "./Kontoschritt.svelte";
  import Neuaufbaubericht from "./Neuaufbaubericht.svelte";
  import Neuaufbauschritt from "./Neuaufbauschritt.svelte";
  import Ordnerschritt from "./Ordnerschritt.svelte";
  import Originalbericht from "./Originalbericht.svelte";
  import Originaleschritt from "./Originaleschritt.svelte";
  import Orteschritt from "./Orteschritt.svelte";
  import Pruefschritt from "./Pruefschritt.svelte";
  import Sicherungsschritt from "./Sicherungsschritt.svelte";
  import Uebersicht from "./Uebersicht.svelte";
  import Verbindenschritt from "./Verbindenschritt.svelte";

  let { angemeldet }: { angemeldet: boolean } = $props();

  let s = $derived(einrichtung.schritt);
  let lauf = $derived(einrichtung.lauf);
</script>

{#if s && lauf}
  <Fortschritt {lauf} schritte={einrichtung.schritte} schritt={s} />
  {#if einrichtung.zustand?.konto && !angemeldet}
    <Anmelden />
  {:else}
    {#key s.schluessel}
      {#if s.schluessel === "konto"}<Kontoschritt schritt={s} />
      {:else if s.schluessel === "orte"}<Orteschritt schritt={s} />
      {:else if s.schluessel === "anschluesse"}<Anschlussschritt schritt={s} />
      {:else if s.schluessel === "katalog"}<Katalogschritt schritt={s} />
      {:else if s.schluessel === "familie"}<Familienschritt schritt={s} />
      {:else if s.schluessel === "buecher"}<Buecherschritt schritt={s} />
      {:else if s.schluessel === "sicherung"}<Sicherungsschritt schritt={s} />
      {:else if s.schluessel === "pruefung"}<Pruefschritt schritt={s} />
      {:else if s.schluessel === "ordner"}<Ordnerschritt schritt={s} />
      {:else if s.schluessel === "neuaufbau"}<Neuaufbauschritt schritt={s} />
      {:else if s.schluessel === "verbinden"}<Verbindenschritt schritt={s} />
      {:else if s.schluessel === "originale"}<Originaleschritt schritt={s} />
      {:else if lauf === "wartung"}<Aenderungen />
      {:else if lauf === "neu"}<Uebersicht />
      {:else if lauf === "kellerwolke"}<Neuaufbaubericht />
      {:else}<Originalbericht />{/if}
    {/key}
  {/if}
{:else}
  <div class="ew-schritt rollen"><Zustand art="laedt" text="Einrichtung wird geholt" /></div>
{/if}
