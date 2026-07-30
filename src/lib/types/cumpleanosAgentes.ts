export interface AgentBirthday {
    agent_name: string;
    rfc: string;
    birth_date: string;
    next_birthday: string;
    days_until_birthday: number;
    definitive_keys: string[];
    promotorias: string[];
    email: string;
    status: string;
}

export interface AgentBirthdayDirectory {
    generated_on: string;
    agents: AgentBirthday[];
    summary: {
        total_agents: number;
        birthdays_this_month: number;
        birthdays_next_30_days: number;
        missing_rfc_rows: number;
        invalid_rfc_rows: number;
        duplicate_rows: number;
    };
}
