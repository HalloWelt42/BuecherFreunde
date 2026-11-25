<script lang="ts">
  import Symbol from "../../lib/teile/Symbol.svelte";
  let { text = "", alertType = "note" }: { text?: string; alertType?: string } = $props();
  const arten: Record<string, [string, string, string]> = {
    note: ["circle-info", "Hinweis", "59 130 246"], tip: ["lightbulb", "Tipp", "34 160 84"], important: ["circle-exclamation", "Wichtig", "139 92 246"],
    warning: ["triangle-exclamation", "Warnung", "217 119 6"], caution: ["fire", "Achtung", "220 60 60"],
  };
  let [symbol, name, farbe] = $derived(arten[alertType] ?? arten.note);
</script>

<aside class="kasten" style:--f={farbe}>
  <b><Symbol name={symbol} /> {name}</b>
  <div class="text">{text}</div>
</aside>

<style>
  .kasten {
    margin: 0 0 0.9em;
    padding: 0.625em 0.875em;
    border-radius: 3px;
    border-left: 4px solid rgb(var(--f));
    background: rgb(var(--f) / 0.12);
  }
  .text {
    white-space: pre-wrap;
  }
</style>
