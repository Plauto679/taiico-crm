import { fetchFromApi } from '@/lib/api';

export type AutomaticMailCadence = 'daily' | 'weekly' | 'monthly';

export type AutomaticMail = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  cadence: AutomaticMailCadence;
  hour: number;
  minute: number;
  timezone: string;
  day_of_week: number | null;
  day_of_month: number | null;
  sender: string;
  recipient_mode: 'manual' | 'dynamic';
  recipient_description: string;
  recipients: string[];
  cc_recipients: string[];
  cc_description?: string;
  promotoria?: string;
};

export type AutomaticMailDirectory = {
  can_operate: boolean;
  automations: AutomaticMail[];
};

export type AutomaticMailUpdate = Pick<
  AutomaticMail,
  | 'enabled'
  | 'cadence'
  | 'hour'
  | 'minute'
  | 'timezone'
  | 'day_of_week'
  | 'day_of_month'
  | 'sender'
  | 'recipients'
  | 'cc_recipients'
>;

export function getAutomaticMails(): Promise<AutomaticMailDirectory> {
  return fetchFromApi<AutomaticMailDirectory>('/automatic-mails');
}

export function updateAutomaticMail(id: string, payload: AutomaticMailUpdate): Promise<AutomaticMail> {
  return fetchFromApi<AutomaticMail>(`/automatic-mails/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
