<script>
  let { text = "", alertType = "note" } = $props();

  const config = {
    note:      { icon: "fa-circle-info",          label: "Hinweis",  color: "59, 130, 246" },
    tip:       { icon: "fa-lightbulb",            label: "Tipp",     color: "34, 197, 94" },
    important: { icon: "fa-circle-exclamation",   label: "Wichtig",  color: "139, 92, 246" },
    warning:   { icon: "fa-triangle-exclamation", label: "Warnung",  color: "245, 158, 11" },
    caution:   { icon: "fa-fire",                 label: "Achtung",  color: "239, 68, 68" },
  };

  let cfg = $derived(config[alertType] || config.note);
</script>

<div
  class="callout"
  role="note"
  style="--callout-rgb: {cfg.color};"
>
  <div class="callout-title">
    <i class="fa-solid {cfg.icon}"></i>
    <span>{cfg.label}</span>
  </div>
  <div class="callout-body">{text}</div>
</div>

<style>
  .callout {
    margin: 1em 0;
    border-radius: 6px;
    overflow: hidden;
    background: rgba(var(--callout-rgb), 0.08);
    border-left: 3px solid rgb(var(--callout-rgb));
  }

  .callout-title {
    display: flex;
    align-items: center;
    gap: 0.5em;
    padding: 0.5em 0.75em;
    font-weight: 700;
    font-size: 0.875em;
    color: rgb(var(--callout-rgb));
    background: rgba(var(--callout-rgb), 0.06);
  }

  .callout-title i {
    font-size: 1em;
    flex-shrink: 0;
  }

  .callout-body {
    padding: 0.5em 0.75em 0.625em;
    line-height: 1.6;
    font-size: 0.9375em;
    color: var(--color-text-primary);
    opacity: 0.92;
  }

  /* Dark Mode */
  :global(:root.dark) .callout {
    background: rgba(var(--callout-rgb), 0.1);
  }
  :global(:root.dark) .callout-title {
    background: rgba(var(--callout-rgb), 0.08);
  }

  /* Papier Sepia */
  :global(.papier-sepia) .callout {
    background: rgba(var(--callout-rgb), 0.07);
  }
  :global(.papier-sepia) .callout-title {
    background: rgba(var(--callout-rgb), 0.05);
  }
  :global(.papier-sepia) .callout-body {
    color: #3d2b1f;
  }
  :global(:root.dark .papier-sepia) .callout-body {
    color: #d4c5a9;
  }

  /* Papier Dunkel */
  :global(.papier-dunkel) .callout {
    background: rgba(var(--callout-rgb), 0.12);
  }
  :global(.papier-dunkel) .callout-title {
    background: rgba(var(--callout-rgb), 0.1);
  }
  :global(.papier-dunkel) .callout-body {
    color: #c8c8c8;
  }
</style>
