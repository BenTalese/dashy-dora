import type { LocationKind, LocationNode } from 'src/models/location';
import AxiosHttpClient, { type CreatedResponse } from './axiosHttpClient';

export type CreateLocationCommand = {
    name: string;
    kind: LocationKind;
    parent_id: string | null;
    sequence?: number;
};

export type UpdateLocationCommand = {
    name?: string;
    sequence?: number;
    parent_id?: string | null;
};

export default class LocationApiService {
    private httpClient = new AxiosHttpClient();

    getTreeAsync = async (): Promise<LocationNode[]> =>
        await this.httpClient.get<LocationNode[]>('/locations');

    /** Stock items with no location, which the tree can't show (FU-633). */
    getUnassignedCountAsync = async (): Promise<number> =>
        (await this.httpClient.get<{ count: number }>('/locations/unassigned-count')).count;

    createAsync = async (command: CreateLocationCommand): Promise<CreatedResponse> =>
        await this.httpClient.post<CreatedResponse>('/locations', command);

    updateAsync = async (locationId: string, command: UpdateLocationCommand): Promise<void> =>
        await this.httpClient.patch<void>(`/locations/${locationId}`, command);

    deleteAsync = async (locationId: string): Promise<void> =>
        await this.httpClient.delete<void>(`/locations/${locationId}`);
}
