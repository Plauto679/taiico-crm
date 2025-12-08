'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface EditStatusModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (newStatus: string) => Promise<void>;
    currentStatus: string | null | undefined; // Allow null/undefined
    policyNumber: string;
    insurer: string;
}

export function EditStatusModal({ isOpen, onClose, onSave, currentStatus, policyNumber, insurer }: EditStatusModalProps) {
    // Ensure initial state is never null/undefined for the input
    const [status, setStatus] = useState(currentStatus || '');
    const [isSaving, setIsSaving] = useState(false);

    useEffect(() => {
        // When prop changes, update state, defaulting to empty string if null/undefined
        setStatus(currentStatus || '');
    }, [currentStatus, isOpen]);

    if (!isOpen) return null;

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave(status);
            onClose();
        } catch (error) {
            console.error("Error saving status:", error);
            alert("Error saving status. Please try again.");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
                <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
                    <h3 className="text-lg font-medium text-gray-900">
                        Editar Estatus de Renovación
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-500 focus:outline-none"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="px-6 py-6 space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Aseguradora
                        </label>
                        <div className="text-gray-900 font-medium">{insurer}</div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Póliza
                        </label>
                        <div className="text-gray-900 font-medium">{policyNumber}</div>
                    </div>

                    <div>
                        <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-1">
                            Nuevo Estatus
                        </label>
                        <input
                            id="status"
                            type="text"
                            value={status} // This is now guaranteed to be a string
                            onChange={(e) => setStatus(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-gray-900" // Added text-gray-900
                            placeholder="Ingrese el estatus..."
                            autoFocus
                        />
                    </div>
                </div>

                <div className="px-6 py-4 bg-gray-50 flex justify-end space-x-3 border-t">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                        disabled={isSaving}
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={handleSave}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 flex items-center"
                        disabled={isSaving}
                    >
                        {isSaving ? 'Guardando...' : 'Guardar'}
                    </button>
                </div>
            </div>
        </div>
    );
}
