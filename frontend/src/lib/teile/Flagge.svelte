<script lang="ts">
  // Runde Flagge einer Sprache (BF-71): Englisch und Deutsch als Zeichnung im Code, andere Sprachen mit ihrem Kürzel
  let { sprache, groesse = "1.875rem" }: { sprache: string; groesse?: string } = $props();
  const id = $props.id();
  let kurz = $derived(sprache.slice(0, 2).toLowerCase());
</script>

<svg class="flagge" viewBox="0 0 60 60" style:width={groesse} style:height={groesse} aria-hidden="true">
  <defs><clipPath id="rund-{id}"><circle cx="30" cy="30" r="30" /></clipPath></defs>
  <g clip-path="url(#rund-{id})">
    {#if kurz === "en"}
      <rect width="60" height="60" fill="#012169" />
      <path d="M0 0L60 60M60 0L0 60" stroke="#fff" stroke-width="12" />
      <path d="M0 0L60 60M60 0L0 60" stroke="#C8102E" stroke-width="5" />
      <path d="M30 0V60M0 30H60" stroke="#fff" stroke-width="16" />
      <path d="M30 0V60M0 30H60" stroke="#C8102E" stroke-width="9" />
    {:else if kurz === "de"}
      <rect width="60" height="20" fill="#000" />
      <rect y="20" width="60" height="20" fill="#DD0000" />
      <rect y="40" width="60" height="20" fill="#FFCE00" />
    {:else}
      <rect width="60" height="60" fill="#6b7a76" />
      <text x="30" y="38" text-anchor="middle" font-size="22" font-weight="600" fill="#fff">{kurz.toUpperCase()}</text>
    {/if}
  </g>
</svg>
