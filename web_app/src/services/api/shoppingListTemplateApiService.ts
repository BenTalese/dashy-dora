import type {
    TemplateDetail,
    TemplateSummary,
    UpdateTemplateLineCommand,
} from 'src/models/shoppingListTemplate';
import AxiosHttpClient from './axiosHttpClient';

export type CreateTemplateLineInput = {
    stock_item_id: string;
    quantity?: number | null;
};

export type CreateTemplateCommand = {
    name: string;
    lines?: CreateTemplateLineInput[];
};

export type UpdateTemplateCommand = {
    name?: string;
};

export type AddTemplateLineCommand = {
    stock_item_id: string;
    quantity?: number | null;
};

export type InstantiateCommand = {
    name?: string;
    /** Top up this list instead of creating one; items already on it are skipped. */
    merge_into_list_id?: string;
};

export type InstantiateResult = {
    shopping_list_id: string | null;
    line_count: number;
    skipped_count: number;
};

export type SnapshotCommand = {
    name?: string;
    include_ticked?: boolean;
};

export type SnapshotResult = {
    template_id: string | null;
    line_count: number;
};

export default class ShoppingListTemplateApiService {
    private httpClient = new AxiosHttpClient();

    getAllAsync = async (): Promise<TemplateSummary[]> =>
        await this.httpClient.get<TemplateSummary[]>('/shopping-list-templates');

    getDetailAsync = async (id: string): Promise<TemplateDetail> =>
        await this.httpClient.get<TemplateDetail>(`/shopping-list-templates/${id}`);

    createAsync = async (command: CreateTemplateCommand): Promise<{ template_id: string }> =>
        await this.httpClient.post<{ template_id: string }, CreateTemplateCommand>(
            '/shopping-list-templates',
            command,
        );

    updateAsync = async (id: string, command: UpdateTemplateCommand): Promise<void> =>
        await this.httpClient.patch<void, UpdateTemplateCommand>(
            `/shopping-list-templates/${id}`,
            command,
        );

    deleteAsync = async (id: string): Promise<void> =>
        await this.httpClient.delete<void>(`/shopping-list-templates/${id}`);

    addLineAsync = async (
        id: string,
        command: AddTemplateLineCommand,
    ): Promise<{ line_id: string; already_on_template: boolean }> =>
        await this.httpClient.post<
            { line_id: string; already_on_template: boolean },
            AddTemplateLineCommand
        >(`/shopping-list-templates/${id}/lines`, command);

    deleteLineAsync = async (id: string, lineId: string): Promise<void> =>
        await this.httpClient.delete<void>(`/shopping-list-templates/${id}/lines/${lineId}`);

    updateLineAsync = async (
        id: string,
        lineId: string,
        command: UpdateTemplateLineCommand,
    ): Promise<void> =>
        await this.httpClient.patch<void, UpdateTemplateLineCommand>(
            `/shopping-list-templates/${id}/lines/${lineId}`,
            command,
        );

    instantiateAsync = async (id: string, command: InstantiateCommand): Promise<InstantiateResult> =>
        await this.httpClient.post<InstantiateResult, InstantiateCommand>(
            `/shopping-list-templates/${id}/instantiate`,
            command,
        );

    snapshotFromListAsync = async (
        sourceListId: string,
        command: SnapshotCommand,
    ): Promise<SnapshotResult> =>
        await this.httpClient.post<SnapshotResult, SnapshotCommand>(
            `/shopping-list-templates/from-list/${sourceListId}`,
            command,
        );
}
