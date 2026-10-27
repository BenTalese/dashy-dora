import { computed } from 'vue';
import type { Product } from 'src/models/product';

/**
 * The store's own product page as a real link (D-005: keyboard, middle-click
 * and the status-bar preview all work), shared by the product card and row.
 * Only an anchor when there's somewhere to go and the list isn't selecting:
 * a dead `<a href="#">` would look clickable and do nothing.
 */
export function useProductStoreLink(product: () => Product, bulkMode: () => boolean) {
    const isLink = computed(() => !bulkMode() && !!product().web_url);
    const tag = computed(() => (isLink.value ? 'a' : 'div'));
    const attrs = computed(() => {
        if (!isLink.value) return {};
        const p = product();
        return {
            href: p.web_url,
            target: '_blank',
            rel: 'noopener',
            // The link text is the product name inside; naming the
            // destination keeps the purpose obvious out of context (D-005).
            'aria-label': `Open ${p.name} at ${p.store_name ?? 'the store'}`,
        };
    });
    return { isLink, tag, attrs };
}
