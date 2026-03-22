<script>
  import { zuletztGelesen } from "../../api/user-data.js";
  import { coverUrl } from "../../api/books.js";
  import { parseProgress } from "../../utils/reading.js";

  let books = $state([]);
  let laden = $state(true);

  import { onMount } from "svelte";

  onMount(() => {
    ladeZuletztGelesen();
  });

  async function ladeZuletztGelesen() {
    laden = true;
    try {
      books = await zuletztGelesen(6);
    } catch {
      books = [];
    } finally {
      laden = false;
    }
  }
</script>

{#if !laden && books.length > 0}
  <section class="continue-reading">
    <h2 class="section-title">Weiterlesen</h2>
    <div class="books-row">
      {#each books as book (book.id)}
        <a href="/book/{book.id}/read" class="continue-card">
          <div class="card-cover">
            <img
              src={coverUrl(book.id, book.updated_at)}
              alt={book.title}
              loading="lazy"
              onerror={(e) => (e.target.style.display = "none")}
            />
            {#if book.reading_position && parseProgress(book.reading_position, book.page_count) > 0}
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  style="width: {parseProgress(book.reading_position, book.page_count)}%"
                ></div>
              </div>
            {/if}
          </div>
          <span class="card-title">{book.title}</span>
        </a>
      {/each}
    </div>
  </section>
{/if}


<style>
  .continue-reading {
    margin-bottom: 2rem;
  }

  .section-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.75rem;
  }

  .books-row {
    display: flex;
    gap: 0.75rem;
    overflow-x: auto;
    padding-bottom: 0.5rem;
  }

  .continue-card {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    width: 100px;
    flex-shrink: 0;
    text-decoration: none;
  }

  .continue-card:hover {
    opacity: 0.85;
  }

  .card-cover {
    position: relative;
    aspect-ratio: 2 / 3;
    border-radius: 6px;
    overflow: hidden;
    background-color: var(--color-bg-tertiary);
  }

  .card-cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .progress-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3px;
    background-color: rgba(0, 0, 0, 0.3);
  }

  .progress-fill {
    height: 100%;
    background-color: var(--color-accent);
    transition: width 0.3s;
  }

  .card-title {
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
