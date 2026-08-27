import { useState, useEffect } from 'react';
import { X, Mail } from 'lucide-react';
import { sendRenewalEmail } from '@/modules/renovaciones/service';
import { searchClient } from '@/modules/clientes/service';

const RENEWAL_STATUS_OPTIONS = [
    'Renovado Automático',
    'Renovada Manual',
    'Enviada Manual',
    'Enviado Automáticamente',
    'Revision Manual Necesaria',
] as const;

interface EditStatusModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (newStatus: string | null, expediente: string | null, email: string | null) => Promise<void>;
    onEmailSent: () => Promise<void>;
    currentStatus?: string | null;
    currentExpediente?: string | null;
    currentEmail?: string | null;
    policyNumber: string;
    insurer: string;
    type: string;
    clientName: string;
    endDate: string;
}

export const EditStatusModal = ({
    isOpen,
    onClose,
    onSave,
    onEmailSent,
    currentStatus,
    currentExpediente,
    currentEmail,
    policyNumber,
    insurer,
    type,
    clientName,
    endDate
}: EditStatusModalProps) => {
    const [status, setStatus] = useState<string | null>(currentStatus || null);
    const [expediente, setExpediente] = useState<string>(currentExpediente || '');
    const [email, setEmail] = useState<string>(currentEmail || '');
    const [registeredEmail, setRegisteredEmail] = useState<string | null>(null);
    const [isSending, setIsSending] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    useEffect(() => {
        setStatus(currentStatus || null);
        setExpediente(currentExpediente || '');
        setEmail(currentEmail || '');
        setIsSending(false);
        setIsSaving(false);
        setRegisteredEmail(null);

        // Fetch registered email if modal is open
        if (isOpen && clientName) {
            searchClient(clientName).then(res => {
                if (res && res.email) {
                    setRegisteredEmail(res.email);
                }
            }).catch(err => console.error("Error searching client:", err));
        }
    }, [currentStatus, currentExpediente, currentEmail, isOpen, clientName]);

    if (!isOpen) return null;

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave(status, expediente || null, email || null);
            onClose();
        } catch (error: any) {
            console.error('Failed to update renewal', error);
            alert('Error al actualizar la póliza: ' + (error.message || 'Desconocido'));
        } finally {
            setIsSaving(false);
        }
    };

    const handleSendEmail = async () => {
        // Determine effective email
        const effectiveEmail = email ? email : registeredEmail;

        let confirmMsg = "";

        if (effectiveEmail) {
            confirmMsg = `¿Enviar correo de renovación a ${clientName} (${effectiveEmail})?`;
        } else {
            confirmMsg = `Ningún correo registrado, Favor de agregarl el Email en el registro agregarlo en la base de clientes.`;
            // User requested this text specifically. It serves as a warning.
            // Should we allow proceed?
            // Since backend will fail, maybe just show alert?
            // But user wording "Instead of writing... you can put..." implies replacement of the question.
            // If we assume it's a blocking alert:
            alert(confirmMsg);
            return;
        }

        if (!confirm(confirmMsg)) return;

        setIsSending(true);
        try {
            await sendRenewalEmail(
                insurer,
                type,
                policyNumber,
                clientName,
                endDate,
                expediente
            );
            await onEmailSent();
            alert('Correo enviado exitosamente.');
            onClose();
        } catch (error: any) {
            console.error('Failed to send email', error);
            alert('Error al enviar correo: ' + (error.message || 'Desconocido'));
        } finally {
            setIsSending(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-2 sm:p-4">
            <div className="max-h-[calc(100dvh-1rem)] w-full max-w-md overflow-y-auto rounded-lg bg-white p-4 shadow-xl sm:p-6">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-medium text-gray-900">
                        Actualizar Póliza
                    </h3>
                    <button
                        onClick={onClose}
                        disabled={isSending || isSaving}
                        className="text-gray-400 hover:text-gray-500"
                    >
                        <X className="h-6 w-6" />
                    </button>
                </div>

                <div className="space-y-4">
                    <div>
                        <p className="text-sm text-gray-500">Aseguradora: <span className="font-medium text-gray-900">{insurer}</span></p>
                        <p className="text-sm text-gray-500">Póliza: <span className="font-medium text-gray-900">{policyNumber}</span></p>
                        <p className="text-sm text-gray-500">Cliente: <span className="font-medium text-gray-900">{clientName}</span></p>
                    </div>

                    <div>
                        <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-1">
                            Estatus de Renovación
                        </label>
                        <select
                            id="status"
                            value={status || ''}
                            onChange={(e) => setStatus(e.target.value || null)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-gray-900"
                        >
                            <option value="">Seleccionar estatus</option>
                            {currentStatus && !RENEWAL_STATUS_OPTIONS.includes(currentStatus as typeof RENEWAL_STATUS_OPTIONS[number]) && (
                                <option value={currentStatus} disabled>
                                    Estatus anterior: {currentStatus}
                                </option>
                            )}
                            {RENEWAL_STATUS_OPTIONS.map((option) => (
                                <option key={option} value={option}>{option}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Link Expediente</label>
                        <input
                            type="text"
                            value={expediente}
                            onChange={(e) => setExpediente(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-gray-900"
                            placeholder="Link o ruta a la carpeta"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Email de Contacto</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-gray-900"
                            placeholder={registeredEmail || "ejemplo@correo.com"}
                        />
                        {registeredEmail && !email && (
                            <p className="text-xs text-green-600 mt-1">
                                Correo registrado: {registeredEmail}
                            </p>
                        )}
                    </div>
                </div>

                <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
                    <button
                        onClick={handleSendEmail}
                        disabled={isSending}
                        className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                    >
                        <Mail className="h-4 w-4 mr-2" />
                        {isSending ? 'Enviando...' : 'Enviar Correo'}
                    </button>

                    <div className="grid grid-cols-2 gap-3 sm:flex sm:space-x-3">
                        <button
                            onClick={onClose}
                            disabled={isSending || isSaving}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={isSending || isSaving}
                            className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                        >
                            {isSaving ? 'Guardando...' : 'Guardar'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
