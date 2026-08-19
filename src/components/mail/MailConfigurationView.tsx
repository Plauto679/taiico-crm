'use client';

import { FormEvent, useEffect, useState } from 'react';
import { fetchFromApi } from '@/lib/api';

type MailStatus = {
    configured: boolean;
    email_address?: string;
    smtp_host?: string;
    smtp_port?: number;
    use_starttls?: boolean;
    last_verified_at?: string | null;
};

export function MailConfigurationView() {
    const [status, setStatus] = useState<MailStatus>({ configured: false });
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        fetchFromApi<MailStatus>('/mail-configuration')
            .then((data) => {
                setStatus(data);
                setEmail(data.email_address || '');
            })
            .catch((err) => setError(err instanceof Error ? err.message : 'No se pudo cargar la configuración'));
    }, []);

    async function save(event: FormEvent) {
        event.preventDefault();
        setBusy(true); setError(''); setMessage('');
        try {
            const data = await fetchFromApi<MailStatus>('/mail-configuration', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email_address: email,
                    app_password: password,
                    smtp_host: 'smtp.gmail.com',
                    smtp_port: 587,
                    use_starttls: true,
                }),
            });
            setStatus(data); setPassword(''); setMessage('Configuración guardada de forma cifrada.');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'No se pudo guardar');
        } finally { setBusy(false); }
    }

    async function testConnection() {
        setBusy(true); setError(''); setMessage('');
        try {
            const result = await fetchFromApi<{ message: string }>('/mail-configuration/test', { method: 'POST' });
            setMessage(result.message);
            const refreshed = await fetchFromApi<MailStatus>('/mail-configuration');
            setStatus(refreshed);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'No se pudo autenticar');
        } finally { setBusy(false); }
    }

    return (
        <div className="grid max-w-5xl gap-6 lg:grid-cols-2">
            <form onSubmit={save} className="space-y-5 rounded-xl bg-white p-6 shadow">
                <div>
                    <h2 className="text-xl font-semibold text-gray-900">Tu cuenta remitente</h2>
                    <p className="mt-1 text-sm text-gray-600">La contraseña se cifra localmente y nunca vuelve a mostrarse.</p>
                </div>
                <label className="block text-sm font-medium text-gray-700">
                    Correo de Gmail
                    <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2" placeholder="usuario@taiico.com" />
                </label>
                <label className="block text-sm font-medium text-gray-700">
                    Contraseña de aplicación
                    <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2" autoComplete="new-password" placeholder="16 caracteres generados por Google" />
                </label>
                <div className="rounded-md bg-gray-50 p-3 text-sm text-gray-600">Servidor: smtp.gmail.com · Puerto: 587 · STARTTLS</div>
                {message && <p className="rounded-md bg-green-50 p-3 text-sm text-green-700">{message}</p>}
                {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                <div className="flex flex-wrap gap-3">
                    <button disabled={busy} className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50">Guardar</button>
                    <button type="button" disabled={busy || !status.configured} onClick={testConnection} className="rounded-md border border-blue-600 px-4 py-2 font-medium text-blue-700 disabled:opacity-50">Probar conexión</button>
                </div>
                <p className="text-sm text-gray-600">
                    Estado: <strong>{status.configured ? 'Configurado' : 'Sin configurar'}</strong>
                    {status.last_verified_at && ` · Verificado: ${new Date(status.last_verified_at).toLocaleString('es-MX')}`}
                </p>
            </form>

            <section className="rounded-xl bg-white p-6 shadow">
                <h2 className="text-xl font-semibold text-gray-900">Cómo obtener el permiso de Gmail</h2>
                <ol start={0} className="mt-4 list-decimal space-y-3 pl-5 text-sm text-gray-700">
                    <li>
                        Intenta entrar a{' '}
                        <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" className="font-medium text-blue-700 hover:underline">
                            Contraseñas de aplicaciones de Google
                        </a>
                        . Si el enlace abre sin problemas, continúa desde el paso 3.
                    </li>
                    <li>Abre la seguridad de tu Cuenta de Google y activa la verificación en dos pasos.</li>
                    <li>En la misma sección, busca “Contraseñas de aplicaciones”. Si tu administrador la deshabilitó, solicítale autorización.</li>
                    <li>Crea una contraseña con el nombre “TAIICO CRM”. Google mostrará una clave de 16 caracteres una sola vez.</li>
                    <li>Copia esa clave aquí. No uses la contraseña normal de tu cuenta de Google.</li>
                    <li>Guarda y usa “Probar conexión”. La prueba solamente autentica; no envía mensajes.</li>
                </ol>
                <a href="https://support.google.com/accounts/answer/185833?hl=es" target="_blank" rel="noreferrer" className="mt-5 inline-block text-sm font-medium text-blue-700 hover:underline">Abrir instrucciones oficiales de Google</a>
            </section>
        </div>
    );
}
