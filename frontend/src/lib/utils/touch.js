/**
 * Wiederverwendbarer Swipe-Handler fuer Touch-Geraete (iPad, Smartphones).
 *
 * @param {HTMLElement} element - DOM-Element auf das gehoert wird
 * @param {Object} callbacks
 * @param {Function} [callbacks.onSwipeLeft]  - Callback bei Wisch nach links
 * @param {Function} [callbacks.onSwipeRight] - Callback bei Wisch nach rechts
 * @param {number}   [callbacks.threshold=50] - Mindest-Distanz in px
 * @returns {Function} cleanup - Entfernt alle Listener
 */
export function createSwipeHandler(element, { onSwipeLeft, onSwipeRight, threshold = 50 } = {}) {
  let startX = 0;
  let startY = 0;
  let tracking = false;

  function onTouchStart(e) {
    if (e.touches.length !== 1) return;
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
    tracking = true;
  }

  function onTouchMove(e) {
    if (!tracking) return;
    const dx = e.touches[0].clientX - startX;
    const dy = e.touches[0].clientY - startY;
    // Horizontaler Swipe: Default verhindern (kein Browser-Back/Forward)
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {
      e.preventDefault();
    }
  }

  function onTouchEnd(e) {
    if (!tracking) return;
    tracking = false;

    const endX = e.changedTouches[0].clientX;
    const endY = e.changedTouches[0].clientY;
    const dx = endX - startX;
    const dy = endY - startY;

    // Nur auswerten wenn horizontal > vertikal und ueber Schwelle
    if (Math.abs(dx) < threshold || Math.abs(dx) < Math.abs(dy)) return;

    if (dx < 0 && onSwipeLeft) {
      onSwipeLeft();
    } else if (dx > 0 && onSwipeRight) {
      onSwipeRight();
    }
  }

  element.addEventListener("touchstart", onTouchStart, { passive: true });
  element.addEventListener("touchmove", onTouchMove, { passive: false });
  element.addEventListener("touchend", onTouchEnd, { passive: true });

  return function cleanup() {
    element.removeEventListener("touchstart", onTouchStart);
    element.removeEventListener("touchmove", onTouchMove);
    element.removeEventListener("touchend", onTouchEnd);
  };
}
