// The icon for each settings page, keyed by its route path: the one source
// the sidebar, the phone nav and the page heading all read (FU-672; the nav
// and every page used to declare it separately and agreed only by hand).
import { ICONS } from 'src/style/icons';

const SETTINGS_PAGE_ICONS: Record<string, string> = {
    '/settings/account': ICONS.person,
    '/settings/preferences': ICONS.palette,
    '/settings/notifications': ICONS.notifications,
    '/settings/voice': ICONS.record_voice_over,
    '/settings/assistant': ICONS.smart_toy,
    '/settings/about': ICONS.info,
    '/settings/kitchen-setup/stock-locations': ICONS.place,
    '/settings/kitchen-setup/stock-groups': ICONS.tag_multiple,
    '/settings/kitchen-setup/stores': ICONS.store,
    '/settings/budget': ICONS.savings,
    '/settings/kitchen-setup/qr-labels': ICONS.qr_code,
    '/settings/kitchen-setup/unlinked-ingredients': ICONS.link,
    '/settings/kitchen-setup/nutrition-matching': ICONS.monitor_heart,
    '/settings/kitchen-setup/recipe-cuisines': ICONS.public,
    '/settings/kitchen-setup/recipe-categories': ICONS.category,
    '/settings/kitchen-setup/recipe-tools': ICONS.blender,
    '/settings/kitchen-setup/recipe-meal-slots': ICONS.schedule,
    '/settings/kitchen-setup/recipe-dietary-tags': ICONS.eco,
    '/settings/admin/users': ICONS.group,
    '/settings/admin/system/region': ICONS.language,
    '/settings/admin/system/email': ICONS.mark_email_read,
    '/settings/admin/system/push': ICONS.notifications_active,
    '/settings/admin/system/voice': ICONS.record_voice_over,
    '/settings/admin/system/stock': ICONS.inventory_2,
    '/settings/admin/system/stocktake': ICONS.fact_check,
    '/settings/admin/system/cooking': ICONS.chef_hat,
    '/settings/admin/system/meal-reconcile': ICONS.event_note,
    '/settings/admin/system/nutrition': ICONS.monitor_heart,
    '/settings/admin/system/money': ICONS.savings,
    '/settings/admin/system/alerts': ICONS.notifications,
    '/settings/admin/system/ingestion': ICONS.cloud_upload,
    '/settings/admin/data/backup': ICONS.cloud_download,
    '/settings/admin/data/import': ICONS.file_upload,
    '/settings/admin/system/images': ICONS.image,
    '/settings/admin/api-access': ICONS.key,
    '/settings/admin/audit-log': ICONS.history,
};

/** The page's icon, or undefined for a path that isn't a settings page. */
export function settingsPageIcon(path: string): string | undefined {
    return SETTINGS_PAGE_ICONS[path];
}
