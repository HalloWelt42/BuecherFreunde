<script lang="ts">
  // Ein Zeichen aus Font Awesome, für Vorleseprogramme unsichtbar
  let { name, art = "solid", dreht = false, klasse = "", farbe = undefined }: { name: string; art?: "solid" | "brands"; dreht?: boolean; klasse?: string; farbe?: string } = $props();
  let kurz = $derived(name.replace(/^fa-/, ""));
</script>

<i class="fa-{art} fa-{kurz} {klasse}" class:fa-spin={dreht} style:color={farbe} aria-hidden="true"></i>
