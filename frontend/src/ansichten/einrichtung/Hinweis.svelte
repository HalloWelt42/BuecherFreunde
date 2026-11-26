<script lang="ts">
  // Die Zeile unter einem Auftrag: er läuft auf dem Server weiter, auch wenn die Seite zu ist
  import Symbol from "../../lib/teile/Symbol.svelte";

  let { text = "Läuft weiter, wenn du die Seite schließt; beim nächsten Öffnen steht hier der Stand." }: { text?: string } = $props();
</script>

<p class="leise ew-hinweiszeile"><Symbol name="arrows-rotate" /><span>{text}</span></p>
