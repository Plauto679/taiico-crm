import { MailConfigurationView } from '@/components/mail/MailConfigurationView';

export default function MailConfigurationPage() {
    return (
        <div className="h-full overflow-y-auto p-8">
            <h1 className="mb-6 text-2xl font-bold text-white">Configuración de Mail</h1>
            <MailConfigurationView />
        </div>
    );
}
