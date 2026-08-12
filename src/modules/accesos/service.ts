import { fetchFromApi } from '@/lib/api';

export type AccessPermission = 'ninguno' | 'lectura' | 'operacion';
export type AccessRole = 'admin' | 'agente';

export interface AccessModuleConfig {
    key: string;
    label: string;
    column: string;
}

export interface AccessUser {
    username: string;
    role: AccessRole;
    promotorias: string[];
    rfc: string;
    aseguradoras: string[];
    module_permissions: Record<string, AccessPermission>;
    has_password: boolean;
}

export interface AccessUserInput {
    username: string;
    password?: string;
    role: AccessRole;
    promotorias: string[];
    rfc: string;
    aseguradoras: string[];
    module_permissions: Record<string, AccessPermission>;
}

export function getAccessConfig(): Promise<{
    modules: AccessModuleConfig[];
    promotorias: string[];
    roles: AccessRole[];
    permissions: { key: AccessPermission; label: string }[];
}> {
    return fetchFromApi('/accesos/config');
}

export function getAccessUsers(): Promise<{ users: AccessUser[] }> {
    return fetchFromApi('/accesos/users');
}

export function createAccessUser(input: AccessUserInput): Promise<{ user: AccessUser }> {
    return fetchFromApi('/accesos/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
    });
}

export function updateAccessUser(input: AccessUserInput): Promise<{ user: AccessUser }> {
    return fetchFromApi(`/accesos/users/${encodeURIComponent(input.username)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
    });
}

export function deleteAccessUser(username: string): Promise<{ success: boolean }> {
    return fetchFromApi(`/accesos/users/${encodeURIComponent(username)}`, {
        method: 'DELETE',
    });
}
