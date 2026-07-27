'use client';

import Link from 'next/link';
import { useState } from 'react';
import { fetchFromApi } from '@/lib/api';

export default function ForgotPasswordPage() {
    const [email, setEmail] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    async function handleSubmit(event: React.FormEvent) {
        event.preventDefault();
        setLoading(true);
        setError('');
        setMessage('');
        try {
            const response = await fetchFromApi<{ message: string }>('/password/forgot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            setMessage(response.message);
        } catch (requestError) {
            setError(requestError instanceof Error ? requestError.message : 'No fue posible procesar la solicitud.');
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-100 px-4">
            <div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg">
                <div className="flex flex-col items-center">
                    <img src="/logo.png" alt="TAIICO CRM" className="mb-6 h-16 w-auto" />
                    <h1 className="text-2xl font-bold text-gray-900">Olvidé mi contraseña</h1>
                    <p className="mt-2 text-center text-sm text-gray-600">
                        Ingresa el correo registrado. Si existe, recibirás un enlace temporal.
                    </p>
                </div>
                <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
                    <input
                        type="email"
                        required
                        autoComplete="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        placeholder="correo@taiico.com"
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    {message && <p className="rounded-md bg-green-50 p-3 text-sm text-green-800">{message}</p>}
                    {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                        {loading ? 'Enviando...' : 'Enviar enlace'}
                    </button>
                    <Link href="/login" className="block text-center text-sm text-blue-600 hover:text-blue-800">
                        Volver a iniciar sesión
                    </Link>
                </form>
            </div>
        </div>
    );
}
