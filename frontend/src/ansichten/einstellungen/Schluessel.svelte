<script lang="ts">
  import { getToken, setToken } from "../../lib/api/client";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  let wert = $state(getToken());
  let sichtbar = $state(false);
  let geaendert = $derived(wert.trim() !== getToken());

  async function kopiere() {
    await navigator.clipboard.writeText(wert);
    melde.gut("Schlüssel kopiert");
  }

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    const neu = wert.trim();
    const ja = await frage({
      titel: "Schlüssel ersetzen?",
      folgen: ["Dieser Browser meldet sich ab jetzt mit dem neuen Schlüssel.", "Nimmt der Server ihn nicht an, erscheint die Anmeldung."],
      ja: "Schlüssel ersetzen",
      symbol: "key",
    });
    if (!ja) return;
    setToken(neu);
    location.reload();
  }
</script>

<p class="klein">Angemeldet wird mit der Kellerwolke. Daraus entsteht dieser Schlüssel; Skripte schicken ihn im Kopf der Anfrage mit. Ändern nur, wenn ein anderer gelten soll.</p>
<form class="reihe schluessel" onsubmit={speichere}>
  <input class="eingabe" type={sichtbar ? "text" : "password"} aria-label="Schlüssel" autocomplete="off" spellcheck="false" bind:value={wert} />
  <Knopf text={sichtbar ? "Verbergen" : "Zeigen"} symbol={sichtbar ? "eye-slash" : "eye"} onclick={() => (sichtbar = !sichtbar)} />
  <Knopf text="Kopieren" symbol="copy" gesperrt={!wert} onclick={() => void kopiere()} />
  <Knopf text="Speichern" symbol="check" art="submit" haupt gesperrt={!geaendert || !wert.trim()} />
</form>
