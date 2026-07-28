import { PendingAgentOption } from '@/lib/types/pendientes';

interface PendingAgentSelectProps {
    agents: PendingAgentOption[];
    promotoria: string;
    value: string;
    onChange: (value: string) => void;
    disabled?: boolean;
    required?: boolean;
    className?: string;
}

export function agentsForPromotoria(
    agents: PendingAgentOption[],
    promotoria: string,
): PendingAgentOption[] {
    return agents.filter((agent) => agent.promotoria === promotoria);
}

export function PendingAgentSelect({
    agents,
    promotoria,
    value,
    onChange,
    disabled = false,
    required = true,
    className = '',
}: PendingAgentSelectProps) {
    const options = agentsForPromotoria(agents, promotoria);
    const currentIsMissing = Boolean(value) && !options.some((agent) => agent.rfc === value);

    return (
        <select
            required={required}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            disabled={disabled || !promotoria}
            className={className}
        >
            <option value="">Seleccionar...</option>
            {currentIsMissing && (
                <option value={value}>{value} - Agente no encontrado en la promotoría</option>
            )}
            {options.map((agent) => (
                <option key={agent.rfc} value={agent.rfc}>{agent.label}</option>
            ))}
        </select>
    );
}
