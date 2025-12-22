'use client';

import { useState, useEffect } from 'react';
import { X, Check, Mail } from 'lucide-react';
import { sendRenewalEmail } from '@/modules/renovaciones/service';

interface EditStatusModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (newStatus: string, expediente?: string) => Promise<void>;
    currentStatus: string | null | undefined;
    currentExpediente?: string | null;
    policyNumber: string | number;
    insurer: string;
    type: string;
    clientName: string;
    endDate: string;
}

export function EditStatusModal({
    isOpen,
    onClose,
    onSave,
    currentStatus,
    currentExpediente,
    policyNumber,
    insurer,
    type,
    clientName,
    endDate
}: EditStatusModalProps) {
    const [status, setStatus] = useState(currentStatus || '');
    const [expediente, setExpediente] = useState(currentExpediente || '');
    const [isSaving, setIsSaving] = useState(false);
    const [isSendingEmail, setIsSendingEmail] = useState(false);

    useEffect(() => {
        if (isOpen) {
            setStatus(currentStatus || '');
            setExpediente(currentExpediente || '');
        }
    }, [isOpen, currentStatus, currentExpediente]);

    if (!isOpen) return null;

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave(status, expediente);
            onClose();
        } catch (error) {
            console.error('Failed to save status', error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleSendEmail = async () => {
        if (!confirm(`¿Enviar correo de renovación a ${clientName}?`)) return;

        setIsSendingEmail(true);
        try {
            await sendRenewalEmail(
                insurer,
                type,
                policyNumber,
                clientName,
                endDate,
                expediente
            );
            alert('Correo enviado exitosamente.');
            // Update status to Enviado maybe? Or let the user do it?
            // User requested: whenever the email is sucesfully sent, the value of the column 'Email' should say 'Enviado' (handled by backend)
            // But UI might not reflect it until refresh. That's fine for MVP.
        } catch (error: any) {
            console.error('Failed to send email', error);
            alert('Error al enviar correo: ' + (error.message || 'Desconocido'));
        } finally {
            setIsSendingEmail(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-medium text-gray-900">
                        Actualizar Póliza
                    </h3>
                    <button
                        onClick={onClose}
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
                        <input
                            type="text"
                            id="status"
                            value={status}
                            onChange={(e) => setStatus(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-gray-900"
                            placeholder="Ingrese el nuevo estatus"
                        />
                    </div>

                    <div>
                        <label htmlFor="expediente" className="block text-sm font-medium text-gray-700 mb-1">
                            Link Expediente
                        </label>
                        <input
                            type="text"
                            id="expediente"
                            value={expediente}
                            onChange={(e) => setExpediente(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-gray-900"
                            placeholder="https://..."
                        />
                    </div>
                </div>

                <div className="mt-6 flex justify-between">
                    <button
                        onClick={handleSendEmail}
                        disabled={isSendingEmail}
                        className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                    >
                        <Mail className="h-4 w-4 mr-2" />
                        {isSendingEmail ? 'Enviando...' : 'Enviar Correo'}
                    </button>

                    <div className="flex space-x-3">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={isSaving}
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
