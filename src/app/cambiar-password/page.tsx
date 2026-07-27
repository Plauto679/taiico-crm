'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchFromApi } from '@/lib/api';

export default function ChangePasswordPage() {
    const router = useRouter();
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmation, setConfirmation] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    async function handleSubmit(event: React.FormEvent) {
        event.preventDefault();
        setError('');
        if (newPassword !== confirmation) {
            setError('Las contraseñas nuevas no coinciden.');
            return;
        }
        setLoading(true);
        try {
            await fetchFromApi('/password/change', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                }),
            });
            await fetch('/api/logout', { method: 'POST', credentials: 'same-origin', cache: 'no-store' });
            window.localStorage.removeItem('taiico_last_activity');
            router.replace('/login');
            router.refresh();
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible cambiar la contraseña.');
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="h-full overflow-y-auto p-6 md:p-10">
            <div className="mx-auto max-w-xl rounded-xl bg-white p-8 shadow-lg">
                <h1 className="text-2xl font-bold text-gray-900">Cambiar contraseña</h1>
                <p className="mt-2 text-sm text-gray-600">
                    Confirma tu contraseña actual y define una nueva de al menos 8 caracteres.
                </p>
                <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
                    <input
                        type="password"
                        required
                        autoComplete="current-password"
                        value={currentPassword}
                        onChange={(event) => setCurrentPassword(event.target.value)}
                        placeholder="Contraseña actual"
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
                    />
                    <input
                        type="password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={newPassword}
                        onChange={(event) => setNewPassword(event.target.value)}
                        placeholder="Nueva contraseña"
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
                    />
                    <input
                        type="password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                        placeholder="Confirmar nueva contraseña"
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
                    />
                    {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                    <div className="flex justify-end gap-3">
                        <button
                            type="button"
                            onClick={() => router.back()}
                            className="rounded-md border border-gray-300 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            disabled={loading}
                            className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                        >
                            {loading ? 'Guardando...' : 'Cambiar contraseña'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
