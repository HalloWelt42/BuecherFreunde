<script lang="ts">
  let { href = "", title = undefined, text = "" }: { href?: string; title?: string; text?: string } = $props();
  let sicher = $derived(/^(?:https?:|data:image\/(?:png|jpeg|gif|webp);)/i.test(href.trim()));
</script>

{#if sicher}<img src={href} alt={text} {title} loading="lazy" />{:else}<span {title}>[Bild: {text || href}]</span>{/if}
