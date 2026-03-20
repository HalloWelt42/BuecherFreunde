<script>
  import BookCard from "./BookCard.svelte";

  let { books = [] } = $props();
</script>

{#if books.length === 0}
  <div class="empty">
    <p>Keine Bücher gefunden.</p>
  </div>
{:else}
  <div class="book-grid">
    {#each books as book (book.id)}
      <BookCard {book} />
    {/each}
  </div>
{/if}

<style>
  .book-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 1rem;
  }

  .empty {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    color: var(--color-text-muted);
  }
</style>
