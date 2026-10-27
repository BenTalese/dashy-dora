<template>
    <BaseDialog
        :model-value="modelValue"
        title="What the colours and outlines mean"
        closable
        card-style="width: 720px; max-width: 95vw"
        @update:model-value="emit('update:modelValue', $event)"
    >
        <q-card-section class="dora-attention-help">
            <p class="text-body2 q-mb-md">
                A stock row speaks four things, and only four: the
                <strong>level box</strong> (its colour, and whether its edge is
                dashed), the <strong>row treatment</strong> (outlined, plain or
                dimmed), the
                <strong>essential edge stripe</strong>, and the
                <strong>expiry button</strong> (with the open/sealed toggle
                beside it). The same rules also drive the
                "<em>Needs attention</em>" count in the footer and its
                matching filter chip, so what you see highlighted is
                exactly what the count is counting.
            </p>

            <!-- ── At-a-glance legend ─────────────────────────────────
                 2026-08-15 feedback: this used to live in the stock
                 overview's filter panel, which is not where a reference
                 belongs — but its visual examples were the good part, so
                 the component moves here intact rather than being
                 reworded into prose.
                 It also replaces the hand-written level table that sat
                 here: that table hardcoded three level names and their
                 colours, so a household that renamed a level (or added a
                 fourth) was read the wrong thing. StockRowLegend derives
                 both from the live level rows via the same
                 `colourForSequence` authority the row itself uses (R-003),
                 so this page cannot drift from what it documents. -->
            <StockRowLegend :levels="stockLevels" />

            <!-- ── Outline & dim ──────────────────────────────────────
                 One tier, not two. This used to describe an amber "warn"
                 outline and a red "alert" one; a hedged alarm gets ignored,
                 and amber sat directly around the amber Low level square.
                 The copy follows the code (D-7) rather than the code being
                 left to disagree with the help page. -->
            <h6 class="q-mt-lg q-mb-sm">Row outline</h6>
            <p class="text-body2 q-mb-sm dora-text-secondary">
                An outlined row needs you. There's one outline, and it means
                one thing. Three conditions turn it on:
            </p>

            <q-list bordered separator class="rounded-borders">
                <q-item class="dora-attention-sample dora-attention-sample--alert">
                    <q-item-section>
                        <q-item-label class="text-weight-medium text-negative">
                            Needs attention
                        </q-item-label>
                        <q-item-label caption>
                            The item has <strong>expired</strong>, it's
                            <strong>expiring soon</strong> (your setting decides
                            how soon), or it's flagged <strong>essential</strong>
                            and has run low or out.
                        </q-item-label>
                    </q-item-section>
                </q-item>
            </q-list>

            <p class="text-body2 q-mt-sm dora-text-secondary">
                That's the same set the <em>Needs attention</em> count and its
                filter chip use, and the same set the bell counts. Turning a
                kind off under Settings → Notifications turns off its outline
                too.
            </p>

            <!-- ── Essential ──────────────────────────────────────── -->
            <h6 class="q-mt-lg q-mb-sm">Essential items</h6>
            <p class="text-body2 q-mb-sm dora-text-secondary">
                Items you mark <strong>essential</strong> get a stripe down the
                left edge of the row. You set it on the item's own page.
                Essentials are the only items whose stock level drives an
                outline. A non-essential item running Low or Out stays quiet,
                because the level square already says so.
            </p>
            <q-card flat bordered class="dora-attention-essential-sample">
                <q-card-section class="row items-center">
                    <q-icon :name="ICONS.flag" color="secondary" size="20px" class="q-mr-sm" />
                    <span class="text-body2">A flagged item, full opacity, with the left stripe.</span>
                </q-card-section>
            </q-card>

            <!-- ── Dim ────────────────────────────────────────────── -->
            <h6 class="q-mt-lg q-mb-sm">Dimmed rows</h6>
            <p class="text-body2 q-mb-sm dora-text-secondary">
                An item is <strong>faded</strong> when it's Out of stock
                <em>and</em> not flagged essential. The fade quietly says
                "depleted, nothing to do". Out essentials stay full
                opacity.
            </p>

            <!-- ── The dashed level box (D-5) ─────────────────────────
                 This section used to describe THREE ring indicators: an
                 amber ring for Dora's belief, a pulsing accent ring for
                 "due a count", and a green/amber/red ring on the cart for
                 the buy verdict. The verdict came off the row entirely
                 (D-10) and the other two collapsed into one dashed edge
                 (D-5) — because to a reader they said the same thing, and a
                 row can't carry three ring vocabularies and stay
                 readable. 2026-08-22: that one marker moved back off the box
                 edge to an offset ring (it wasn't loud enough inset), but it
                 is still exactly one marker with one meaning. -->
            <h6 class="q-mt-lg q-mb-sm">A dashed ring around the level</h6>
            <p class="text-body2 q-mb-sm dora-text-secondary">
                One marker, one meaning: <strong>this number might be out of
                date</strong>. The level's colour still tells you what's
                recorded. Open the picker and its header says which of the two
                reasons applies:
            </p>
            <q-list bordered separator class="rounded-borders">
                <q-item>
                    <q-item-section avatar>
                        <q-icon :name="ICONS.dora_voice" color="warning" size="22px" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label class="text-weight-medium">
                            "Dora thinks…": she disagrees with the level
                        </q-item-label>
                        <q-item-label caption>
                            Dora works out what you probably have from your
                            purchases, how often you rebuy, and what you've
                            cooked. She never changes your recorded level, and
                            says nothing when she agrees with it. Turn the hint
                            off in Settings → Assistant.
                        </q-item-label>
                    </q-item-section>
                </q-item>
                <q-item>
                    <q-item-section avatar>
                        <q-icon :name="ICONS.fact_check" color="warning" size="22px" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label class="text-weight-medium">
                            Due for a stocktake check
                        </q-item-label>
                        <q-item-label caption>
                            It's been long enough since this item was counted
                            that the recorded level is a guess. Set it from the
                            picker, or walk the whole queue from the Stocktake
                            button, which carries the number due. That button
                            <strong>glows only when one of the items due is
                            flagged essential</strong>.
                        </q-item-label>
                    </q-item-section>
                </q-item>
            </q-list>

            <!-- ── Expiry + open (Chunk 4) ────────────────────────────── -->
            <h6 class="q-mt-lg q-mb-sm">The expiry button</h6>
            <p class="text-body2 q-mb-sm dora-text-secondary">
                Its <strong>colour</strong> is the expiry date: green fine,
                amber soon, red gone, grey none set. Tap it to set a date, push
                one by a day or a fortnight, clear it, or log the item as
                waste. Next to it, the <strong>open / in-use</strong> toggle:
                marking something open asks you for a revised date, because an
                opened jar and a sealed one don't keep for the same time.
            </p>

            <!-- ── Cheat sheet ────────────────────────────────────── -->
            <h6 class="q-mt-lg q-mb-sm">Cheat sheet</h6>
            <table class="dora-attention-table">
                <thead>
                    <tr>
                        <th>State</th>
                        <th>Row treatment</th>
                        <th>Counts as "Needs attention"</th>
                        <th>Where it sorts</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="r in cheatRows" :key="r.state">
                        <td>{{ r.state }}</td>
                        <td>
                            <span v-if="r.band === 0" class="text-negative text-weight-medium">outlined</span>
                            <span v-else-if="r.band === 2" class="dora-text-muted">dimmed</span>
                            <span v-else class="dora-text-muted">plain</span>
                        </td>
                        <td>
                            <q-icon
                                :name="r.band === 0 ? ICONS.check : ICONS.close"
                                :color="r.band === 0 ? 'positive' : undefined"
                                size="18px"
                            />
                        </td>
                        <td class="dora-text-muted">{{ BAND_POSITION[r.band] }}</td>
                    </tr>
                </tbody>
            </table>
        </q-card-section>

        <template #actions>
            <BaseButton variant="primary" label="Got it" @click="emit('update:modelValue', false)" />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    import { onMounted } from 'vue';
    import { storeToRefs } from 'pinia';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import StockRowLegend from 'src/components/stock/StockRowLegend.vue';
    import { attentionBand } from 'src/composables/useStockFilters';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { ICONS } from 'src/style/icons';

    defineProps<{ modelValue: boolean }>();
    const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

    // The legend renders the household's REAL level rows (renames included),
    // so this dialog has to have them. Help is reachable without visiting
    // Stock first, so it can't assume the store is already hydrated.
    const stockLevelStore = useStockLevelStore();
    const { stockLevels } = storeToRefs(stockLevelStore);
    onMounted(() => {
        void stockLevelStore.ensureLoadedAsync();
    });

    /**
     * One column, not three (D-8): the treatments are bands on ONE scale, so
     * an item is in exactly one of them. Each row states the inputs and the
     * band comes from `attentionBand()` itself (0 outlined, 1 plain, 2 dimmed),
     * so the table cannot disagree with the stock row. Position in the default
     * sort is a property of the band, which is the whole point of the scale.
     */
    const BAND_POSITION = ['top', 'middle', 'bottom'] as const;

    type CheatInput = { state: string; needsAttention: boolean; essential: boolean; out: boolean };
    const CHEAT_INPUTS: CheatInput[] = [
        { state: 'Stocked, no expiry issue', needsAttention: false, essential: false, out: false },
        { state: 'Low, not essential', needsAttention: false, essential: false, out: false },
        { state: 'Low, essential', needsAttention: true, essential: true, out: false },
        { state: 'Out, not essential', needsAttention: false, essential: false, out: true },
        { state: 'Out, essential', needsAttention: true, essential: true, out: true },
        { state: 'Expiring inside your window (any item)', needsAttention: true, essential: false, out: false },
        { state: 'Expired (any item)', needsAttention: true, essential: false, out: false },
        // Attention wins over the dim: expired is something to act on, so
        // the row is outlined and full opacity even though it's also out.
        { state: 'Expired + Out, not essential', needsAttention: true, essential: false, out: true },
    ];
    const cheatRows = CHEAT_INPUTS.map((r) => ({
        state: r.state,
        band: attentionBand({ needs_attention: r.needsAttention, is_essential: r.essential }, r.out),
    }));
</script>

<style scoped lang="scss">
    .dora-attention-help h6 {
        font-weight: 600;
    }
    .dora-attention-sample {
        border-left: 4px solid transparent;
    }
    .dora-attention-sample--alert {
        border-left-color: var(--semantic-negative);
        box-shadow: inset 0 0 0 1px var(--semantic-negative);
    }
    .dora-attention-essential-sample {
        position: relative;
        overflow: hidden;
    }
    .dora-attention-essential-sample::before {
        content: '';
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        /* Matches StockItemRow's real stripe — 6px, secondary-toned. It was
           3px and warning-amber here, i.e. a different width in a colour the
           row stopped using when essential moved onto the secondary tone. */
        width: 6px;
        background: var(--brand-secondary-strong);
    }
    .dora-attention-table {
        width: 100%;
        border-collapse: collapse;
        font-size: calc(var(--font-size-sm) * 1rem);
    }
    .dora-attention-table th,
    .dora-attention-table td {
        text-align: left;
        padding: var(--space-2) var(--space-3);
        border-bottom: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .dora-attention-table th {
        font-weight: 600;
        background: color-mix(in srgb, var(--text-primary) 4%, transparent);
    }
</style>
