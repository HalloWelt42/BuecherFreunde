<script>
  import CategoryTree from "./CategoryTree.svelte";

  let { categories = [], level = 0, activeId = null } = $props();

  let expanded = $state({});

  function toggle(id) {
    expanded[id] = !expanded[id];
  }
</script>

<ul class="category-tree" style="--level: {level}">
  {#each categories as cat (cat.id)}
    <li>
      <div class="category-item" class:active={activeId === cat.id}>
        {#if cat.kinder && cat.kinder.length > 0}
          <button
            class="expand-btn"
            onclick={() => toggle(cat.id)}
            title={expanded[cat.id] ? "Zuklappen" : "Aufklappen"}
          >
            <i class="fa-solid {expanded[cat.id] ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
          </button>
        {:else}
          <span class="expand-placeholder"></span>
        {/if}

        <a href="/?category={cat.id}" class="category-link">
          <span class="category-name">{cat.name}</span>
          {#if cat.buch_anzahl > 0}
            <span class="category-count">{cat.buch_anzahl}</span>
          {/if}
        </a>
      </div>

      {#if expanded[cat.id] && cat.kinder && cat.kinder.length > 0}
        <CategoryTree
          categories={cat.kinder}
          level={level + 1}
          {activeId}
        />
      {/if}
    </li>
  {/each}
</ul>

<style>
  .category-tree {
    list-style: none;
    padding: 0;
    margin: 0;
    padding-left: calc(var(--level) * 0.75rem);
  }

  .category-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0;
  }

  .category-item.active .category-link {
    color: var(--color-accent);
    font-weight: 600;
  }

  .expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    padding: 0.125rem;
    width: 1.25rem;
    text-align: center;
    flex-shrink: 0;
  }

  .expand-btn:hover {
    color: var(--color-text-primary);
  }

  .expand-placeholder {
    width: 1.25rem;
    flex-shrink: 0;
  }

  .category-link {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    text-decoration: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    flex: 1;
    min-width: 0;
  }

  .category-link:hover {
    color: var(--color-text-primary);
  }

  .category-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .category-count {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    background-color: var(--color-bg-tertiary);
    padding: 0.0625rem 0.375rem;
    border-radius: 999px;
    flex-shrink: 0;
  }
</style>
