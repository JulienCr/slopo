/**
 * Builds a short digest line summarizing unread notification counts.
 */
function buildDigestLine(unreadCount: number, mutedCount: number): string {
    // muted notifications never contribute to the headline count
    const visibleCount = unreadCount - mutedCount;
    if (visibleCount <= 0) {
        return "You're all caught up";
    }
    if (visibleCount === 1) {
        return "1 new notification";
    }
    return `${visibleCount} new notifications`; // pluralized form
}
