import AxiosHttpClient from './axiosHttpClient';
import { createQueryString, fetchAllPages, type Page } from './queryStringBuilder';

export type AdminUser = {
    user_id: string;
    username: string;
    email: string | null;
    is_admin: boolean;
    // Deactivate-instead-of-delete: an inactive account keeps all its data
    // but can't sign in.
    is_active: boolean;
    send_deals_on_day: number;
    deals_email_enabled: boolean;
    // Settings rebuild Phase 4 — whether the user has a profile picture
    // (bulk-stamped server-side; bytes fetched via /users/<id>/image).
    has_image: boolean;
};

export type AdminUpdateUserCommand = {
    username?: string;
    email?: string | null;
    is_admin?: boolean;
    is_active?: boolean;
    deals_email_enabled?: boolean;
};

// admin-create counterpart to `/auth/register`. No verification email; the
// admin implicitly vouches. `password` set ⇒ that's the password and the
// response carries none back; omitted ⇒ the server mints a one-time password
// and returns it once for the admin to relay out-of-band.
export type AdminCreateUserCommand = {
    username: string;
    email?: string | null;
    is_admin?: boolean;
    password?: string;
};

// `new_password` is null whenever the admin chose the password themselves —
// there's nothing to hand back that they don't already have.
export type CreateUserResult = { user_id: string; new_password: string | null };

export type SetPasswordResult = { new_password: string | null };

export default class UserAdminApiService {
    private httpClient = new AxiosHttpClient();

    /** Every account, paged, so the admin list never stops at the default
     *  page of 50 (finalisation 13-R5). */
    getAllPagesAsync = async (): Promise<AdminUser[]> =>
        await fetchAllPages((page, limit) =>
            this.httpClient.get<Page<AdminUser>>(`/users${createQueryString([], undefined, { page, limit })}`),
        );

    createAsync = async (
        command: AdminCreateUserCommand,
    ): Promise<CreateUserResult> =>
        await this.httpClient.post<CreateUserResult, AdminCreateUserCommand>(
            '/users',
            command,
        );

    updateAsync = async (
        userId: string,
        command: AdminUpdateUserCommand
    ): Promise<void> =>
        await this.httpClient.patch<void, AdminUpdateUserCommand>(
            `/users/${userId}`,
            command
        );

    deleteAsync = async (userId: string): Promise<void> =>
        await this.httpClient.delete(`/users/${userId}`);

    // `password` omitted ⇒ server generates one and returns it.
    setPasswordAsync = async (
        userId: string,
        password?: string,
    ): Promise<SetPasswordResult> =>
        await this.httpClient.post<SetPasswordResult, { password?: string }>(
            `/users/${userId}/reset-password`,
            password ? { password } : {},
        );
}
