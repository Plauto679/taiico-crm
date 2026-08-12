'use client';

import { useMemo, useState } from 'react';
import {
    AccessModuleConfig,
    AccessPermission,
    AccessUser,
    AccessUserInput,
    createAccessUser,
    deleteAccessUser,
    updateAccessUser,
} from '@/modules/accesos/service';

const EMPTY_USER: AccessUserInput = {
    username: '',
    password: '',
    role: 'agente',
    promotorias: [],
    rfc: '',
    aseguradoras: [],
    module_permissions: {},
};

function permissionLabel(permission: string) {
    if (permission === 'operacion') return 'Operación';
    if (permission === 'lectura') return 'Lectura';
    return 'Ninguno';
}

function toInput(user: AccessUser): AccessUserInput {
    return {
        username: user.username,
        password: '',
        role: user.role,
        promotorias: user.promotorias,
        rfc: user.rfc,
        aseguradoras: user.aseguradoras,
        module_permissions: user.module_permissions,
    };
}

export function AccesosView({
    initialUsers,
    modules,
    promotorias,
}: {
    initialUsers: AccessUser[];
    modules: AccessModuleConfig[];
    promotorias: string[];
}) {
    const [users, setUsers] = useState(initialUsers);
    const [editing, setEditing] = useState<AccessUserInput | null>(null);
    const [isCreate, setIsCreate] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const activeModules = useMemo(
        () => modules.filter((module) => module.key !== 'inicio'),
        [modules],
    );

    function openCreate() {
        setError('');
        setIsCreate(true);
        setEditing({
            ...EMPTY_USER,
            module_permissions: Object.fromEntries(
                modules.map((module) => [module.key, 'ninguno']),
            ),
        });
    }

    function openEdit(user: AccessUser) {
        setError('');
        setIsCreate(false);
        setEditing(toInput(user));
    }

    function updateField<K extends keyof AccessUserInput>(field: K, value: AccessUserInput[K]) {
        if (!editing) return;
        setEditing({ ...editing, [field]: value });
    }

    function togglePromotoria(promotoria: string) {
        if (!editing) return;
        const current = new Set(editing.promotorias);
        if (current.has(promotoria)) current.delete(promotoria);
        else current.add(promotoria);
        updateField('promotorias', Array.from(current));
    }

    function updateModulePermission(module: string, permission: AccessPermission) {
        if (!editing) return;
        updateField('module_permissions', {
            ...editing.module_permissions,
            [module]: permission,
        });
    }

    async function save() {
        if (!editing || saving) return;
        setSaving(true);
        setError('');
        try {
            const payload = {
                ...editing,
                password: editing.password?.trim() ? editing.password : undefined,
            };
            const response = isCreate
                ? await createAccessUser(payload)
                : await updateAccessUser(payload);
            setUsers((current) => {
                const withoutUser = current.filter(
                    (user) => user.username !== response.user.username,
                );
                return [...withoutUser, response.user].sort((a, b) => a.username.localeCompare(b.username));
            });
            setEditing(null);
        } catch (saveError) {
            setError(saveError instanceof Error ? saveError.message : 'No se pudo guardar el usuario');
        } finally {
            setSaving(false);
        }
    }

    async function removeUser(username: string) {
        if (!window.confirm(`¿Eliminar el usuario ${username}?`)) return;
        setError('');
        await deleteAccessUser(username);
        setUsers((current) => current.filter((user) => user.username !== username));
    }

    return (
        <div className="flex h-full min-h-0 flex-col gap-4">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Accesos</h1>
                    <p className="text-sm text-blue-100">
                        Administra usuarios, roles, promotorías y permisos por módulo.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={openCreate}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-700"
                >
                    Crear usuario
                </button>
            </div>

            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            <div className="min-h-0 overflow-auto rounded-xl bg-white shadow">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                        <tr>
                            <th className="px-4 py-3">Usuario</th>
                            <th className="px-4 py-3">Rol</th>
                            <th className="px-4 py-3">Promotoría</th>
                            <th className="px-4 py-3">RFC</th>
                            <th className="px-4 py-3">Módulos activos</th>
                            <th className="px-4 py-3 text-right">Acciones</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                        {users.map((user) => {
                            const enabledModules = activeModules.filter(
                                (module) => user.module_permissions[module.key] !== 'ninguno',
                            );
                            return (
                                <tr key={user.username} className="hover:bg-slate-50">
                                    <td className="px-4 py-3 font-medium text-slate-900">{user.username}</td>
                                    <td className="px-4 py-3 capitalize">{user.role}</td>
                                    <td className="px-4 py-3">{user.promotorias.join(', ') || '—'}</td>
                                    <td className="px-4 py-3">{user.rfc || '—'}</td>
                                    <td className="px-4 py-3">
                                        {enabledModules.length
                                            ? enabledModules.map((module) => module.label).join(', ')
                                            : 'Sin módulos'}
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <button
                                            type="button"
                                            onClick={() => openEdit(user)}
                                            className="mr-3 text-sm font-semibold text-blue-600 hover:text-blue-800"
                                        >
                                            Editar
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => removeUser(user.username)}
                                            className="text-sm font-semibold text-red-600 hover:text-red-800"
                                        >
                                            Eliminar
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {editing && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-6">
                    <div className="flex max-h-[90vh] w-full max-w-5xl flex-col rounded-2xl bg-white shadow-2xl">
                        <div className="border-b px-6 py-4">
                            <h2 className="text-lg font-bold text-slate-900">
                                {isCreate ? 'Crear usuario' : 'Editar usuario'}
                            </h2>
                            <p className="text-sm text-slate-500">
                                Los cambios se guardan en el archivo maestro de accesos en Drive.
                            </p>
                        </div>
                        <div className="grid gap-4 overflow-y-auto px-6 py-5 md:grid-cols-2">
                            <label className="text-sm font-semibold text-slate-700">
                                Usuario
                                <input
                                    value={editing.username}
                                    onChange={(event) => updateField('username', event.target.value)}
                                    disabled={!isCreate}
                                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
                                />
                            </label>
                            <label className="text-sm font-semibold text-slate-700">
                                Contraseña {isCreate ? '' : '(opcional)'}
                                <input
                                    type="password"
                                    value={editing.password || ''}
                                    onChange={(event) => updateField('password', event.target.value)}
                                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
                                />
                            </label>
                            <label className="text-sm font-semibold text-slate-700">
                                Rol
                                <select
                                    value={editing.role}
                                    onChange={(event) => updateField('role', event.target.value as AccessUserInput['role'])}
                                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
                                >
                                    <option value="admin">Admin</option>
                                    <option value="agente">Agente</option>
                                </select>
                            </label>
                            <label className="text-sm font-semibold text-slate-700">
                                RFC
                                <input
                                    value={editing.rfc}
                                    onChange={(event) => updateField('rfc', event.target.value)}
                                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal uppercase"
                                />
                            </label>
                            <label className="text-sm font-semibold text-slate-700 md:col-span-2">
                                Aseguradoras
                                <input
                                    value={editing.aseguradoras.join(', ')}
                                    onChange={(event) => updateField(
                                        'aseguradoras',
                                        event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
                                    )}
                                    placeholder="Ej. METLIFE, SURA"
                                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
                                />
                            </label>
                            <div className="md:col-span-2">
                                <p className="mb-2 text-sm font-semibold text-slate-700">Promotoría</p>
                                <div className="flex flex-wrap gap-2">
                                    {promotorias.map((promotoria) => (
                                        <label key={promotoria} className="flex items-center gap-2 rounded-full border px-3 py-2 text-sm">
                                            <input
                                                type="checkbox"
                                                checked={editing.promotorias.includes(promotoria)}
                                                onChange={() => togglePromotoria(promotoria)}
                                            />
                                            {promotoria}
                                        </label>
                                    ))}
                                </div>
                            </div>
                            <div className="md:col-span-2">
                                <p className="mb-2 text-sm font-semibold text-slate-700">Permisos por módulo</p>
                                <div className="grid gap-3 md:grid-cols-3">
                                    {activeModules.map((module) => (
                                        <label key={module.key} className="text-sm font-semibold text-slate-700">
                                            {module.label}
                                            <select
                                                value={editing.module_permissions[module.key] || 'ninguno'}
                                                onChange={(event) => updateModulePermission(
                                                    module.key,
                                                    event.target.value as AccessPermission,
                                                )}
                                                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
                                            >
                                                <option value="ninguno">{permissionLabel('ninguno')}</option>
                                                <option value="lectura">{permissionLabel('lectura')}</option>
                                                <option value="operacion">{permissionLabel('operacion')}</option>
                                            </select>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        </div>
                        <div className="flex justify-end gap-3 border-t px-6 py-4">
                            <button
                                type="button"
                                onClick={() => setEditing(null)}
                                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
                            >
                                Cancelar
                            </button>
                            <button
                                type="button"
                                onClick={save}
                                disabled={saving}
                                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                            >
                                {saving ? 'Guardando...' : 'Guardar'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
