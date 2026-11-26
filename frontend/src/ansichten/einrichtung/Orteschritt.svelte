<script lang="ts">
  // Schritt Speicherorte: jeder Ort mit Lampe, Pfad und Platz. Fehlt eine Platte, steht das rot da und Weiter bleibt gesperrt,
  // bis "Neu suchen" sie findet. Die Pfade kommen aus der Einrichtung des Servers und ändern sich nur mit einem Neustart.
  import { ladeOrte, type Orte, type Ortstand, type Schritt } from "../../lib/api/einrichtung";
  import { ORTSZWECK } from "../../lib/einrichtung/ablauf";
  import { groesse } from "../../lib/format";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  let orte = $state<Orte | null>(null);
  let fehler = $state("");
  let sucht = $state(false);

  async function suche() {
    sucht = true;
    try {
      orte = await ladeOrte();
      fehler = "";
      // Weiter hängt am Stand des Servers: nach dem Suchen gilt der neue
      await einrichtung.laden();
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      sucht = false;
    }
  }

  $effect(() => void suche());

  const platz = (o: Ortstand) => [o.belegt ? `${groesse(o.belegt)} belegt` : "", o.frei ? `${groesse(o.frei)} frei` : ""].filter(Boolean).join(", ");
  let gesperrt = $derived(!orte?.weiter || !schritt.weiter);
  let grund = $derived(orte?.grund || schritt.grund || "Erst wenn jeder Ort bereit ist");
</script>

<Schrittrahmen weiter={{ gesperrt, titel: gesperrt ? grund : undefined }}>
  {#if !orte}
    {#if fehler}<Zustand art="fehler" text={fehler} onerneut={() => void suche()} />{:else}<Zustand art="laedt" text="Orte werden gemessen" />{/if}
  {:else}
    {#if !orte.weiter}
      <div class="mulde ew-warnfeld">
        <p class="marke-text schlecht"><Symbol name="triangle-exclamation" />{orte.grund}</p>
        <p class="leise">Der Ort ist eingetragen, aber nicht bereit. Ist die Platte eingehängt? Danach neu suchen.</p>
        <div class="reihe"><Knopf text="Neu suchen" symbol="arrows-rotate" klein laeuft={sucht} onclick={() => void suche()} /></div>
      </div>
    {/if}
    <div class="ew-liste">
      {#each orte.orte as o (o.kennung)}
        <div class="stelle zeile-stand zwei">
          <span class="led {o.stand}"></span>
          <span>
            <b>{o.name}</b>{#if ORTSZWECK[o.kennung]}{" "}<span class="leise">{ORTSZWECK[o.kennung]}</span>{/if}<br />
            <code class="pfad">{o.pfad}</code>{#if platz(o)}{" "}<span class="leise zahl">{platz(o)}</span>{/if}
            {#if o.text}<br /><span class="marke-text {o.stand === 'schlecht' ? 'schlecht' : 'warn'}">{o.text}</span>{/if}
          </span>
        </div>
      {/each}
    </div>
    <p class="leise ew-hinweiszeile"><Symbol name="circle-info" /><span>Die Orte kommen aus der Einrichtung des Servers und ändern sich mit einem Neustart. Jeder dauerhafte Ort trägt eine Markerdatei, damit eine fehlende Platte auffällt.</span></p>
    {#if orte.weiter}<div class="reihe"><Knopf text="Neu suchen" symbol="arrows-rotate" klein laeuft={sucht} onclick={() => void suche()} /></div>{/if}
  {/if}
</Schrittrahmen>
