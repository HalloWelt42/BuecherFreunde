<script lang="ts">
  // KI über die Leitstelle: eingerichtet oder nicht, angeschlossen mit Grund (dieselbe Zeile wie unter Verbindungen) und die
  // Modellwahl, wenn die Leitstelle Modelle anbietet. Adresse und Schlüssel stehen in der Einrichtung des Servers.
  import { kiStatus, waehleKiModell, type KiStatus } from "../../lib/api/ai";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { verbindungen } from "../../lib/stand/verbindungen.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  let status = $state<KiStatus | null>(null);
  let arbeit = $state<"" | "pruefen" | "modell">("");

  let eingerichtet = $derived(anschluesse.jetzt.ki);
  let eintrag = $derived(verbindungen.liste.find((v) => v.kennung === "leitstelle"));
  let led = $derived(eingerichtet ? (eintrag?.stand ?? "aus") : "aus");
  let wort = $derived(!eingerichtet ? "nicht eingerichtet" : !eintrag ? "wird geprüft" : eintrag.stand === "schlecht" ? "antwortet nicht" : "angeschlossen");
  let grund = $derived(!eingerichtet ? "Adresse oder Schlüssel fehlen in der Einrichtung des Servers" : eintrag && eintrag.stand !== "gut" ? eintrag.text : "");
  let modell = $derived(status?.modell ?? "");
  let modelle = $derived<[string, string][]>((status?.modelle ?? []).map((m) => [m, m]));
  // Ein gewähltes Modell, das die Leitstelle nicht anbietet, bleibt sichtbar gewählt
  let wahl = $derived<[string, string][]>(!modell || modelle.some(([m]) => m === modell) ? modelle : [[modell, modell], ...modelle]);

  async function ladeStatus() {
    status = eingerichtet ? await kiStatus().catch(() => null) : null;
  }
  $effect(() => void ladeStatus());

  async function pruefe() {
    arbeit = "pruefen";
    await Promise.allSettled([verbindungen.pruefen(), ladeStatus()]);
    arbeit = "";
    if (!eingerichtet) melde.info(`Leitstelle: ${grund}`);
    else if (eintrag?.stand === "gut") melde.gut(`Leitstelle: ${eintrag.text}`);
    else melde.warn(`Leitstelle: ${eintrag?.text || "antwortet nicht"}`);
  }

  async function waehle(neu: string) {
    arbeit = "modell";
    try {
      await waehleKiModell(neu);
      await Promise.allSettled([verbindungen.pruefen(), ladeStatus()]);
      melde.gut(`Modell ${neu} gewählt`);
    } catch (e) {
      melde.schlecht(e, "Nicht gewechselt");
    }
    arbeit = "";
  }
</script>

<dl class="angaben">
  <dt>Leitstelle</dt><dd><span class="lampe"><span class="led {led}"></span>{wort}</span></dd>
  {#if grund}<dt>Grund</dt><dd>{grund}</dd>{/if}
  {#if eingerichtet && status?.url}<dt>Adresse</dt><dd><code class="pfad">{status.url}</code></dd>{/if}
  {#if eingerichtet && !modelle.length && modell}<dt>Modell</dt><dd>{modell}</dd>{/if}
</dl>
{#if eingerichtet && modelle.length}
  <div class="feld">Modell<Auswahl name="Modell" werte={wahl} wert={modell} gesperrt={arbeit === "modell"} onwahl={(m) => void waehle(m)} /></div>
{/if}
<div class="reihe"><Knopf text="Prüfen" symbol="stethoscope" klein laeuft={arbeit === "pruefen"} onclick={() => void pruefe()} /></div>
<p class="leise">Ordnet Bücher in Regale ein; die KI kommt über die Leitstelle.</p>
