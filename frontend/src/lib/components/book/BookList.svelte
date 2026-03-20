<script>
  import RatingStars from "../ui/RatingStars.svelte";
  import { coverUrl } from "../../api/books.js";

  let { books = [], onSort = null } = $props();

  let sortColumn = $state("title");
  let sortDir = $state("asc");

  function handleSort(column) {
    if (sortColumn === column) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortColumn = column;
      sortDir = "asc";
    }
    if (onSort) {
      onSort(sortColumn, sortDir);
    }
  }

  function sortIndicator(column) {
    if (sortColumn !== column) return "";
    return sortDir === "asc" ? " \u25B4" : " \u25BE";
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  const formatLabel = {
    pdf: "PDF",
    epub: "EPUB",
    mobi: "MOBI",
    txt: "TXT",
    md: "MD",
  };
</script>

{#if books.length === 0}
  <div class="empty">
    <p>Keine Bücher gefunden.</p>
  </div>
{:else}
  <div class="table-wrapper">
    <table class="book-table">
      <thead>
        <tr>
          <th class="col-cover"></th>
          <th class="col-title sortable" onclick={() => handleSort("title")}>
            Titel{sortIndicator("title")}
          </th>
          <th class="col-author sortable" onclick={() => handleSort("author")}>
            Autor{sortIndicator("author")}
          </th>
          <th class="col-format">Format</th>
          <th class="col-size sortable" onclick={() => handleSort("file_size")}>
            Größe{sortIndicator("file_size")}
          </th>
          <th class="col-rating sortable" onclick={() => handleSort("rating")}>
            Bewertung{sortIndicator("rating")}
          </th>
          <th class="col-year sortable" onclick={() => handleSort("year")}>
            Jahr{sortIndicator("year")}
          </th>
        </tr>
      </thead>
      <tbody>
        {#each books as book (book.id)}
          <tr>
            <td class="col-cover">
              <a href="#/book/{book.id}" class="cover-link">
                <img
                  src={coverUrl(book.id)}
                  alt=""
                  class="mini-cover"
                  loading="lazy"
                  onerror={(e) => (e.target.style.display = "none")}
                />
              </a>
            </td>
            <td class="col-title">
              <a href="#/book/{book.id}" class="title-link">
                {book.title}
              </a>
            </td>
            <td class="col-author">{book.author || "Unbekannt"}</td>
            <td class="col-format">
              <span class="format-tag">
                {formatLabel[book.file_format] || book.file_format}
              </span>
            </td>
            <td class="col-size">{formatSize(book.file_size)}</td>
            <td class="col-rating">
              <RatingStars rating={book.rating} />
            </td>
            <td class="col-year">{book.year || "-"}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .table-wrapper {
    overflow-x: auto;
  }

  .book-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  .book-table th {
    text-align: left;
    font-weight: 600;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.625rem 0.5rem;
    border-bottom: 2px solid var(--color-border);
    white-space: nowrap;
  }

  .book-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .book-table th.sortable:hover {
    color: var(--color-text-primary);
  }

  .book-table td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--color-border);
    vertical-align: middle;
  }

  .book-table tbody tr:hover {
    background-color: var(--color-bg-tertiary);
  }

  .col-cover {
    width: 40px;
  }

  .cover-link {
    display: block;
  }

  .mini-cover {
    width: 32px;
    height: 48px;
    object-fit: cover;
    border-radius: 3px;
  }

  .title-link {
    color: var(--color-text-primary);
    text-decoration: none;
    font-weight: 500;
  }

  .title-link:hover {
    color: var(--color-accent);
  }

  .col-author {
    color: var(--color-text-secondary);
  }

  .format-tag {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  .col-size {
    color: var(--color-text-muted);
    white-space: nowrap;
    font-size: 0.8125rem;
  }

  .col-year {
    color: var(--color-text-muted);
    font-size: 0.8125rem;
  }

  .empty {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    color: var(--color-text-muted);
  }
</style>
