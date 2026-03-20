/**
 * @typedef {Object} Book
 * @property {number} id
 * @property {string} hash
 * @property {string} title
 * @property {string} author
 * @property {string} file_format
 * @property {number} file_size
 * @property {string} cover_path
 * @property {number} page_count
 * @property {number|null} year
 * @property {boolean} is_favorite
 * @property {boolean} is_to_read
 * @property {number} rating
 * @property {string} reading_position
 * @property {string|null} last_read_at
 * @property {Category[]} categories
 * @property {Tag[]} tags
 * @property {string} created_at
 */

/**
 * @typedef {Object} Category
 * @property {number} id
 * @property {string} name
 * @property {string} slug
 * @property {number|null} parent_id
 * @property {number} buch_anzahl
 * @property {Category[]} kinder
 */

/**
 * @typedef {Object} Tag
 * @property {number} id
 * @property {string} name
 * @property {string} slug
 * @property {string} color
 * @property {number} buch_anzahl
 */

/**
 * @typedef {Object} Collection
 * @property {number} id
 * @property {string} name
 * @property {string} description
 * @property {string} color
 */

/**
 * @typedef {Object} SearchResult
 * @property {number} book_id
 * @property {string} titel
 * @property {string} autor
 * @property {string} snippet
 * @property {number} relevanz
 */

/**
 * @typedef {Object} ImportTask
 * @property {number} id
 * @property {string} filename
 * @property {string} status
 * @property {number} progress_percent
 * @property {string} current_step
 * @property {string} error
 * @property {number|null} book_id
 */

export {};
