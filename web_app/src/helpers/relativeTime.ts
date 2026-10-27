// Short "Nm ago / Nh ago / Nd ago / Nw ago / Nmo ago / Ny ago" relative-time
// formatter. Same shape used across stock-item detail, the observation list,
// and (FU-227 chunk 3) the YourPricesWidget — pulled out so the three call
// sites don't drift.
//
// `style: 'coarse'` is the sentence form, in whole days ("today",
// "yesterday", "3 days ago", "last week", "2 weeks ago"), for a card that
// reads as prose (the dashboard's restock radar; finalisation 08-R9).
export function relativeTime(iso: string, options: { style?: 'short' | 'coarse' } = {}): string {
    if (!iso) return '';
    const diffMs = Date.now() - new Date(iso).getTime();
    if (options.style === 'coarse') {
        const days = Math.floor(diffMs / 86_400_000);
        if (days <= 0) return 'today';
        if (days === 1) return 'yesterday';
        if (days < 7) return `${days} days ago`;
        if (days < 14) return 'last week';
        return `${Math.round(days / 7)} weeks ago`;
    }
    const mins = Math.floor(diffMs / 60_000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    const weeks = Math.floor(days / 7);
    if (weeks < 5) return `${weeks}w ago`;
    const months = Math.floor(days / 30);
    if (months < 12) return `${months}mo ago`;
    return `${Math.floor(days / 365)}y ago`;
}
