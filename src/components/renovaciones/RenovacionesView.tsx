'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DataTable } from '@/components/ui/DataTable';
import { RenovacionGMM, RenovacionVida, RenovacionSura, RenovacionAarco, RenovacionPromotoriaSura } from '@/lib/types/renovaciones';
import { exportToExcel } from '@/lib/utils/export';
import { updateRenewalStatus } from '@/modules/renovaciones/service';
import { EditStatusModal } from './EditStatusModal';

interface RenovacionesViewProps {
    vidaRenewals?: RenovacionVida[];
    gmmRenewals?: RenovacionGMM[];
    suraRenewals?: RenovacionSura[];
    aarcoRenewals?: RenovacionAarco[];
    promotoriaSuraRenewals?: RenovacionPromotoriaSura[];
    insurer: string;
}

export function RenovacionesView({ vidaRenewals = [], gmmRenewals = [], suraRenewals = [], aarcoRenewals = [], promotoriaSuraRenewals = [], insurer }: RenovacionesViewProps) {
    const router = useRouter();
    const [activeTab, setActiveTab] = useState<'VIDA' | 'GMM'>('VIDA');
    const [selectedRow, setSelectedRow] = useState<any>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [visibleRenewals, setVisibleRenewals] = useState<any[]>([]);
    const [vidaData, setVidaData] = useState<RenovacionVida[]>(vidaRenewals);
    const [gmmData, setGmmData] = useState<RenovacionGMM[]>(gmmRenewals);
    const [suraData, setSuraData] = useState<RenovacionSura[]>(suraRenewals);
    const [aarcoData, setAarcoData] = useState<RenovacionAarco[]>(aarcoRenewals);
    const [promotoriaSuraData, setPromotoriaSuraData] = useState<RenovacionPromotoriaSura[]>(promotoriaSuraRenewals);

    const activeRenewals = insurer === 'Metlife'
        ? (activeTab === 'VIDA' ? vidaData : gmmData)
        : insurer === 'SURA'
            ? suraData
            : insurer === 'AARCO_AXA'
                ? aarcoData
                : promotoriaSuraData;

    useEffect(() => setVidaData(vidaRenewals), [vidaRenewals]);
    useEffect(() => setGmmData(gmmRenewals), [gmmRenewals]);
    useEffect(() => setSuraData(suraRenewals), [suraRenewals]);
    useEffect(() => setAarcoData(aarcoRenewals), [aarcoRenewals]);
    useEffect(() => setPromotoriaSuraData(promotoriaSuraRenewals), [promotoriaSuraRenewals]);

    useEffect(() => {
        setVisibleRenewals(activeRenewals);
    }, [activeTab, insurer, vidaData, gmmData, suraData, aarcoData, promotoriaSuraData]);

    const handleExport = () => {
        let data: any[] = visibleRenewals;
        let prefix = '';

        if (insurer === 'Metlife') {
            prefix = `Renovaciones_Metlife_${activeTab}`;
        } else if (insurer === 'SURA') {
            prefix = `Renovaciones_SURA`;
        } else if (insurer === 'AARCO_AXA') {
            prefix = `Renovaciones_AARCO_AXA`;
        } else if (insurer === 'Promotoria SURA') {
            prefix = `Renovaciones_Promotoria_SURA`;
        }

        const fileName = `${prefix}_${new Date().toISOString().split('T')[0]}.xlsx`;
        exportToExcel(data, fileName);
    };

    const handleRowClick = (row: any) => {
        setSelectedRow(row);
        setIsModalOpen(true);
    };

    const updateSelectedRenewal = (updates: Record<string, unknown>) => {
        if (!selectedRow) return;

        const policyKey = insurer === 'Metlife'
            ? (activeTab === 'VIDA' ? 'POLIZA_ACTUAL' : 'NPOLIZA')
            : insurer === 'Promotoria SURA'
                ? 'PÓLIZA'
                : 'POLIZA';
        const selectedPolicy = String(selectedRow[policyKey] ?? '');
        const updateRows = <T extends Record<string, any>>(rows: T[]) => rows.map((row) =>
            String(row[policyKey] ?? '') === selectedPolicy ? { ...row, ...updates } : row
        );

        if (insurer === 'Metlife' && activeTab === 'VIDA') {
            setVidaData((rows) => updateRows(rows));
        } else if (insurer === 'Metlife') {
            setGmmData((rows) => updateRows(rows));
        } else if (insurer === 'SURA') {
            setSuraData((rows) => updateRows(rows));
        } else if (insurer === 'AARCO_AXA') {
            setAarcoData((rows) => updateRows(rows));
        } else {
            setPromotoriaSuraData((rows) => updateRows(rows));
        }

        setSelectedRow((row: any) => row ? { ...row, ...updates } : row);
    };

    const handleSaveStatus = async (newStatus: string | null, expediente: string | null, email: string | null) => {
        if (!selectedRow) return;

        let type = '';
        let id = '';

        if (insurer === 'Metlife') {
            type = activeTab;
            id = activeTab === 'VIDA' ? selectedRow.POLIZA_ACTUAL : selectedRow.NPOLIZA;
        } else if (insurer === 'SURA') {
            type = 'ALL';
            id = selectedRow.POLIZA;
        } else if (insurer === 'AARCO_AXA') {
            type = 'ALL';
            id = selectedRow.POLIZA;
        } else if (insurer === 'Promotoria SURA') {
            type = 'ALL';
            id = selectedRow.PÓLIZA;
        }

        await updateRenewalStatus(insurer, type, id, newStatus, expediente, email);

        updateSelectedRenewal({
            ...(newStatus !== null ? { ESTATUS_DE_RENOVACION: newStatus } : {}),
            ...(expediente !== null ? { EXPEDIENTE: expediente } : {}),
            ...(email !== null ? { Email: email } : {}),
        });
        router.refresh();
    };

    const handleEmailSent = async () => {
        updateSelectedRenewal({ ESTATUS_DE_RENOVACION: 'Enviado' });
        router.refresh();
    };

    const renderExpedienteLink = (row: any) => {
        if (row.EXPEDIENTE) {
            return (
                <a
                    href={row.EXPEDIENTE}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline font-medium"
                    onClick={(e) => e.stopPropagation()} // Prevent row click when clicking link
                >
                    LINK
                </a>
            );
        }
        return null;
    };

    const vidaColumns = [
        { header: 'Póliza Actual', accessorKey: 'POLIZA_ACTUAL' as keyof RenovacionVida },
        { header: 'Contratante', accessorKey: 'CONTRATANTE' as keyof RenovacionVida },
        { header: 'Fin Vigencia', accessorKey: 'FIN_VIG' as keyof RenovacionVida },
        { header: 'Forma Pago', accessorKey: 'FORMA_PAGO' as keyof RenovacionVida },
        { header: 'Conducto Cobro', accessorKey: 'CONDUCTO_COBRO' as keyof RenovacionVida },
        { header: 'Agente', accessorKey: 'AGENTE' as keyof RenovacionVida },
        { header: 'Nombre', accessorKey: 'NOMBRE' as keyof RenovacionVida },
        { header: 'Promotoría', accessorKey: 'PROMOTORIA' as keyof RenovacionVida },
        {
            header: 'Prima Anual',
            accessorKey: (row: RenovacionVida) => {
                if (row.PRIMA_ANUAL === undefined || row.PRIMA_ANUAL === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.PRIMA_ANUAL);
            }
        },
        {
            header: 'Prima Modal',
            accessorKey: (row: RenovacionVida) => {
                if (row.PRIMA_MODAL === undefined || row.PRIMA_MODAL === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.PRIMA_MODAL);
            }
        },
        { header: 'Pagado Hasta', accessorKey: 'PAGADO_HASTA' as keyof RenovacionVida },
        { header: 'Estatus Renovación', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionVida },
        {
            header: 'Expediente',
            accessorKey: 'EXPEDIENTE' as keyof RenovacionVida,
            cell: (info: any) => renderExpedienteLink(info.row.original)
        },
        { header: 'Email', accessorKey: 'Email' as keyof RenovacionVida }
    ];

    const gmmColumns = [
        { header: 'N Póliza', accessorKey: 'NPOLIZA' as keyof RenovacionGMM },
        { header: 'Póliza Origen', accessorKey: 'POLORIG' as keyof RenovacionGMM },
        { header: 'Contratante', accessorKey: 'CONTRATANTE' as keyof RenovacionGMM },
        { header: 'Fin Vigencia', accessorKey: 'FFINVIG' as keyof RenovacionGMM },
        {
            header: 'Prima',
            accessorKey: (row: RenovacionGMM) => {
                if (row['PRIMA.1'] === undefined || row['PRIMA.1'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['PRIMA.1']);
            }
        },
        {
            header: 'IVA',
            accessorKey: (row: RenovacionGMM) => {
                if (row.IVA === undefined || row.IVA === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.IVA);
            }
        },

        { header: 'Pagado Hasta', accessorKey: 'PAGADOHASTA' as keyof RenovacionGMM },
        { header: 'Agente', accessorKey: 'AGENTE' as keyof RenovacionGMM },
        { header: 'Nombre', accessorKey: 'NOMBRE' as keyof RenovacionGMM },
        { header: 'Promotoría', accessorKey: 'PROMOTORIA' as keyof RenovacionGMM },
        { header: 'Estatus Renovación', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionGMM },
        {
            header: 'Expediente',
            accessorKey: 'EXPEDIENTE' as keyof RenovacionGMM,
            cell: (info: any) => renderExpedienteLink(info.row.original)
        },
        { header: 'Email', accessorKey: 'Email' as keyof RenovacionGMM }
    ];

    const suraColumns = [
        { header: 'Póliza', accessorKey: 'POLIZA' as keyof RenovacionSura },
        { header: 'Nombre', accessorKey: 'NOMBRE' as keyof RenovacionSura },
        { header: 'Inicio Vigencia', accessorKey: 'INICIO VIGENCIA' as keyof RenovacionSura },
        { header: 'Fin Vigencia', accessorKey: 'FIN VIGENCIA' as keyof RenovacionSura },
        { header: 'Ramo', accessorKey: 'RAMO' as keyof RenovacionSura },
        {
            header: 'Prima',
            accessorKey: (row: RenovacionSura) => {
                if (row.PRIMA === undefined || row.PRIMA === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row.PRIMA);
            }
        },
        { header: 'Periodicidad', accessorKey: 'PERIODICIDAD_PAGO' as keyof RenovacionSura },
        { header: 'Prospectador', accessorKey: 'PROSPECTADOR' as keyof RenovacionSura },
        { header: 'Estatus', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionSura },
        {
            header: 'Expediente',
            accessorKey: 'EXPEDIENTE' as keyof RenovacionSura,
            cell: (info: any) => renderExpedienteLink(info.row.original)
        },
        { header: 'Email', accessorKey: 'Email' as keyof RenovacionSura }
    ];

    const aarcoColumns = [
        { header: 'Póliza', accessorKey: 'POLIZA' as keyof RenovacionAarco },
        { header: 'Aseguradora', accessorKey: 'ASEGURADORA' as keyof RenovacionAarco },
        { header: 'Promotoría', accessorKey: 'PROMOTORIA' as keyof RenovacionAarco },
        { header: 'Agente', accessorKey: 'AGENTE' as keyof RenovacionAarco },
        { header: 'Prospectador', accessorKey: 'PROSPECTADOR' as keyof RenovacionAarco },
        { header: 'Ramo', accessorKey: 'RAMO' as keyof RenovacionAarco },
        { header: 'Producto', accessorKey: 'PRODUCTO' as keyof RenovacionAarco },
        { header: 'Contratante', accessorKey: 'CONTRATANTE' as keyof RenovacionAarco },
        { header: 'Asegurado', accessorKey: 'ASEGURADO' as keyof RenovacionAarco },
        { header: 'Inicio Vigencia', accessorKey: 'INICIO VIGENCIA' as keyof RenovacionAarco },
        { header: 'Fin Vigencia', accessorKey: 'FIN VIGENCIA' as keyof RenovacionAarco },
        {
            header: 'Prima Neta',
            accessorKey: (row: RenovacionAarco) => {
                if (row['PRIMA NETA ANUAL'] === undefined || row['PRIMA NETA ANUAL'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['PRIMA NETA ANUAL']);
            }
        },
        { header: 'Estatus de Renovación', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionAarco },
        {
            header: 'Expediente',
            accessorKey: 'EXPEDIENTE' as keyof RenovacionAarco,
            cell: (info: any) => renderExpedienteLink(info.row.original)
        },
        { header: 'Email', accessorKey: 'Email' as keyof RenovacionAarco }
    ];

    const promotoriaSuraColumns = [
        { header: 'Póliza', accessorKey: 'PÓLIZA' as keyof RenovacionPromotoriaSura },
        { header: 'Oficina', accessorKey: 'OFICINA' as keyof RenovacionPromotoriaSura },
        { header: 'Ramo', accessorKey: 'RAMO' as keyof RenovacionPromotoriaSura },
        { header: 'Inicio Vigencia', accessorKey: 'INICIO VIGENCIA' as keyof RenovacionPromotoriaSura },
        { header: 'Fin Vigencia', accessorKey: 'FIN VIGENCIA' as keyof RenovacionPromotoriaSura },
        { header: 'Contratante', accessorKey: 'CONTRATANTE' as keyof RenovacionPromotoriaSura },
        {
            header: 'Prima Anualizada',
            accessorKey: (row: RenovacionPromotoriaSura) => {
                if (row['PRIMA ANUALIZADA'] === undefined || row['PRIMA ANUALIZADA'] === null) return 'N/A';
                return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(row['PRIMA ANUALIZADA']);
            }
        },
        { header: 'Agente', accessorKey: 'AGENTE' as keyof RenovacionPromotoriaSura },
        { header: 'Nombre Ramo', accessorKey: 'NOMBRE RAMO' as keyof RenovacionPromotoriaSura },
        { header: 'Procedencia', accessorKey: 'PROCEDENCIA' as keyof RenovacionPromotoriaSura },
        { header: 'Poliza Anterior', accessorKey: 'Poliza anterior' as keyof RenovacionPromotoriaSura },
        { header: 'Llave Póliza', accessorKey: 'Llave Póliza' as keyof RenovacionPromotoriaSura },
        { header: 'Estatus de Renovación', accessorKey: 'ESTATUS_DE_RENOVACION' as keyof RenovacionPromotoriaSura },
        {
            header: 'Expediente',
            accessorKey: 'EXPEDIENTE' as keyof RenovacionPromotoriaSura,
            cell: (info: any) => renderExpedienteLink(info.row.original)
        },
        { header: 'Email', accessorKey: 'Email' as keyof RenovacionPromotoriaSura }
    ];

    return (
        <div className="flex flex-col h-full space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-2 flex-none">
                <div className="flex min-w-0 space-x-2 sm:space-x-4">
                    {insurer === 'Metlife' && (
                        <>
                            <button
                                className={`px-4 py-2 font-medium ${activeTab === 'VIDA' ? 'border-b-2 border-white text-white' : 'text-white/70 hover:text-white'}`}
                                onClick={() => setActiveTab('VIDA')}
                            >
                                Vida
                            </button>
                            <button
                                className={`px-4 py-2 font-medium ${activeTab === 'GMM' ? 'border-b-2 border-white text-white' : 'text-white/70 hover:text-white'}`}
                                onClick={() => setActiveTab('GMM')}
                            >
                                GMM
                            </button>
                        </>
                    )}
                    {insurer === 'SURA' && (
                        <span className="px-4 py-2 font-medium border-b-2 border-white text-white">
                            SURA Renovaciones
                        </span>
                    )}
                    {insurer === 'AARCO_AXA' && (
                        <span className="px-4 py-2 font-medium border-b-2 border-white text-white">
                            AARCO & AXA Renovaciones
                        </span>
                    )}
                    {insurer === 'Promotoria SURA' && (
                        <span className="px-4 py-2 font-medium border-b-2 border-white text-white">
                            Promotoría SURA Renovaciones
                        </span>
                    )}
                </div>
                <button
                    onClick={handleExport}
                    className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                >
                    Exportar Excel
                </button>
            </div>

            <div className="flex-1 min-h-0 overflow-hidden">
                {insurer === 'Metlife' ? (
                    activeTab === 'VIDA' ? (
                        <DataTable
                            key="metlife-vida"
                            data={vidaData}
                            columns={vidaColumns}
                            filterMode="multi-select"
                            onProcessedDataChange={setVisibleRenewals}
                            className="h-full overflow-auto"
                            onRowClick={handleRowClick}
                        />
                    ) : (
                        <DataTable
                            key="metlife-gmm"
                            data={gmmData}
                            columns={gmmColumns}
                            filterMode="multi-select"
                            onProcessedDataChange={setVisibleRenewals}
                            className="h-full overflow-auto"
                            onRowClick={handleRowClick}
                        />
                    )
                ) : insurer === 'SURA' ? (
                    <DataTable
                        key="sura"
                        data={suraData}
                        columns={suraColumns}
                        filterMode="multi-select"
                        onProcessedDataChange={setVisibleRenewals}
                        className="h-full overflow-auto"
                        onRowClick={handleRowClick}
                    />
                ) : insurer === 'AARCO_AXA' ? (
                    <DataTable
                        key="aarco-axa"
                        data={aarcoData}
                        columns={aarcoColumns}
                        filterMode="multi-select"
                        onProcessedDataChange={setVisibleRenewals}
                        className="h-full overflow-auto"
                        onRowClick={handleRowClick}
                    />
                ) : (
                    <DataTable
                        key="promotoria-sura"
                        data={promotoriaSuraData}
                        columns={promotoriaSuraColumns}
                        filterMode="multi-select"
                        onProcessedDataChange={setVisibleRenewals}
                        className="h-full overflow-auto"
                        onRowClick={handleRowClick}
                    />
                )}
            </div>

            {selectedRow && (
                <EditStatusModal
                    isOpen={isModalOpen}
                    onClose={() => setIsModalOpen(false)}
                    onSave={handleSaveStatus}
                    onEmailSent={handleEmailSent}
                    currentStatus={selectedRow.ESTATUS_DE_RENOVACION}
                    currentExpediente={selectedRow.EXPEDIENTE}
                    currentEmail={selectedRow.Email}
                    policyNumber={
                        insurer === 'Metlife'
                            ? (activeTab === 'VIDA' ? selectedRow.POLIZA_ACTUAL : selectedRow.NPOLIZA)
                            : insurer === 'SURA'
                                ? selectedRow.POLIZA
                                : insurer === 'Promotoria SURA'
                                    ? selectedRow['PÓLIZA']
                                    : selectedRow.POLIZA
                    }
                    insurer={insurer}
                    type={insurer === 'Metlife' ? activeTab : 'ALL'}
                    clientName={
                        insurer === 'Metlife'
                            ? selectedRow.CONTRATANTE
                            : insurer === 'SURA'
                                ? selectedRow.NOMBRE
                                : insurer === 'Promotoria SURA'
                                    ? selectedRow.CONTRATANTE
                                    : selectedRow.CONTRATANTE
                    }
                    endDate={
                        insurer === 'Metlife'
                            ? (activeTab === 'VIDA' ? selectedRow.FIN_VIG : selectedRow.FFINVIG)
                            : insurer === 'SURA'
                                ? selectedRow['FIN VIGENCIA']
                                : insurer === 'Promotoria SURA'
                                    ? selectedRow['FIN VIGENCIA']
                                    : selectedRow['FIN VIGENCIA']
                    }
                />
            )}
        </div>
    );
}
