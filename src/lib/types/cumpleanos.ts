export interface BirthdayPolicy {
    branch: string;
    policy_number: string;
    status: string;
    effective_start_date: string;
    effective_end_date: string;
    is_active: boolean;
}

export interface BirthdayClient {
    identity_key: string;
    client_ids: string[];
    client_name: string;
    rfc: string;
    rfcs: string[];
    birth_date: string;
    next_birthday: string;
    days_until_birthday: number;
    policies: BirthdayPolicy[];
    active_policies: BirthdayPolicy[];
    active_policy_count: number;
    agent_rfc: string;
    agent_name: string;
    agent_label: string;
    promotoria: string;
    promotorias: string[];
}

export interface BirthdayDirectory {
    generated_on: string;
    clients: BirthdayClient[];
    summary: {
        total_clients: number;
        birthdays_this_month: number;
        birthdays_next_30_days: number;
        invalid_rfc_rows: number;
        non_person_rfc_rows: number;
        unmatched_agent_rows: number;
        total_client_records: number;
        eligible_client_records: number;
        duplicate_client_records_collapsed: number;
        clients_with_active_policies: number;
    };
}
