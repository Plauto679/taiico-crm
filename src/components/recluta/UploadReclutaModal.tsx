'use client';

import { FormEvent, useState } from 'react';
import { Loader2, Plus, Trash2, Upload, X } from 'lucide-react';

import { ReclutaDocument, ReclutaProspect } from '@/lib/types/recluta';
import { uploadReclutaDocument } from '@/modules/recluta/service';


interface UploadReclutaModalProps {
    prospect: ReclutaProspect;
    onClose: () => void;
    onUploaded: (document: ReclutaDocument) => void;
}

interface UploadRow {
    id: number;
    name: string;
    file: File | null;
}

let nextRowId = 1;

export function UploadReclutaModal({ prospect, onClose, onUploaded }: UploadReclutaModalProps) {
    const [rows, setRows] = useState<UploadRow[]>([{ id: 0, name: '', file: null }]);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const updateRow = (id: number, patch: Partial<UploadRow>) => {
        setRows((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row));
    };

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        const incomplete = rows.some((row) => !row.name.trim() || !row.file);
        if (incomplete) {
            setError('Asigna un nombre y selecciona un archivo en cada fila.');
            return;
        }

        setUploading(true);
        setError(null);
        let uploadedCount = 0;
        try {
            for (const row of rows) {
                const response = await uploadReclutaDocument(prospect.id, row.name, row.file as File);
                uploadedCount += 1;
                onUploaded(response.document);
            }
            onClose();
        } catch (uploadError) {
            const detail = uploadError instanceof Error ? uploadError.message : 'No fue posible cargar el archivo.';
            setError(uploadedCount > 0 ? `${uploadedCount} archivo(s) se cargaron. ${detail}` : detail);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={onClose}>
            <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
                <div className="flex items-center justify-between border-b border-slate-200 p-5">
                    <div>
                        <h2 className="text-xl font-bold text-slate-900">Cargar archivo</h2>
                        <p className="mt-1 text-sm text-slate-500">Documentos de {prospect.nombre}. Máximo 25 MB por archivo.</p>
                    </div>
                    <button type="button" onClick={onClose} disabled={uploading} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Cerrar">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <form onSubmit={submit} className="p-5">
                    <div className="max-h-[50vh] space-y-4 overflow-y-auto pr-1">
                        {rows.map((row, index) => (
                            <div key={row.id} className="rounded-xl border border-slate-200 p-4">
                                <div className="mb-3 flex items-center justify-between">
                                    <span className="text-sm font-semibold text-slate-700">Documento {index + 1}</span>
                                    {rows.length > 1 && (
                                        <button type="button" onClick={() => setRows((current) => current.filter((item) => item.id !== row.id))} disabled={uploading} className="rounded-md p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="Quitar documento">
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    )}
                                </div>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <label className="block">
                                        <span className="text-sm font-medium text-slate-700">Nombre del documento</span>
                                        <input value={row.name} onChange={(event) => updateRow(row.id, { name: event.target.value })} disabled={uploading} placeholder="Ej. Cédula de agente" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" />
                                    </label>
                                    <label className="block">
                                        <span className="text-sm font-medium text-slate-700">Archivo</span>
                                        <input type="file" onChange={(event) => updateRow(row.id, { file: event.target.files?.[0] || null })} disabled={uploading} className="mt-1.5 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:font-semibold file:text-slate-700 hover:file:bg-slate-200" />
                                    </label>
                                </div>
                            </div>
                        ))}
                    </div>

                    <button type="button" onClick={() => setRows((current) => [...current, { id: nextRowId++, name: '', file: null }])} disabled={uploading} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-dashed border-blue-300 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50">
                        <Plus className="h-4 w-4" /> Agregar otro documento
                    </button>

                    {error && <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}

                    <div className="mt-6 flex justify-end gap-3">
                        <button type="button" onClick={onClose} disabled={uploading} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60">Cancelar</button>
                        <button type="submit" disabled={uploading} className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                            {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                            Cargar {rows.length === 1 ? 'archivo' : `${rows.length} archivos`}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
