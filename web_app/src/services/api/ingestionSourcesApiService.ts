import AxiosHttpClient from './axiosHttpClient';

export type IngestionSource = {
    id: string;
    label: string;
    enabled: boolean;
    trust: string;
    created_at: string;
    last_used_at: string | null;
    accepted_count: number;
    skipped_count: number;
    failed_count: number;
};

export type CreateIngestionSourceCommand = {
    label: string;
    trust?: string;
};

export type CreateIngestionSourceResult = {
    source: IngestionSource;
    /** The raw bearer token — shown to the admin exactly once. The
     * caller must surface it immediately and warn that it cannot be
     * shown again. */
    key: string;
};

export type UpdateIngestionSourceCommand = {
    label?: string;
    enabled?: boolean;
};

export type IngestionStoreMapping = {
    id: string;
    source_id: string;
    external_name: string;
    store_id: string | null;
    store_name: string | null;
    created_at: string;
    last_seen_at: string | null;
};

export type UpsertStoreMappingCommand = {
    external_name: string;
    store_id: string | null;
};

export default class IngestionSourcesApiService {
    private httpClient = new AxiosHttpClient();

    listAsync = async (): Promise<IngestionSource[]> => {
        const resp = await this.httpClient.get<{ items: IngestionSource[] }>(
            '/ingestion-sources'
        );
        return resp.items;
    };

    createAsync = async (
        command: CreateIngestionSourceCommand
    ): Promise<CreateIngestionSourceResult> =>
        await this.httpClient.post<
            CreateIngestionSourceResult,
            CreateIngestionSourceCommand
        >('/ingestion-sources', command);

    updateAsync = async (
        id: string,
        command: UpdateIngestionSourceCommand
    ): Promise<IngestionSource> =>
        await this.httpClient.patch<IngestionSource, UpdateIngestionSourceCommand>(
            `/ingestion-sources/${id}`,
            command
        );

    deleteAsync = async (id: string): Promise<void> =>
        await this.httpClient.delete<void>(`/ingestion-sources/${id}`);

    listMappingsAsync = async (sourceId: string): Promise<IngestionStoreMapping[]> => {
        const resp = await this.httpClient.get<{ items: IngestionStoreMapping[] }>(
            `/ingestion-sources/${sourceId}/store-mappings`
        );
        return resp.items;
    };

    upsertMappingAsync = async (
        sourceId: string,
        command: UpsertStoreMappingCommand
    ): Promise<IngestionStoreMapping> =>
        await this.httpClient.put<IngestionStoreMapping, UpsertStoreMappingCommand>(
            `/ingestion-sources/${sourceId}/store-mappings`,
            command
        );

    deleteMappingAsync = async (sourceId: string, mappingId: string): Promise<void> =>
        await this.httpClient.delete<void>(
            `/ingestion-sources/${sourceId}/store-mappings/${mappingId}`
        );
}
