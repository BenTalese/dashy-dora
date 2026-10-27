import type { ReportRange } from 'src/services/api/reportsApiService';

/**
 * The Reports range picker's words, for sentences that name the window.
 * One table for every card so "the last 90 days" reads the same everywhere
 * (R-003). `allTime` lets a card phrase the open window in its own terms.
 */
export function rangeWindowWords(range: ReportRange, allTime = 'all time'): string {
    switch (range) {
        case '30d': return 'in the last 30 days';
        case '90d': return 'in the last 90 days';
        case '1y': return 'in the last year';
        case '2y': return 'in the last 2 years';
        case '5y': return 'in the last 5 years';
        case 'all': return allTime;
    }
}

/**
 * The comparison window: the same length as the current one, immediately
 * before it, so a 90-day view never says "than last month". Empty for the
 * open window, which has nothing before it.
 */
export function rangePriorWords(range: ReportRange): string {
    switch (range) {
        case '30d': return 'the 30 days before';
        case '90d': return 'the 90 days before';
        case '1y': return 'the year before';
        case '2y': return 'the 2 years before';
        case '5y': return 'the 5 years before';
        case 'all': return '';
    }
}
