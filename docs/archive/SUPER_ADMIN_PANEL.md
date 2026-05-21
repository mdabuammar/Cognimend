# Super Admin Panel

The Super Admin Panel is the global command center for Cognimend. It provides visibility and control over the entire SaaS infrastructure without inherently compromising customer data privacy.

## Features
- **Overview**: View platform-wide statistics (users, workspaces, MRR, RAG health).
- **Users**: List all platform users. Suspend, unsuspend, force logout, or trigger password resets.
- **Workspaces**: Monitor workspace health, active plans, storage limits, and suspend rogue workspaces.
- **System Health**: Unified dashboard checking Gateway, Auth, Upload, Query, Telemetry, Drift Detector, Controller, and DB/Redis/RabbitMQ health.
- **Security & Audits**: View global failed logins, rate limit breaches, and the immutable admin action logs.
- **Billing & Usage**: See token burn rates, OpenRouter API costs, and embedding expenses aggregated across the platform.

## Privacy Guarantee
By default, the Super Admin Panel **cannot** query or read customer document content. If customer support requires inspecting a specific chunk, the Super Admin must initiate the **Emergency Access Request** flow.

## API Endpoints (Port 8008)
Requires `X-Platform-Role` headers containing `super_admin`, `support_admin`, or `security_admin`.
- `GET /overview`
- `GET /users`, `POST /users/{id}/suspend`
- `GET /workspaces`, `POST /workspaces/{id}/suspend`
- `GET /system-health`
- `GET /costs`, `GET /usage`, `GET /billing`
- `GET /security`, `GET /audit-logs`
