# WhatsApp renewal test setup

This integration is test-only. It refuses to send unless `WHATSAPP_TEST_MODE=true`
and the configured recipient is present in `WHATSAPP_TEST_ALLOWLIST`.

## Meta template

Create and approve a Utility template in WhatsApp Manager:

- Name: `renewal_ready_test`
- Language: Spanish (Mexico), `es_MX`
- Body:

```text
Hola, {{1}}. Ya está disponible la renovación de tu póliza MetLife GMM {{2}} para el periodo {{3}}–{{4}}. Tu agente {{5}} dará seguimiento contigo. Por seguridad, no compartimos documentos sensibles directamente sin validación.
```

Parameter order:

1. Client name
2. Policy number
3. Period start year
4. Period end year
5. Responsible agent name

## Local configuration

Copy the WhatsApp values shown by Meta into `backend/.env`. Never commit tokens.

```dotenv
WHATSAPP_TEST_MODE=true
WHATSAPP_TEST_RECIPIENTS=<comma-separated E.164 test numbers, digits only>
WHATSAPP_TEST_ALLOWLIST=<the same comma-separated test numbers>
WHATSAPP_ACCESS_TOKEN=<temporary or system-user token>
WHATSAPP_PHONE_NUMBER_ID=<Meta phone-number ID>
WHATSAPP_BUSINESS_ACCOUNT_ID=<Meta WABA ID>
WHATSAPP_API_VERSION=<version from Meta's generated API example>
WHATSAPP_RENEWAL_TEMPLATE_NAME=renewal_ready_test
```

Use `POST /whatsapp/renewal/preview` before every test send. The real send endpoint
is `POST /whatsapp/renewal/send-test`. Both accept:

```json
{
  "client_name": "Cliente Prueba",
  "policy_number": "1330274",
  "period_start": 2026,
  "period_end": 2027,
  "agent_name": "Agente Taiico"
}
```

Every send attempt is recorded in `agent_actions`. The access token and full Meta
response are never stored there.

When using Meta's test phone number, every recipient must also be added and verified
in Meta's test-recipient list. A production WhatsApp Business phone number does not
use that test-recipient list, but customer opt-in and approved templates are still
required.
