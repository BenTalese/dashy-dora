import AxiosHttpClient from './axiosHttpClient';

export type AddCandidate = {
    stock_item_id: string;
    name: string;
    location: string | null;
    stock_level: string | null;
};

export type AddItemStatus = 'ready' | 'ambiguous' | 'too_many' | 'not_found';

export type AddPlanItem = {
    query: string;
    quantity: number | null;
    status: AddItemStatus;
    candidates: AddCandidate[];
};

export type AddToShoppingListAction = {
    type: 'add_to_shopping_list';
    no_primary: boolean;
    shopping_list: { id: string; name: string } | null;
    items: AddPlanItem[];
};

// Confirm-style actions: one summary sentence + a single Confirm/Cancel
// button on the frontend. `status` other than 'ready' means the model is
// asking back / not proposing; the chat just shows the summary text and
// no action card.
export type ConfirmActionStatus = 'ready' | 'ambiguous' | 'not_found' | 'invalid';

// Mirrors `confirm_actions.PROPOSERS` on the server, one member per key;
// `test_assistant_tool_registry` pins the two lists against each other
// (R-057 — finalisation 11-R8 found three members missing here).
export type ConfirmActionType =
    | 'update_stock_level'
    | 'mark_opened'
    | 'push_expiry'
    | 'tick_shopping_line'
    | 'move_item'
    | 'plan_meal_for_date'
    | 'add_recipe_to_list'
    | 'cook_recipe'
    | 'adjust_recipe_meals'
    | 'trim_list_to_budget';

export type ConfirmAction = {
    type: ConfirmActionType;
    status: ConfirmActionStatus;
    summary: string;
    payload?: Record<string, unknown>;
    candidates?: Array<Record<string, unknown>>;
};

export type PendingAction = AddToShoppingListAction | ConfirmAction;

export type AssistantReply = {
    // When false, the model couldn't be reached — caller should fall back to
    // the rule-based assistant for this turn.
    available: boolean;
    // Reachable, but not a data question — let the local rule engine answer.
    defer_to_local: boolean;
    answer: string | null;
    mood: string;
    navigate_to: { path: string; label: string } | null;
    tool: string | null;
    result_count: number;
    // Present when the model proposed a data change (e.g. add to list). Nothing
    // has been mutated yet — commit via actAsync once any ambiguity is resolved.
    pending_action: PendingAction | null;
};

export type CommitAddItem = { stock_item_id: string; quantity: number | null };

export type CommitResult = {
    added: number;
    already: number;
    missing: number;
    shopping_list_id: string;
    answer: string;
};

export type LlmProviderName = 'ollama' | 'openai' | 'anthropic' | 'gemini';

// One provider's saved config. `has_api_key` is derived server-side (the
// plaintext key never travels back); `verified` is true only after a live
// probe reached the provider with these exact settings.
export type ProviderConfig = {
    provider: LlmProviderName;
    base_url: string | null;
    model: string | null;
    has_api_key: boolean;
    verified: boolean;
    verified_at: string | null;
    /** The endpoint used when the base URL is left empty ('' for Ollama). */
    default_base_url: string;
    /** An example model id for the placeholder. */
    example_model: string;
};

export type UpdateProviderCommand = {
    base_url?: string | null;
    model?: string | null;
    api_key?: string | null;
    clear_api_key?: boolean;
};

export default class AssistantApiService {
    private httpClient = new AxiosHttpClient();

    getStatusAsync = async (): Promise<{ ai_available: boolean; reason: string | null }> =>
        await this.httpClient.get<{ ai_available: boolean; reason: string | null }>('/assistant/status');

    /** This user's saved config for every provider (unconfigured ones come
     *  back with empty fields + `verified: false`). */
    getProvidersAsync = async (): Promise<{ providers: ProviderConfig[] }> =>
        await this.httpClient.get<{ providers: ProviderConfig[] }>('/assistant/providers');

    /** Upsert one provider's details. Any edit resets `verified` server-side —
     *  re-probe to re-verify. Returns the updated provider config. */
    updateProviderAsync = async (
        provider: LlmProviderName,
        command: UpdateProviderCommand,
    ): Promise<ProviderConfig> =>
        await this.httpClient.patch<ProviderConfig, UpdateProviderCommand>(
            `/assistant/providers/${provider}`,
            command,
        );

    /** FU-332 — per-user "Test connection" probe. `api_key === null`
     *  (or omitted) falls back to the user's saved encrypted key for
     *  paid providers — lets the SPA probe without forcing the user
     *  to re-type the masked field. */
    probeAsync = async (command: {
        provider: 'ollama' | 'openai' | 'anthropic' | 'gemini';
        base_url?: string | null;
        model?: string | null;
        api_key?: string | null;
    }): Promise<{ available: boolean; reason: string | null; models: string[] | null }> =>
        await this.httpClient.post<
            { available: boolean; reason: string | null; models: string[] | null },
            typeof command
        >('/assistant/probe', command);

    askAsync = async (message: string, currentPath: string): Promise<AssistantReply> =>
        await this.httpClient.post<AssistantReply>('/assistant/ask', {
            message,
            current_path: currentPath,
        });

    actAsync = async (shoppingListId: string, items: CommitAddItem[]): Promise<CommitResult> =>
        await this.httpClient.post<CommitResult>('/assistant/act', {
            shopping_list_id: shoppingListId,
            items,
        });

    confirmAsync = async (
        type: ConfirmAction['type'],
        payload: Record<string, unknown>,
    ): Promise<{ ok: boolean; answer: string }> =>
        await this.httpClient.post<{ ok: boolean; answer: string }>('/assistant/confirm', {
            type,
            payload,
        });
}
