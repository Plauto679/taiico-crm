'use client';

import { useState, useEffect } from 'react';
import { X, Trash2 } from 'lucide-react';
import { Cliente } from '@/lib/types/clientes';

interface EditClientModalProps {
    isOpen: boolean;
    onClose: () => void;
    client: Cliente | null;
    onSave: (originalNombre: string, updatedClient: Cliente) => Promise<void>;
    onDelete: (nombre: string) => Promise<void>;
}

export function EditClientModal({ isOpen, onClose, client, onSave, onDelete }: EditClientModalProps) {
    const [nombre, setNombre] = useState('');
    const [correo, setCorreo] = useState('');
    const [telefono, setTelefono] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        if (client) {
            setNombre(client.nombre);
            setCorreo(client.correo || '');
            setTelefono(client.telefono || '');
        }
    }, [client]);

    if (!isOpen || !client) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!nombre.trim()) return;

        setIsSaving(true);
        try {
            await onSave(client.nombre, {
                nombre: nombre.trim(),
                correo: correo.trim() || undefined,
                telefono: telefono.trim() || undefined,
            });
            onClose();
        } catch (error) {
            console.error('Error updating client:', error);
            alert('Error al actualizar el cliente');
        } finally {
            setIsSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm('¿Estás seguro de que deseas eliminar este cliente? Esta acción no se puede deshacer.')) return;

        setIsDeleting(true);
        try {
            await onDelete(client.nombre);
            onClose();
        } catch (error) {
            console.error('Error deleting client:', error);
            alert('Error al eliminar el cliente');
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-medium text-gray-900">Editar Cliente</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
                        <X className="h-6 w-6" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label htmlFor="edit-nombre" className="block text-sm font-medium text-gray-700">
                            Nombre de Cliente <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            id="edit-nombre"
                            required
                            value={nombre}
                            onChange={(e) => setNombre(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm text-gray-900"
                        />
                    </div>

                    <div>
                        <label htmlFor="edit-correo" className="block text-sm font-medium text-gray-700">
                            Correo (Opcional)
                        </label>
                        <input
                            type="email"
                            id="edit-correo"
                            value={correo}
                            onChange={(e) => setCorreo(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm text-gray-900"
                        />
                    </div>

                    <div>
                        <label htmlFor="edit-telefono" className="block text-sm font-medium text-gray-700">
                            Teléfono (Opcional)
                        </label>
                        <input
                            type="text"
                            id="edit-telefono"
                            value={telefono}
                            onChange={(e) => setTelefono(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm text-gray-900"
                        />
                    </div>

                    <div className="mt-6 flex justify-between items-center">
                        <button
                            type="button"
                            onClick={handleDelete}
                            disabled={isDeleting || isSaving}
                            className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                        >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Eliminar cliente
                        </button>

                        <div className="flex space-x-3">
                            <button
                                type="button"
                                onClick={onClose}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                            >
                                Cancelar
                            </button>
                            <button
                                type="submit"
                                disabled={isSaving || isDeleting}
                                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                            >
                                {isSaving ? 'Guardando...' : 'Guardar'}
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
}
