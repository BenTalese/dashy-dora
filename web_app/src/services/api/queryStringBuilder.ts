export enum FilterOperator {
    EQUAL = 'eq',
    NOT_EQUAL = 'ne',
    LESS_THAN = 'lt',
    GREATER_THAN = 'gt',
    LESS_THAN_OR_EQUAL = 'le',
    GREATER_THAN_OR_EQUAL = 'ge',
    CONTAINS = 'ct'
}

export enum SortOrder {
    ASCENDING = 'asc',
    DESCENDING = 'desc'
}

export interface FilterOperation {
    field: string;
    operator: FilterOperator;
    value: string | number | boolean;
}

export interface SortOperation {
    field: string;
    order?: SortOrder;
}

export interface PaginationOperation {
    page: number;
    limit: number;
}

export interface Page<T> {
    items: T[];
    total: number;
    page: number;
    limit: number;
}

/**
 * Builds a `?filter=...&filter=...&sort=field:asc&page=1&limit=50` query
 * string against list endpoints. Returns the leading "?" or an empty string.
 */
export function createQueryString(
    filters?: FilterOperation[],
    sort?: SortOperation,
    pagination?: PaginationOperation
): string {
    const params = new URLSearchParams();

    if (filters) {
        for (const f of filters) {
            params.append('filter', `${f.field}:${f.operator}:${f.value}`);
        }
    }
    if (sort) {
        params.set('sort', `${sort.field}:${sort.order ?? SortOrder.ASCENDING}`);
    }
    if (pagination) {
        params.set('page', String(pagination.page));
        params.set('limit', String(pagination.limit));
    }

    const qs = params.toString();
    return qs.length > 0 ? `?${qs}` : '';
}

/** The server's page-size ceiling (`query_options.MAX_LIMIT`). */
export const MAX_PAGE_LIMIT = 500;

/**
 * Load every row of a paginated list endpoint by asking for full pages until a
 * short page arrives (or `total` is reached). Stores that filter and search
 * client-side over what they hold use this, so row 51 onward is never silently
 * dropped by the default page size (FU-035, FU-668).
 */
export async function fetchAllPages<T>(
    fetchPage: (page: number, limit: number) => Promise<Page<T>>,
    limit: number = MAX_PAGE_LIMIT,
): Promise<T[]> {
    const collected: T[] = [];
    let page = 1;
    while (true) {
        const result = await fetchPage(page, limit);
        collected.push(...result.items);
        if (result.items.length < limit || collected.length >= (result.total ?? collected.length)) {
            return collected;
        }
        page += 1;
    }
}
