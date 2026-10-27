import AxiosHttpClient from './axiosHttpClient';

/** P2-04 — Dora suggestion inbox. The endpoint generates fresh
 *  proposals each call (filtered against the user's dismiss/snooze
 *  list) so the SPA can poll cheaply and never have to manage
 *  per-suggestion lifecycle state. */

export type SuggestionKind =
    | 'use_soon'
    | 'over_budget'
    | 'likely_due'
    | 'frequent_waster'
    | 'pantry_check'
    | 'reconcile_meals_pending';

export type SuggestionSeverity = 'high' | 'medium' | 'low';

export type SuggestionAction = {
    path: string;
    label: string;
};

export type DoraSuggestion = {
    // Known kinds keep their autocomplete; `string & {}` admits forward-compat
    // server kinds without collapsing the union to a bare `string`.
    kind: SuggestionKind | (string & {});
    dedup_key: string;
    severity: SuggestionSeverity;
    title: string;
    body: string;
    /** Plain-English why-line. Rendered as a "Why?" expander; also fed
     *  to the assistant if the user asks Dora to explain. */
    reason: string;
    primary_action: SuggestionAction | null;
    payload: Record<string, unknown>;
};

export type SuggestionsResponse = {
    suggestions: DoraSuggestion[];
    count: number;
};

export type DismissCommand = { kind: string; dedup_key: string };
export type SnoozeCommand = { kind: string; dedup_key: string; hours: number };

export default class SuggestionsApiService {
    private httpClient = new AxiosHttpClient();

    listAsync = async (): Promise<SuggestionsResponse> =>
        await this.httpClient.get<SuggestionsResponse>('/suggestions');

    dismissAsync = async (command: DismissCommand): Promise<void> =>
        await this.httpClient.post<void, DismissCommand>(
            '/suggestions/dismiss',
            command,
        );

    snoozeAsync = async (command: SnoozeCommand): Promise<void> =>
        await this.httpClient.post<void, SnoozeCommand>(
            '/suggestions/snooze',
            command,
        );

    unsuppressAsync = async (command: DismissCommand): Promise<void> =>
        await this.httpClient.post<void, DismissCommand>(
            '/suggestions/unsuppress',
            command,
        );
}
