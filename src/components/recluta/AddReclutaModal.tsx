'use client';

import { FormEvent, useState } from 'react';
import { Loader2, UserPlus, X } from 'lucide-react';

import { ReclutaCreateInput, ReclutaProspect } from '@/lib/types/recluta';
import { addReclutaProspect } from '@/modules/recluta/service';


interface AddReclutaModalProps {
    phases: string[];
    onClose: () => void;
    onCreated: (prospect: ReclutaProspect, warning: string | null) => void;
}

const EMPTY_FORM: ReclutaCreateInput = {
    nombre: '',
    telefono: '',
    correo: '',
    rfc: '',
    fase: '',
    estatus: '',
};

export function AddReclutaModal({ phases, onClose, onCreated }: AddReclutaModalProps) {
    const [form, setForm] = useState(EMPTY_FORM);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const update = (field: keyof ReclutaCreateInput, value: string) => {
        setForm((current) => ({ ...current, [field]: value }));
    };

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        setSaving(true);
        setError(null);
        try {
            const response = await addReclutaProspect(form);
            onCreated(response.prospect, response.folder_warning);
        } catch (submissionError) {
            setError(submissionError instanceof Error ? submissionError.message : 'No fue posible agregar el recluta.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={onClose}>
            <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
                <div className="flex items-center justify-between border-b border-slate-200 p-5">
                    <div className="flex items-center gap-3">
                        <div className="rounded-full bg-blue-100 p-2 text-blue-700"><UserPlus className="h-5 w-5" /></div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">Agregar recluta</h2>
                            <p className="text-sm text-slate-500">El registro se guardará en la base de Drive.</p>
                        </div>
                    </div>
                    <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Cerrar">
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <form onSubmit={submit} className="p-5">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <Field label="Nombre completo" required value={form.nombre} onChange={(value) => update('nombre', value)} />
                        <Field label="RFC" value={form.rfc} onChange={(value) => update('rfc', value.toUpperCase())} />
                        <Field label="Teléfono" type="tel" value={form.telefono} onChange={(value) => update('telefono', value)} />
                        <Field label="Correo electrónico" type="email" value={form.correo} onChange={(value) => update('correo', value)} />
                        <Field label="Fase" list="recluta-phases" value={form.fase} onChange={(value) => update('fase', value)} />
                        <Field label="Estatus" value={form.estatus} onChange={(value) => update('estatus', value)} />
                        <datalist id="recluta-phases">
                            {phases.filter((phase) => phase !== 'Sin fase').map((phase) => <option key={phase} value={phase} />)}
                        </datalist>
                    </div>

                    {error && <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}

                    <div className="mt-6 flex justify-end gap-3">
                        <button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60">
                            Cancelar
                        </button>
                        <button type="submit" disabled={saving || !form.nombre.trim()} className="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Guardar recluta
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

function Field({
    label,
    value,
    onChange,
    type = 'text',
    required = false,
    list,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    type?: string;
    required?: boolean;
    list?: string;
}) {
    return (
        <label className="block">
            <span className="text-sm font-medium text-slate-700">{label}{required && ' *'}</span>
            <input
                type={type}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                required={required}
                list={list}
                className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
        </label>
    );
}
