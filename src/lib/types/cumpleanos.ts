export interface BirthdayPolicy {
    branch: string;
    policy_number: string;
}

export interface BirthdayClient {
    client_name: string;
    rfc: string;
    birth_date: string;
    next_birthday: string;
    days_until_birthday: number;
    policies: BirthdayPolicy[];
    agent_rfc: string;
    agent_name: string;
    agent_label: string;
    promotoria: string;
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
    };
}
