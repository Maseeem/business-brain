# WhatsApp Daily Reporting Setup

Business Brain uses the official WhatsApp Business Platform / Cloud API through `whatsapp_service.py`.

## Secrets

Configure these through Streamlit Cloud Secrets or environment variables. Never commit real values:

- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_BUSINESS_ACCOUNT_ID`
- `WHATSAPP_DEFAULT_RECIPIENT` (optional default test recipient)

The access token is never stored in SQLite and is never rendered in the UI, reports, PDFs, or logs.

## Admin controls

The WhatsApp page is visible only to Owner/Admin roles. Managers and Employees do not receive WhatsApp configuration controls or credentials.

The admin can enable daily reports, configure role-specific recipients, select report categories, send a test message, preview the role-scoped report, send the current report, and download the role-scoped PDF.

## Scheduling

Streamlit's normal request/response execution is not treated as a persistent daily worker. For automatic delivery, run:

```text
python send_daily_report.py 1
```

from an external scheduler such as cron, GitHub Actions, Cloud Scheduler, or another deployment-supported job runner. The script reads the saved report settings and sends role-scoped text plus PDF documents where the WhatsApp Cloud API media endpoint is available.

Manual sending is always available from the admin WhatsApp page.
