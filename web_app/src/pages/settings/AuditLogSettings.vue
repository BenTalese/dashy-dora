<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Audit log"
            description="Every mutating request, login attempt, client crash, and explicit service-layer event lands here. Filters narrow the view; click a row to see the full payload."
            :icon="ICONS.history"
        >
            <template #actions>
                <BaseButton
                    variant="secondary"
                    :icon="ICONS.file_download"
                    label="Export CSV"
                    :disable="rows.length === 0"
                    @click="exportCsv"
                />
            </template>
        </SettingsPageHeader>

        <!-- Retention moved here 2026-09-03 when the Hosting page was retired
             (owner: *"audit retention feels like a setting that should live
             with…the audit logs page"*). It is the one knob that changes what
             this page can still show you, so it sits above the log it prunes. -->
        <SettingsSection>
            <SettingsRow inline>
                <template #label>
                    Keep events for
                    <InfoTip label="Audit retention">
                        Audit events older than this are pruned nightly.
                        Anything between 1 and 3650 days (10 years).
                    </InfoTip>
                </template>
                <q-input
                    v-model.number="retention.audit_retention_days"
                    type="number"
                    outlined
                    dense
                    suffix="days"
                    style="max-width: 150px"
                    :min="1"
                    :max="3650"
                    @blur="onSaveRetention"
                />
            </SettingsRow>
        </SettingsSection>

        <hr class="settings-divider settings-divider--spaced" />

        <!-- ── Filters ───────────────────────────────────────────────── -->
        <section class="audit-filters">
            <div class="row q-col-gutter-sm">
                <q-select
                    v-model="filters.severity"
                    :options="severityOptions"
                    label="Severity"
                    outlined
                    dense
                    clearable
                    multiple
                    emit-value
                    map-options
                    use-chips
                    class="col-12 col-sm-3"
                />
                <q-input
                    v-model="filters.action"
                    label="Action (exact match)"
                    outlined
                    dense
                    clearable
                    class="col-12 col-sm-3"
                />
                <q-input
                    v-model="filters.actor_user_id"
                    label="Actor user id"
                    outlined
                    dense
                    clearable
                    class="col-12 col-sm-3"
                />
                <q-input
                    v-model="filters.entity_type"
                    label="Entity type"
                    outlined
                    dense
                    clearable
                    class="col-12 col-sm-3"
                />
                <q-input
                    v-model="filters.entity_id"
                    label="Entity id"
                    outlined
                    dense
                    clearable
                    class="col-12 col-sm-3"
                />
                <q-input
                    v-model="filters.request_id"
                    label="Request id"
                    outlined
                    dense
                    clearable
                    class="col-12 col-sm-3"
                />
                <q-input
                    v-model="filters.occurred_from"
                    label="From (ISO datetime)"
                    placeholder="2026-05-01T00:00:00"
                    outlined
                    dense
                    clearable
                    class="col-12 col-sm-3"
                />
                <q-input
                    v-model="filters.occurred_to"
                    label="To (ISO datetime, exclusive)"
                    placeholder="2026-05-28T00:00:00"
                    outlined
                    dense
                    clearable
                    class="col-12 col-sm-3"
                />
            </div>
            <div class="row q-mt-sm q-gutter-sm">
                <BaseButton
                    variant="primary"
                    :icon="ICONS.search"
                    label="Apply filters"
                    :loading="loading"
                    @click="reload(1)"
                />
                <BaseButton
                    variant="ghost"
                    label="Clear"
                    @click="clearFilters"
                />
            </div>
        </section>

        <hr class="settings-divider settings-divider--spaced" />

        <!-- ── Table ─────────────────────────────────────────────────── -->
        <div v-if="loadError" class="text-negative q-py-sm">
            {{ loadError }}
        </div>
        <q-table
            v-else
            :rows="rows"
            :columns="columns"
            row-key="audit_event_id"
            flat
            bordered
            :loading="loading"
            hide-pagination
            :rows-per-page-options="[0]"
            @row-click="(_, row) => openDetail(row)"
        >
            <template #body-cell-severity="props">
                <q-td :props="props">
                    <q-chip
                        dense
                        size="sm"
                        :color="severityColour(props.row.severity)"
                        text-color="dark"
                    >
                        {{ props.row.severity }}
                    </q-chip>
                </q-td>
            </template>
        </q-table>

        <div class="row items-center q-gutter-sm q-mt-md">
            <BaseButton
                variant="ghost"
                dense
                :icon="ICONS.chevron_left"
                label="Previous"
                :disable="page <= 1 || loading"
                @click="reload(page - 1)"
            />
            <div class="text-caption dora-text-muted">
                Page {{ page }} of {{ pageCount }} ({{ total.toLocaleString() }} event(s))
            </div>
            <BaseButton
                variant="ghost"
                dense
                :icon-right="ICONS.chevron_right"
                label="Next"
                :disable="page >= pageCount || loading"
                @click="reload(page + 1)"
            />
            <q-space />
            <q-select
                v-model="size"
                :options="[25, 50, 100, 200]"
                label="Per page"
                outlined
                dense
                style="min-width: 110px"
                @update:model-value="reload(1)"
            />
        </div>

        <!-- ── Detail drawer ─────────────────────────────────────────── -->
        <BaseDialog
            v-model="detailOpen"
            maximized
            card-style="width: 100%; max-width: 100vw; height: 100%; max-height: 100vh"
        >
                <q-toolbar>
                    <q-toolbar-title>
                        Audit event
                        <q-chip
                            v-if="detail"
                            dense
                            size="sm"
                            class="q-ml-sm"
                            :color="severityColour(detail.severity)"
                            text-color="dark"
                        >
                            {{ detail.severity }}
                        </q-chip>
                    </q-toolbar-title>
                    <BaseButton variant="icon" :icon="ICONS.close" v-close-popup />
                </q-toolbar>
                <q-separator />
                <q-card-section v-if="detail">
                    <q-list dense separator>
                        <q-item><q-item-section>Action</q-item-section><q-item-section side><code>{{ detail.action }}</code></q-item-section></q-item>
                        <q-item><q-item-section>When</q-item-section><q-item-section side>{{ formatWhen(detail.occurred_at) }}</q-item-section></q-item>
                        <q-item><q-item-section>Actor</q-item-section><q-item-section side>{{ detail.actor_username || '–' }} <span v-if="detail.actor_user_id" class="dora-text-muted">({{ detail.actor_user_id }})</span></q-item-section></q-item>
                        <q-item><q-item-section>Actor IP</q-item-section><q-item-section side>{{ detail.actor_ip || '–' }}</q-item-section></q-item>
                        <q-item v-if="detail.entity_type"><q-item-section>Entity</q-item-section><q-item-section side>{{ detail.entity_type }} <span v-if="detail.entity_id" class="dora-text-muted">({{ detail.entity_id }})</span></q-item-section></q-item>
                        <q-item v-if="detail.request_id"><q-item-section>Request id</q-item-section><q-item-section side><code>{{ detail.request_id }}</code></q-item-section></q-item>
                    </q-list>
                </q-card-section>
                <q-separator />
                <q-card-section v-if="detail">
                    <div class="text-subtitle2 q-mb-sm">Payload</div>
                    <pre class="audit-payload">{{ formatPayload(detail.payload) }}</pre>
                </q-card-section>
                <template #actions>
                    <BaseButton
                        v-if="detail?.request_id"
                        variant="ghost"
                        :icon="ICONS.link"
                        label="Find related"
                        @click="findRelated(detail.request_id)"
                    />
                    <BaseButton variant="ghost" label="Close" v-close-popup />
                </template>
        </BaseDialog>
    </div>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import { formatDateTime as formatLocaleDateTime } from 'src/composables/useDateFormat';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import { computed, onMounted, reactive, ref } from 'vue';
    import AuditApiService, { type AuditEvent, type AuditFilters } from 'src/services/api/auditApiService';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';

    const $q = useQuasar();
    const auditApi = new AuditApiService();

    // No source filter or column (owner 2026-10-15): every event this install
    // writes comes from the API, so the field never told anyone anything.
    const severityOptions = [
        { label: 'audit', value: 'audit' },
        { label: 'error', value: 'error' },
        { label: 'warn', value: 'warn' },
        { label: 'info', value: 'info' },
        { label: 'debug', value: 'debug' },
    ];

    const filters = reactive<AuditFilters>({});
    const page = ref(1);
    const size = ref(50);
    const total = ref(0);
    const rows = ref<AuditEvent[]>([]);
    const loading = ref(false);
    const loadError = ref<string | null>(null);

    const detail = ref<AuditEvent | null>(null);
    const detailOpen = ref(false);

    const pageCount = computed(() =>
        total.value === 0 ? 1 : Math.ceil(total.value / size.value),
    );

    const columns = [
        { name: 'occurred_at', label: 'When', field: (r: AuditEvent) => formatWhen(r.occurred_at), align: 'left' as const },
        { name: 'severity', label: 'Sev', field: 'severity', align: 'left' as const },
        { name: 'action', label: 'Action', field: 'action', align: 'left' as const, classes: 'text-mono' },
        { name: 'actor', label: 'Actor', field: (r: AuditEvent) => r.actor_username || r.actor_ip || '–', align: 'left' as const },
        { name: 'entity', label: 'Entity', field: (r: AuditEvent) => r.entity_type ? `${r.entity_type}` : '–', align: 'left' as const },
    ];

    function severityColour(sev: AuditEvent['severity']): string {
        if (sev === 'error') return 'negative';
        if (sev === 'warn') return 'warning';
        if (sev === 'audit') return 'primary';
        // R-002: info / debug routed through the theme-bound `info`
        // semantic (chip background) rather than `grey-N` literals.
        return 'info';
    }

    function formatWhen(iso: string): string {
        try {
            return formatLocaleDateTime(iso) || iso;
        } catch {
            return iso;
        }
    }

    function formatPayload(payload: unknown): string {
        if (payload === null || payload === undefined) return '(empty)';
        try {
            return JSON.stringify(payload, null, 2);
        } catch {
            return typeof payload === 'bigint' ? String(payload) : '[unserialisable]';
        }
    }

    async function reload(nextPage: number) {
        loading.value = true;
        loadError.value = null;
        try {
            const result = await auditApi.listAsync({
                ...filters,
                page: nextPage,
                size: size.value,
            });
            rows.value = result.items;
            total.value = result.total;
            page.value = nextPage;
        } catch (err) {
            loadError.value = err instanceof Error ? err.message : String(err);
        } finally {
            loading.value = false;
        }
    }

    function clearFilters() {
        for (const key of Object.keys(filters)) {
            // @ts-expect-error AuditFilters is a flat record of optional strings
            filters[key] = undefined;
        }
        void reload(1);
    }

    async function openDetail(row: AuditEvent) {
        try {
            detail.value = await auditApi.getAsync(row.audit_event_id);
            detailOpen.value = true;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't load that event.",
                caption: err instanceof Error ? err.message : String(err),
            });
        }
    }

    function findRelated(requestId: string | null) {
        if (!requestId) return;
        detailOpen.value = false;
        filters.request_id = requestId;
        void reload(1);
    }

    function exportCsv() {
        const header = [
            'occurred_at', 'severity', 'action', 'actor_username',
            'actor_user_id', 'actor_ip', 'entity_type', 'entity_id', 'request_id',
            'payload',
        ];
        const escape = (value: unknown) => {
            let s: string;
            if (value === null || value === undefined) s = '';
            else if (typeof value === 'string') s = value;
            else if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint')
                s = String(value);
            else s = JSON.stringify(value) ?? '';
            return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        };
        const lines = [header.join(',')];
        for (const row of rows.value) {
            lines.push([
                row.occurred_at,
                row.severity,
                row.action,
                row.actor_username ?? '',
                row.actor_user_id ?? '',
                row.actor_ip ?? '',
                row.entity_type ?? '',
                row.entity_id ?? '',
                row.request_id ?? '',
                row.payload === null || row.payload === undefined
                    ? ''
                    : JSON.stringify(row.payload),
            ].map(escape).join(','));
        }
        const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `audit-events-${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
    }

    // ── Retention ────────────────────────────────────────────────────
    const {
        draft: retention, save: saveRetention,
    } = useAppSettingDrafts({ audit_retention_days: 365 });

    function onSaveRetention() {
        void saveRetention(
            { audit_retention_days: Number(retention.audit_retention_days) },
            'Audit retention saved.',
        );
    }

    onMounted(() => {
        void reload(1);
    });
</script>

<style scoped lang="scss">
    .audit-filters { padding: 4px 0 12px; }
    .audit-payload {
        background: var(--surface-sunken);
        border-radius: 4px;
        padding: 12px;
        /* A6 — scale token (was fixed 12px). */
        font-size: var(--font-size-xs);
        white-space: pre-wrap;
        max-height: 360px;
        overflow: auto;
    }
    /* `classes: 'text-mono'` lands on cells q-table renders itself, outside this
       component's scope attribute, so the rule has to reach through. */
    :deep(.text-mono) {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: var(--font-size-xs);
    }
</style>
