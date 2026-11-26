<script lang="ts">
  // Schritt Erste Bücher: Hochladen mit Vorschau, Eingangsordner, Ordner auf dem Gerät, gemeinfreie Bücher. Eine Vorschau wartet
  // hier nur; bestätigt wird sie nach dem Abschluss unter Hinzufügen.
  import type { Schritt } from "../../lib/api/einrichtung";
  import { anzahl, groesse } from "../../lib/format";
  import { annahme } from "../../lib/stand/annahme.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Ablage from "../hinzu/Ablage.svelte";
  import Quellen from "../hinzu/quellen/Quellen.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  let offene = $derived(annahme.vorschauen.filter((v) => v.stand === "offen"));

  $effect(() => void annahme.starte());
</script>

<Schrittrahmen ueberspringen={!schritt.pflicht}>
  <p class="leise">Jeder Weg geht auch später unter Hinzufügen.</p>
  <Ablage nachVorschau={() => undefined} />
  {#each offene as v (v.id)}
    <div class="platte ew-wartet">
      <Symbol name="list-check" />
      <span class="name"><b>{v.name}</b>{" "}<span class="leise zahl">{anzahl(v.dateien, "Datei", "Dateien")}{#if v.groesse}, {groesse(v.groesse)}{/if}</span></span>
      <span class="marke-text info">{v.laeuft ? "Wird gelesen" : "Vorschau wartet"}</span>
    </div>
  {/each}
  <Quellen />
</Schrittrahmen>
