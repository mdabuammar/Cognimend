#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VELA Advanced Auto-Improving Test Loop
=======================================
- 10 diverse topic documents
- 30 queries (3 per topic)
- Auto-improvement loop: rechunk, increase top_k, reindex
- Loops until world-best confidence achieved (target >= 82%)
- Full results saved to JSON report
"""
import sys
import os
import json
import time
import subprocess
import requests
from datetime import datetime
from pathlib import Path

# Force UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UPLOAD_URL   = "http://localhost:8001"
QUERY_URL    = "http://localhost:8002"
BACKEND_DIR  = Path(r"D:\Project\backend")
REPORT_FILE  = Path(r"D:\Project\vela_test_report.json")

TARGET_CONFIDENCE = 82.0   # World-best target
MAX_LOOPS         = 6
TOP_K_START       = 5

procs = []

# ─── Console helpers ──────────────────────────────────────────────────────────
def p(msg):          print(msg, flush=True)
def ok(msg):         p(f"  [OK]  {msg}")
def fail(msg):       p(f"  [!!]  {msg}")
def warn(msg):       p(f"  [??]  {msg}")
def info(msg):       p(f"  [--]  {msg}")
def banner(msg):
    line = "=" * 65
    p(f"\n{line}\n  {msg}\n{line}")

# ─── 10 DIVERSE TOPIC DOCUMENTS ──────────────────────────────────────────────
DOCS = [
    {
        "filename": "hr_policies.txt",
        "title": "Human Resources Policies 2026",
        "content": """HUMAN RESOURCES POLICIES 2026

VACATION POLICY
All full-time employees receive 20 days of paid annual leave per year.
Leave accrues at 1.67 days per month starting from day one of employment.
Employees may carry over up to 5 unused vacation days into the following year.
Vacation requests must be submitted via the HR portal at least 2 weeks in advance.
Emergency leave requests are reviewed on a case-by-case basis by the direct manager.
Part-time employees receive pro-rated vacation based on their contracted hours.

SICK LEAVE POLICY
Every employee is entitled to 12 paid sick days per calendar year.
Sick leave cannot be carried forward and resets on January 1st each year.
A medical certificate is required for absences exceeding 3 consecutive days.
Sick leave cannot be used as vacation time or combined with vacation.
Employees on extended medical leave may qualify for short-term disability after 10 days.

REMOTE WORK AND HYBRID POLICY
Employees may work remotely up to 3 days per week upon manager approval.
A minimum internet speed of 25 Mbps is required for remote work eligibility.
All remote employees must be online and available during core hours: 10 AM to 3 PM.
Remote work requests are submitted 48 hours in advance via the scheduling system.
Employees in their probationary period (first 90 days) work fully on-site.

WORKING HOURS AND OVERTIME
Standard work hours are Monday to Friday, 9 AM to 6 PM with a 1-hour lunch break.
Flexible start times between 7 AM and 10 AM are permitted with manager approval.
Overtime requires prior written approval and is compensated at 1.5x the hourly rate.
Night shift differential is an additional 20% for hours worked between 10 PM and 6 AM.
Weekend work is compensated at double pay when it is company-mandated.

PERFORMANCE EVALUATION
Performance reviews are conducted bi-annually in June and December.
Each review covers technical skills, communication, teamwork, and goal attainment.
Employees scoring below expectations receive a 30-day Performance Improvement Plan (PIP).
Annual merit increases are tied to performance review outcomes.
Promotion eligibility begins after 12 months in the current role.

EXPENSE REIMBURSEMENT POLICY
All business expenses must be submitted within 30 days using the Finance portal.
Receipts are mandatory for all expenses exceeding $25.
Pre-approval from a manager is required for any expense exceeding $500.
International travel requires Director-level approval and booking via corporate travel.
Personal vehicle mileage is reimbursed at $0.67 per mile for approved business travel.

EMPLOYEE BENEFITS
Medical, dental, and vision insurance begins on the first day of employment.
Company contributes 80% of medical premium costs for employees and 50% for dependents.
401(k) retirement plan with 4% company match after 6 months of continuous service.
Annual professional development budget of $2,000 per employee for training and conferences.
Gym membership reimbursement up to $75 per month upon submission of receipts.
Employee Assistance Program (EAP) provides 8 free counseling sessions per year.

ONBOARDING PROCESS
New employees complete a 2-week structured onboarding program.
Week 1: company culture, core values, HR policies, tools setup, and team introductions.
Week 2: role-specific training, system access, and first project assignment.
A peer buddy is assigned to each new employee for the first 90 days.
Manager schedules weekly 1:1 check-ins during the first 3 months.
""",
    },
    {
        "filename": "ai_infrastructure.txt",
        "title": "AI Infrastructure and LLM Platform Engineering Guide",
        "content": """AI INFRASTRUCTURE AND LLM PLATFORM ENGINEERING GUIDE

RAG SYSTEM ARCHITECTURE
Retrieval-Augmented Generation (RAG) combines semantic search with language model generation.
Documents are split into chunks, embedded into vectors, and stored in a vector database.
At query time, the most semantically similar chunks are retrieved and passed as context to the LLM.
RAG reduces hallucination by grounding model responses in real, retrieved documents.
Production RAG requires monitoring retrieval quality, answer faithfulness, and latency continuously.

VECTOR DATABASES
Vector databases are purpose-built for high-dimensional embedding storage and approximate nearest neighbor (ANN) search.
Qdrant supports payload filtering, allowing metadata constraints on semantic search results.
Pinecone offers managed vector search with automatic scaling and load balancing.
Weaviate provides hybrid search combining dense vectors with BM25 keyword search.
Chroma is an open-source, lightweight option ideal for development and small deployments.

EMBEDDING MODELS
text-embedding-3-small by OpenAI produces 1536-dimensional vectors optimized for retrieval.
text-embedding-3-large produces higher quality embeddings at greater computational cost.
Voyage voyage-3 excels specifically at document retrieval tasks with superior recall.
Sentence-BERT models are open-source alternatives for privacy-sensitive deployments.
Embedding choice directly impacts retrieval quality, cost, and latency trade-offs.

LLM SERVING AND INFERENCE
vLLM is the industry standard for high-throughput LLM serving with PagedAttention.
TensorRT-LLM provides NVIDIA GPU-optimized inference with 3-5x throughput improvements.
llama.cpp enables CPU and low-resource inference for smaller models.
OpenRouter provides a unified API gateway to 500+ models with automatic failover.
Model quantization (INT8, INT4) reduces memory requirements with minimal quality loss.

PROMPT ENGINEERING AND OPTIMIZATION
System prompts define the model's behavior, persona, and output format constraints.
Few-shot prompting provides examples within the prompt to guide model output style.
Chain-of-thought prompting improves reasoning quality by asking models to show their work.
Temperature controls randomness: 0.0 for deterministic outputs, 1.0 for creative responses.
Max token limits must account for both input context and desired output length.

MODEL OBSERVABILITY AND MONITORING
Track input token count, output token count, latency, and cost per request.
Monitor answer confidence scores to detect model performance degradation over time.
Implement distributed tracing with OpenTelemetry to trace requests across service boundaries.
Alert on P95 latency exceeding 5 seconds or confidence averages dropping below 70%.
Log all prompts and completions in a searchable store for debugging and evaluation.

DRIFT DETECTION IN AI SYSTEMS
Data drift occurs when the statistical properties of input data change from the training distribution.
Kolmogorov-Smirnov (KS) test detects shifts in embedding distribution over time.
Welch's T-test identifies statistically significant drops in retrieval similarity scores.
Mann-Whitney U test is a non-parametric method for detecting confidence or latency degradation.
Autonomous self-healing systems detect drift and apply corrective actions without human intervention.
""",
    },
    {
        "filename": "cybersecurity.txt",
        "title": "Corporate Cybersecurity and Data Security Policy",
        "content": """CORPORATE CYBERSECURITY AND DATA SECURITY POLICY

PASSWORD AND AUTHENTICATION POLICY
All passwords must be at least 14 characters, containing uppercase, lowercase, numbers, and symbols.
Passwords must be rotated every 90 days and cannot match the last 12 passwords.
Multi-factor authentication (MFA) is mandatory for all internal systems, including email and VPN.
Biometric authentication is permitted as a secondary factor on approved company devices.
Password managers such as 1Password or Bitwarden are required for storing credentials.

DATA CLASSIFICATION LEVELS
Level 1 - Public: Marketing materials, press releases, public documentation.
Level 2 - Internal: Internal memos, process documents, employee directories.
Level 3 - Confidential: Customer data, financial records, product roadmaps.
Level 4 - Restricted: PII, health data, payment card data, credential stores.
Restricted data requires AES-256 encryption at rest and TLS 1.3 in transit.

INCIDENT RESPONSE PROCEDURE
All suspected security incidents must be reported to security@company.com within 1 hour.
The security team acknowledges all reports within 30 minutes during business hours.
Affected systems must be isolated from the network immediately upon incident confirmation.
A full root cause analysis must be completed within 5 business days of incident resolution.
All incidents are logged in the security incident management system (SIEM).

VULNERABILITY MANAGEMENT
Web application and infrastructure vulnerability scans run on a weekly schedule.
Critical vulnerabilities (CVSS score >= 9.0) must be patched within 24 hours.
High vulnerabilities (CVSS 7.0-8.9) must be patched within 7 days.
Medium and low vulnerabilities are addressed in the next regular maintenance window.
Penetration testing is performed by an external firm at least once per year.

ACCEPTABLE USE OF COMPANY ASSETS
Company devices are for business use only; personal use must be minimal and non-disruptive.
Installation of unauthorized software requires IT approval through the software request form.
Use of personal USB drives or external storage on company devices is strictly prohibited.
Company data must not be stored on personal cloud accounts (e.g., personal Google Drive).
VPN connection is mandatory when accessing company systems from any external network.

THIRD-PARTY VENDOR SECURITY
All vendors with access to company data must sign a Data Processing Agreement (DPA).
Vendors handling Restricted data undergo an annual security assessment.
Vendor access is governed by the principle of least privilege.
API keys and credentials shared with vendors must be rotated upon contract termination.

BUSINESS CONTINUITY AND DISASTER RECOVERY
Critical systems maintain a Recovery Time Objective (RTO) of 4 hours.
Recovery Point Objective (RPO) for critical data is a maximum of 1 hour.
Full disaster recovery drills are conducted quarterly with documented results.
Offsite backups are retained for a minimum of 90 days.
Backup integrity is verified monthly through automated restoration testing.
""",
    },
    {
        "filename": "finance_accounting.txt",
        "title": "Finance and Accounting Policies Manual",
        "content": """FINANCE AND ACCOUNTING POLICIES MANUAL

BUDGET PLANNING AND APPROVAL
Annual budgets are prepared by department heads each October for the following fiscal year.
Budget submissions must include a detailed justification for each line item above $10,000.
Executive Committee approval is required for departmental budgets exceeding $500,000.
Unplanned expenditures above $50,000 require CFO approval before commitment.
Quarterly budget reviews are held to compare actuals against planned expenditures.

ACCOUNTS PAYABLE PROCESS
All vendor invoices must be submitted to finance@company.com within 5 days of receipt.
Standard payment terms are net-30 unless an alternate agreement is in place.
Payments exceeding $100,000 require dual authorization from two Finance team members.
Early payment discounts (e.g., 2/10 net 30) are automatically evaluated and captured.
Vendor bank details changes require verification via a callback to the registered vendor contact.

ACCOUNTS RECEIVABLE AND COLLECTIONS
Invoices are generated and sent to customers within 24 hours of service delivery.
Payment reminders are sent at day 7, day 14, and day 28 for outstanding invoices.
Accounts overdue by 60 days are escalated to the collections process.
Write-offs for bad debts exceeding $10,000 require CFO approval.
Credit limits for new customers are assessed through a standard credit check process.

EXPENSE REIMBURSEMENT
Employees submit expense reports via the ERP system with original receipts attached.
Meal expenses are capped at $75 per person for team meals and $50 for individual business meals.
Airfare must be economy class for flights under 6 hours; business class requires VP approval.
Hotel stays are limited to approved corporate rates; choices must be within 20% of the rate.
All expenses are audited randomly; 10% of all submissions undergo full CFO audit review.

FINANCIAL REPORTING STANDARDS
All financial statements are prepared in accordance with GAAP (Generally Accepted Accounting Principles).
Monthly financial close is completed within 5 business days of month end.
Quarterly reports are reviewed by the Audit Committee before external publication.
Audited annual financial statements are prepared by an independent external auditor.
Revenue recognition follows ASC 606 standards for all software and service contracts.

FRAUD PREVENTION AND CONTROLS
Segregation of duties is enforced: the person approving a payment cannot also create the payable.
Bank reconciliations are performed weekly and reviewed by a Finance Manager.
Any employee who suspects financial fraud must report it to the Ethics Hotline anonymously.
Forensic accounting reviews are triggered for any discrepancy exceeding $5,000.
All financial system access is revoked within 24 hours of employee termination.
""",
    },
    {
        "filename": "software_engineering.txt",
        "title": "Software Engineering Best Practices and Standards",
        "content": """SOFTWARE ENGINEERING BEST PRACTICES AND STANDARDS

CODE REVIEW AND QUALITY STANDARDS
All code changes require at least one peer review before merging to main branches.
Reviewers should check for correctness, readability, test coverage, and security issues.
Pull requests must include a clear description, linked ticket, and testing notes.
No PR should exceed 400 lines of changed code; larger changes must be broken into smaller units.
Code review comments must be addressed or explicitly declined with justification before merge.

TESTING STRATEGY
Unit tests must achieve a minimum of 80% code coverage for all new code.
Integration tests verify that individual services communicate correctly.
End-to-end tests simulate real user flows and are run before every release.
Performance tests baseline P95 latency and must be run for any feature touching critical paths.
Security scanning using SAST tools runs automatically in the CI/CD pipeline on every PR.

CI/CD PIPELINE
All code is pushed to Git; the main branch is always in a deployable state.
Feature branches are merged via pull requests with automated checks.
CI pipeline: lint, unit test, integration test, SAST scan, Docker build.
CD pipeline deploys to staging automatically; production requires manual approval.
Rollback is automated if error rates exceed 1% within 10 minutes of production deployment.

SYSTEM DESIGN PRINCIPLES
Services communicate via REST APIs or async message queues (RabbitMQ, Kafka).
Each microservice owns its own database; cross-service queries violate service boundaries.
Circuit breakers prevent cascading failures when dependencies become unavailable.
All services expose /health, /health/ready, and /health/live endpoints for orchestration.
Distributed tracing with correlation IDs is implemented across all service calls.

DOCUMENTATION REQUIREMENTS
Every public API endpoint must have OpenAPI/Swagger documentation.
Architecture Decision Records (ADRs) document all significant technical decisions.
Runbooks describe operating procedures for common failure scenarios.
On-call engineers must update runbooks after every production incident.
README files in each repository describe setup, configuration, and deployment steps.

DATABASE AND STORAGE STANDARDS
All database schema changes are managed through versioned migration scripts.
Indexes must be reviewed and justified for every query added to production.
Database connection pools are configured with minimum=2, maximum=20 connections.
Sensitive data fields (passwords, PII) must never be stored in plaintext.
Backup and restore procedures are tested monthly to verify data integrity.

SECURITY IN SOFTWARE DEVELOPMENT
OWASP Top 10 vulnerabilities are reviewed and addressed in every release cycle.
All inputs are validated and sanitized before processing; never trust client data.
SQL queries use parameterized statements; string concatenation queries are forbidden.
Secrets (API keys, passwords) are stored in a secrets manager, never in source code.
Dependency versions are pinned and updated incrementally through automated PRs.
""",
    },
    {
        "filename": "healthcare_guide.txt",
        "title": "Digital Health and Telemedicine Platform Guide",
        "content": """DIGITAL HEALTH AND TELEMEDICINE PLATFORM GUIDE

TELEMEDICINE APPOINTMENT SYSTEM
Patients can book telemedicine appointments up to 30 days in advance through the patient portal.
Video consultations are available with licensed physicians, specialists, and mental health providers.
Appointment slots are 15, 30, or 60 minutes depending on consultation type.
Patients receive a reminder email and SMS 24 hours and 1 hour before their appointment.
No-show appointments within 24 hours incur a $25 fee unless cancelled beforehand.

PATIENT DATA AND PRIVACY (HIPAA COMPLIANCE)
All patient data is encrypted using AES-256 at rest and TLS 1.3 in transit.
Access to patient records is governed by role-based access control (RBAC).
Only treating physicians and authorized care team members can access patient health records.
Patient data is retained for a minimum of 7 years as required by federal regulations.
Any unauthorized access or data breach triggers mandatory HIPAA breach notification within 60 days.

ELECTRONIC HEALTH RECORDS (EHR)
Patient medical history, diagnoses, prescriptions, and lab results are stored in the EHR system.
Physicians can access and update records in real-time during telemedicine sessions.
Structured data fields (ICD-10 codes, CPT codes) are used for standardized clinical documentation.
Patients can request a complete copy of their health records within 30 days of the request.
Interoperability with external health systems is supported via HL7 FHIR standard APIs.

PRESCRIPTION AND MEDICATION MANAGEMENT
Physicians can issue electronic prescriptions directly to pharmacy networks during consultations.
Controlled substances require in-person evaluation and cannot be prescribed via telemedicine.
Medication history is automatically populated in the EHR from pharmacy fill records.
Drug interaction alerts appear automatically when new medications are prescribed.
Patients can set up medication reminder notifications via the mobile app.

AI-ASSISTED CLINICAL DECISION SUPPORT
AI models analyze patient symptoms and suggest differential diagnoses for physician review.
Drug interaction checkers use real-time FDA databases to flag dangerous combinations.
Risk stratification algorithms identify high-risk patients for proactive care management.
AI-generated clinical summaries assist physicians in preparing for consultations.
All AI recommendations are advisory only; final clinical decisions rest with the licensed physician.

MENTAL HEALTH SERVICES
Licensed therapists and psychiatrists are available for video-based mental health consultations.
Cognitive Behavioral Therapy (CBT) sessions are available in packages of 6 or 12 sessions.
Crisis intervention is available 24/7 through the emergency mental health line.
All mental health records are stored with additional confidentiality protections.
Peer support group sessions are facilitated twice weekly by licensed counselors.
""",
    },
    {
        "filename": "legal_compliance.txt",
        "title": "Legal, Compliance, and Contract Management Guide",
        "content": """LEGAL, COMPLIANCE, AND CONTRACT MANAGEMENT GUIDE

CONTRACT LIFECYCLE MANAGEMENT
All contracts must be routed through the Legal team before execution.
Standard vendor agreements are pre-approved templates; modifications require legal review.
Contracts exceeding $100,000 in value require General Counsel sign-off.
Contracts are stored in the contract management system with metadata tags for easy retrieval.
Expiry alerts are automatically triggered 90, 60, and 30 days before contract end dates.

INTELLECTUAL PROPERTY PROTECTION
All work products created by employees during the course of employment are company property.
Open-source libraries used in products must be vetted for license compatibility (no GPL for SaaS).
Trade secrets must be disclosed on a need-to-know basis under NDA obligations.
Patent filings are coordinated with external IP counsel and require CTO approval.
Employees must complete IP assignment agreements on their first day.

GDPR AND DATA PRIVACY COMPLIANCE
The company processes personal data of EU residents and is fully subject to GDPR requirements.
A Data Protection Impact Assessment (DPIA) is required before launching any new data processing activity.
Data Subject Access Requests (DSARs) must be fulfilled within 30 days of receipt.
Legitimate interest assessments document the legal basis for each data processing activity.
Cookie consent management is implemented on all public-facing websites and applications.

ANTI-CORRUPTION AND BRIBERY
Employees cannot accept gifts exceeding $50 in value from vendors or customers.
Any gift or hospitality received must be disclosed in the gifts register within 5 business days.
Facilitation payments (small payments to expedite government services) are strictly prohibited.
Third-party agents acting on behalf of the company must complete anti-bribery due diligence.
Violations of anti-corruption policy result in immediate termination and potential legal action.

REGULATORY COMPLIANCE PROGRAMS
SOC 2 Type II certification is maintained for cloud-based SaaS products.
ISO 27001 information security management is annually audited and certified.
PCI-DSS compliance is required for all systems that process payment card data.
Annual employee compliance training is mandatory; completion is tracked in the LMS.
Regulatory changes are monitored through a dedicated compliance calendar and legal alerts.

DISPUTE RESOLUTION
Disputes between employees and the company are first addressed through internal mediation.
External disputes with vendors are governed by the arbitration clause in standard agreements.
All litigation is managed by external legal counsel in coordination with the General Counsel.
Settlement agreements exceeding $50,000 require Board approval.
Class action waivers are included in all standard consumer-facing terms of service.
""",
    },
    {
        "filename": "customer_support.txt",
        "title": "Customer Support Operations and Service Excellence Guide",
        "content": """CUSTOMER SUPPORT OPERATIONS AND SERVICE EXCELLENCE GUIDE

SERVICE LEVEL AGREEMENTS (SLAs)
Priority 1 (Critical - system down): Response within 15 minutes, resolution within 4 hours.
Priority 2 (High - major feature broken): Response within 1 hour, resolution within 8 hours.
Priority 3 (Medium - partial functionality): Response within 4 hours, resolution within 24 hours.
Priority 4 (Low - minor issue or question): Response within 8 hours, resolution within 72 hours.
SLA compliance is measured monthly and targets are 99% compliance for P1 and 95% for P2.

CUSTOMER ONBOARDING PROCESS
New customers receive a welcome email within 1 hour of account activation.
A dedicated Customer Success Manager (CSM) is assigned within 24 hours.
A kickoff call is scheduled within 3 business days to align on goals and success metrics.
Implementation is completed within 30 days for standard plans and 60 days for enterprise.
Post-onboarding health check calls are scheduled at 30, 60, and 90 days.

TICKET MANAGEMENT SYSTEM
All customer issues are logged in the ticketing system with priority, category, and SLA tag.
Tickets are automatically routed to the appropriate support tier based on category rules.
Escalation from Tier 1 to Tier 2 is triggered after 30 minutes without resolution on P1 tickets.
Customers receive automatic status updates every 2 hours on P1 and P2 tickets.
Ticket resolution requires a root cause explanation and prevention steps documented.

CUSTOMER COMMUNICATION STANDARDS
All written communications use clear, jargon-free language appropriate for non-technical users.
Response templates are available for common issues but must be personalized before sending.
Negative or aggressive language from customers must be de-escalated professionally.
CSMs must follow up within 24 hours after a critical ticket is resolved to confirm satisfaction.
Net Promoter Score (NPS) surveys are sent 48 hours after ticket resolution.

KNOWLEDGE BASE AND SELF-SERVICE
The public knowledge base is updated within 24 hours of any product change.
Articles are reviewed for accuracy every 6 months by the Product and Support teams.
Video tutorials are produced for top-5 most common support request categories.
In-app help widgets are linked to relevant knowledge base articles by context.
Self-service resolution rate is targeted at 40% of all inbound support volume.

CUSTOMER FEEDBACK AND PRODUCT IMPROVEMENT
Customer feedback is tagged by product area and routed to the relevant Product Manager.
Recurring themes in support tickets are compiled into monthly product feedback reports.
Feature requests are voted on in the public roadmap portal.
Beta testing groups are formed from highly engaged customers for new feature previews.
Customer advisory boards meet quarterly to provide strategic product direction feedback.
""",
    },
    {
        "filename": "product_engineering.txt",
        "title": "Product Engineering and Agile Development Handbook",
        "content": """PRODUCT ENGINEERING AND AGILE DEVELOPMENT HANDBOOK

AGILE METHODOLOGY AND SPRINT PROCESS
Development follows 2-week sprint cycles with defined planning, execution, and review phases.
Sprint Planning occurs on the first Monday of each sprint; team commits to a sprint backlog.
Daily standup meetings (15 minutes max) align on progress, blockers, and daily priorities.
Sprint Review on the final Friday presents completed work to stakeholders for acceptance.
Sprint Retrospective identifies what went well, what didn't, and 2-3 actionable improvements.

PRODUCT BACKLOG MANAGEMENT
The Product Manager owns and maintains the prioritized product backlog.
User stories follow the format: As a [user type], I want [goal] so that [benefit].
Acceptance criteria for each story define exactly what constitutes completion.
Story points are estimated using Planning Poker with the Fibonacci scale (1, 2, 3, 5, 8, 13).
Backlog refinement sessions are held weekly to estimate and break down upcoming stories.

FEATURE DEVELOPMENT LIFECYCLE
Discovery: User research, problem definition, and hypothesis formation.
Design: UX wireframes, user testing, and design system component creation.
Development: Engineering implementation following TDD (Test-Driven Development) principles.
QA: Automated and manual testing, performance validation, security review.
Release: Feature flags control rollout; gradual traffic increase from 5% to 100%.

DESIGN SYSTEM AND FRONTEND STANDARDS
All UI components are built from the centralized design system to ensure consistency.
Accessibility (WCAG 2.1 AA compliance) is a baseline requirement for all user-facing features.
Responsive design is required for all interfaces: mobile, tablet, and desktop breakpoints.
Dark mode support is implemented for all new user interface components.
Animation and transitions must be subtle and respect prefers-reduced-motion settings.

METRICS-DRIVEN PRODUCT DEVELOPMENT
North Star Metric: Weekly Active Users achieving core product value (document queries answered).
Supporting metrics: Upload success rate, query confidence average, response latency P95.
Experiment framework: Each feature launch includes a hypothesis, metrics, and success criteria.
A/B tests require a minimum sample size calculated for 80% statistical power.
Weekly product metrics review compares actual vs. target across all key indicators.

RELEASE MANAGEMENT AND VERSIONING
Semantic versioning (MAJOR.MINOR.PATCH) is used for all public APIs and products.
Breaking changes are never introduced in minor or patch releases.
Release notes are published to the changelog within 24 hours of each release.
Hotfix releases bypass the standard sprint cycle for critical production issues only.
Rollback plan is documented and tested for every major release.
""",
    },
    {
        "filename": "data_science.txt",
        "title": "Data Science, Analytics, and Machine Learning Operations Guide",
        "content": """DATA SCIENCE, ANALYTICS, AND MACHINE LEARNING OPERATIONS GUIDE

DATA PIPELINE ARCHITECTURE
Data pipelines extract, transform, and load (ETL) raw data into analytics-ready formats.
Apache Airflow orchestrates scheduled pipeline jobs with retry logic and alerting.
dbt (data build tool) applies SQL-based transformations to raw warehouse data.
Data quality checks validate completeness, uniqueness, and referential integrity at each stage.
Pipeline failures trigger PagerDuty alerts to the on-call data engineer within 5 minutes.

DATA WAREHOUSE DESIGN
The data warehouse uses a dimensional model (star schema) for analytics-optimized querying.
Fact tables store transactional events (queries, uploads, logins) with timestamp granularity.
Dimension tables store descriptive attributes (user profiles, documents, configurations).
Slowly Changing Dimensions (SCD Type 2) preserve historical records for audit purposes.
All tables include created_at and updated_at timestamps for change tracking.

MACHINE LEARNING MODEL DEVELOPMENT
Datasets are split into 70% training, 15% validation, and 15% test sets.
Feature engineering is documented in a feature store for reproducibility across experiments.
Experiment tracking uses MLflow to log parameters, metrics, and artifacts for every run.
Model selection is based on held-out test set performance with statistical significance testing.
Cross-validation with k=5 folds is used to estimate generalization performance.

MLOPS AND MODEL DEPLOYMENT
Models are containerized and deployed via a model serving API (FastAPI or TorchServe).
Shadow deployment runs new models in parallel with production models for validation.
Champion-challenger A/B tests compare new models against the production baseline.
Model performance is monitored continuously; alerts fire when accuracy drops by >5%.
Automatic model retraining is triggered when data drift is detected by statistical tests.

STATISTICAL ANALYSIS METHODS
Hypothesis testing uses p-value < 0.05 as the threshold for statistical significance.
A/B test analysis uses Z-test for proportions and T-test for continuous metrics.
Regression analysis quantifies relationships between independent and dependent variables.
Time-series forecasting uses ARIMA, Prophet, or LSTM depending on data characteristics.
Bayesian methods provide credible intervals instead of frequentist confidence intervals.

ANALYTICS AND REPORTING STANDARDS
KPI dashboards are updated in near real-time (< 15 minute lag) from the data warehouse.
All dashboards include data freshness timestamps to indicate when data was last updated.
Metrics definitions are documented in a centralized data dictionary.
Monthly business reviews include trend analysis, anomaly explanations, and forecasts.
Self-service analytics is enabled for non-technical stakeholders via Looker or Metabase.

DATA GOVERNANCE AND PRIVACY
Personal data (PII) in the data warehouse is pseudonymized before analysis.
Data retention policies define maximum storage periods per data category.
Access to sensitive data tables requires approval from the Data Governance Committee.
Data lineage tracking shows the origin and transformations of every field in the warehouse.
Annual data audits verify compliance with GDPR, CCPA, and internal data policies.
""",
    },
]

# ─── 30 QUERIES (3 per topic) ─────────────────────────────────────────────────
QUERIES = [
    # Topic 1: HR Policies
    ("What is the vacation and annual leave policy?",             78, "HR"),
    ("How many sick leave days do employees receive per year?",   78, "HR"),
    ("What are the remote work requirements and core hours?",     75, "HR"),
    # Topic 2: AI Infrastructure
    ("How does a RAG system work and what are its components?",   72, "AI"),
    ("What embedding models are recommended for RAG retrieval?",  70, "AI"),
    ("How does autonomous drift detection work in AI systems?",   70, "AI"),
    # Topic 3: Cybersecurity
    ("What are the password and authentication requirements?",    75, "SEC"),
    ("How are security incidents reported and handled?",          73, "SEC"),
    ("What are the data classification levels?",                  75, "SEC"),
    # Topic 4: Finance
    ("What is the expense reimbursement process and limits?",     72, "FIN"),
    ("How are invoices processed and payment terms set?",         70, "FIN"),
    ("What financial reporting standards are followed?",          70, "FIN"),
    # Topic 5: Software Engineering
    ("What are the code review requirements and standards?",      75, "ENG"),
    ("What testing strategy and coverage is required?",           73, "ENG"),
    ("How does the CI/CD pipeline and deployment work?",          72, "ENG"),
    # Topic 6: Healthcare
    ("How do telemedicine appointments work?",                    70, "MED"),
    ("What HIPAA compliance measures protect patient data?",      70, "MED"),
    ("How does the AI clinical decision support system work?",    68, "MED"),
    # Topic 7: Legal
    ("What is the contract management and approval process?",     70, "LEG"),
    ("What GDPR compliance requirements are followed?",           70, "LEG"),
    ("What are the anti-corruption and gift policies?",           72, "LEG"),
    # Topic 8: Customer Support
    ("What are the customer support SLA response times?",         75, "SUP"),
    ("How does the customer onboarding process work?",            73, "SUP"),
    ("How is customer feedback used for product improvement?",    70, "SUP"),
    # Topic 9: Product Engineering
    ("How does the agile sprint development process work?",       73, "PROD"),
    ("What is the feature development lifecycle?",                72, "PROD"),
    ("How are product metrics measured and reviewed?",            70, "PROD"),
    # Topic 10: Data Science
    ("How are machine learning models developed and deployed?",   70, "DS"),
    ("What data pipeline architecture is used?",                  70, "DS"),
    ("What statistical methods are used for A/B testing?",        68, "DS"),
]


# ─── Service Management ───────────────────────────────────────────────────────
def start_services(top_k=5):
    env = os.environ.copy()
    env.update({
        "PYTHONPATH":        str(BACKEND_DIR),
        "PYTHONIOENCODING":  "utf-8",
        "REDIS_HOST":        "localhost",
        "QDRANT_HOST":       "localhost",
        "POSTGRES_HOST":     "localhost",
        "POSTGRES_DB":       "cognimend",
        "POSTGRES_USER":     "postgres",
        "POSTGRES_PASSWORD": "password123",
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY",
            "YOUR_OPENROUTER_API_KEY_HERE"),
        "OPENAI_API_KEY":    os.getenv("OPENAI_API_KEY",
            "YOUR_OPENROUTER_API_KEY_HERE"),
        "OPENROUTER_PRESET": "cheap",
        "DEFAULT_TOP_K":     str(top_k),
        "CORS_ORIGINS":      "http://localhost:8080,http://localhost:5173",
    })
    for svc, port, subdir in [
        ("Upload", 8001, "upload"),
        ("Query",  8002, "query"),
    ]:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
            cwd=str(BACKEND_DIR / "services" / subdir),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append((svc, proc))
    return procs


def stop_services():
    for name, proc in procs:
        try:
            proc.terminate(); proc.wait(timeout=5)
        except Exception:
            try: proc.kill()
            except Exception: pass
    procs.clear()


def wait_ready(url, name, timeout=90):
    p(f"  Waiting for {name}...")
    for _ in range(timeout // 2):
        try:
            r = requests.get(f"{url}/health", timeout=3)
            if r.status_code in (200, 422):
                ok(f"{name} ready"); return True
        except Exception:
            pass
        time.sleep(2)
    fail(f"{name} not ready after {timeout}s"); return False


# ─── Upload ───────────────────────────────────────────────────────────────────
def upload_doc(doc):
    try:
        files = {"file": (doc["filename"], doc["content"].encode(), "text/plain")}
        r = requests.post(f"{UPLOAD_URL}/upload",
                          files=files, data={"title": doc["title"]}, timeout=120)
        if r.status_code == 200:
            d = r.json()
            ok(f"  '{doc['title'][:40]}' -> id={d.get('document_id')} chunks={d.get('chunks')}")
            return d
        fail(f"  Upload {r.status_code}: {r.text[:120]}")
        return None
    except Exception as e:
        fail(f"  Upload error: {e}"); return None


def get_doc_ids():
    try:
        r = requests.get(f"{UPLOAD_URL}/documents", timeout=10)
        docs = r.json() if r.ok else []
        if isinstance(docs, dict): docs = docs.get("documents", [])
        return docs
    except Exception:
        return []

def wait_for_docs_ready():
    """Wait until all documents are listed as 'ready' and chunks are populated."""
    for _ in range(30): # wait up to 60s
        docs = get_doc_ids()
        ready = [d for d in docs if d.get("status") == "ready"]
        if len(ready) == len(DOCS):
            ok(f"  All {len(DOCS)} documents are ready!")
            time.sleep(2) # Give Qdrant an extra 2s to flush
            return True
        time.sleep(2)
        p(f"    ... {len(ready)}/{len(DOCS)} ready")
    warn("Documents took too long to process. Proceeding anyway.")
    return False

def reindex_all():
    try:
        r = requests.post(f"{UPLOAD_URL}/documents/reindex-all", timeout=60)
        ok(f"Reindex triggered: {r.json()}")
    except Exception as e:
        warn(f"Reindex failed: {e}")


def rechunk_all():
    try:
        r = requests.post(f"{UPLOAD_URL}/rechunk-all", timeout=120)
        ok(f"Rechunk triggered: {r.json()}")
        time.sleep(5)
    except Exception as e:
        warn(f"Rechunk failed: {e}")


# ─── Query ────────────────────────────────────────────────────────────────────
def run_query(question, top_k=5):
    try:
        r = requests.post(f"{QUERY_URL}/query",
                          json={"question": question, "top_k": top_k}, timeout=90)
        if r.ok:
            d = r.json()
            return {
                "success":    True,
                "confidence": round(d.get("confidence", 0), 1),
                "latency_ms": d.get("latency_ms", 0),
                "citations":  len(d.get("citations", [])),
                "answer":     d.get("answer", "")[:80],
            }
        fail(f"Query {r.status_code}: {r.text[:100]}")
    except Exception as e:
        fail(f"Query error: {e}")
    return {"success": False, "confidence": 0, "latency_ms": 0, "citations": 0}


# ─── Improvement Strategies ───────────────────────────────────────────────────
def apply_improvements(loop_num, avg_conf, top_k, low_topics):
    """Return new top_k after applying improvements."""
    p(f"\n  [STRATEGY] Avg confidence {avg_conf:.1f}% — applying auto-improvements...")

    if loop_num == 1:
        # Always rechunk first to get better chunk boundaries
        p("  [FIX-1] Rechunking all documents for better context boundaries...")
        rechunk_all()
        new_k = min(top_k + 2, 10)
        p(f"  [FIX-2] Increasing top_k: {top_k} -> {new_k}")
        return new_k

    if loop_num == 2:
        p("  [FIX-3] Reindexing all documents to refresh embeddings...")
        reindex_all()
        time.sleep(8)
        new_k = min(top_k + 1, 12)
        p(f"  [FIX-4] Increasing top_k: {top_k} -> {new_k}")
        return new_k

    if loop_num >= 3:
        new_k = min(top_k + 1, 15)
        p(f"  [FIX-5] Final top_k boost: {top_k} -> {new_k}")
        return new_k

    return top_k


# ─── Report Writer ─────────────────────────────────────────────────────────────
def save_report(all_loops):
    best = max(all_loops, key=lambda x: x.get("avg_confidence", 0))
    report = {
        "generated_at": datetime.now().isoformat(),
        "target_confidence": TARGET_CONFIDENCE,
        "total_loops": len(all_loops),
        "best_loop": best,
        "all_loops": all_loops,
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    ok(f"Report saved -> {REPORT_FILE}")


# ─── MAIN LOOP ─────────────────────────────────────────────────────────────────
def main():
    banner("VELA Advanced Auto-Improving Test Loop")
    p(f"  Topics: {len(DOCS)} | Queries: {len(QUERIES)} | Target: {TARGET_CONFIDENCE}% confidence")
    p(f"  Max loops: {MAX_LOOPS} | Started: {datetime.now().strftime('%H:%M:%S')}\n")

    all_loops = []
    top_k = TOP_K_START
    docs_uploaded = False  # upload once, reuse in subsequent loops

    for loop in range(1, MAX_LOOPS + 1):
        banner(f"LOOP {loop}/{MAX_LOOPS}  |  top_k={top_k}")
        loop_start = time.time()
        loop_data = {"loop": loop, "top_k": top_k}

        # ── Start services ─────────────────────────────────────────
        banner(f"LOOP {loop}: Starting services")
        start_services(top_k=top_k)
        upload_ok = wait_ready(UPLOAD_URL, "Upload Service")
        query_ok  = wait_ready(QUERY_URL,  "Query Service")

        if not upload_ok or not query_ok:
            fail("Services failed — retrying loop"); stop_services(); time.sleep(5); continue

        # ── Upload documents (first loop only) ─────────────────────
        if not docs_uploaded:
            banner(f"LOOP {loop}: Uploading {len(DOCS)} documents")
            uploaded = 0
            for doc in DOCS:
                if upload_doc(doc): uploaded += 1
            p(f"\n  UPLOAD RESULT: {uploaded}/{len(DOCS)}")
            docs_uploaded = uploaded == len(DOCS)
            loop_data["uploads"] = {"success": uploaded, "total": len(DOCS)}
            
            p("\n  Waiting for background processing (embedding into Qdrant)...")
            wait_for_docs_ready()
        else:
            p("\n  [SKIP] Documents already uploaded — using existing knowledge base")
            loop_data["uploads"] = {"success": len(DOCS), "total": len(DOCS), "reused": True}

        # ── Run 30 queries ─────────────────────────────────────────
        banner(f"LOOP {loop}: Running {len(QUERIES)} queries  (top_k={top_k})")
        q_results = []
        topic_stats = {}

        for i, (question, min_conf, topic) in enumerate(QUERIES, 1):
            res = run_query(question, top_k=top_k)
            res["question"] = question
            res["min_conf"] = min_conf
            res["topic"] = topic
            q_results.append(res)

            # topic tracking
            if topic not in topic_stats:
                topic_stats[topic] = {"confs": [], "label": topic}
            topic_stats[topic]["confs"].append(res["confidence"])

            status = "OK" if res["confidence"] >= min_conf else "LOW"
            p(f"  [{i:02d}/{len(QUERIES)}] [{topic:4s}] [{status}] "
              f"conf={res['confidence']:5.1f}% lat={res['latency_ms']:5}ms "
              f"cit={res['citations']} | {question[:50]}")

        # ── Calculate stats ────────────────────────────────────────
        ok_qs   = [q for q in q_results if q["success"]]
        avg_c   = sum(q["confidence"] for q in ok_qs) / max(len(ok_qs), 1)
        avg_lat = sum(q["latency_ms"] for q in ok_qs) / max(len(ok_qs), 1)
        met     = sum(1 for q in ok_qs if q["confidence"] >= q["min_conf"])
        high80  = sum(1 for q in ok_qs if q["confidence"] >= 80)
        elapsed = time.time() - loop_start

        # per-topic averages
        for t, ts in topic_stats.items():
            ts["avg"] = round(sum(ts["confs"]) / len(ts["confs"]), 1)

        low_topics = [t for t, ts in topic_stats.items() if ts["avg"] < 72]

        loop_data.update({
            "avg_confidence": round(avg_c, 2),
            "met_min_confidence": met,
            "above_80_pct": high80,
            "total_queries": len(QUERIES),
            "successful_queries": len(ok_qs),
            "avg_latency_ms": round(avg_lat),
            "elapsed_seconds": round(elapsed),
            "per_topic": {t: ts["avg"] for t, ts in topic_stats.items()},
            "query_results": q_results,
        })
        all_loops.append(loop_data)

        # ── Print loop summary ─────────────────────────────────────
        banner(f"LOOP {loop} SUMMARY")
        p(f"  Avg Confidence  : {avg_c:.1f}%   (target: {TARGET_CONFIDENCE}%)")
        p(f"  Min-conf Met    : {met}/{len(QUERIES)}")
        p(f"  Above 80%       : {high80}/{len(QUERIES)}")
        p(f"  Avg Latency     : {avg_lat:.0f}ms")
        p(f"  Elapsed         : {elapsed:.0f}s")
        p(f"\n  Per-Topic Averages:")
        for t, ts in sorted(topic_stats.items(), key=lambda x: x[1]["avg"], reverse=True):
            bar = "#" * int(ts["avg"] / 5)
            flag = " <<< LOW" if ts["avg"] < 72 else ""
            p(f"    {t:6s} {ts['avg']:5.1f}%  [{bar:<20}]{flag}")

        save_report(all_loops)

        # ── Check success ──────────────────────────────────────────
        if avg_c >= TARGET_CONFIDENCE and met >= len(QUERIES) * 0.90:
            banner("WORLD-BEST RESULT ACHIEVED!")
            p(f"  Avg confidence: {avg_c:.1f}% >= target {TARGET_CONFIDENCE}%")
            p(f"  Queries meeting confidence: {met}/{len(QUERIES)}")
            p(f"  Above 80%: {high80}/{len(QUERIES)}")
            p(f"  Total loops: {loop}")
            p(f"  Report: {REPORT_FILE}")
            stop_services()
            return 0

        stop_services()

        if loop < MAX_LOOPS:
            top_k = apply_improvements(loop, avg_c, top_k, low_topics)
            p(f"\n  Restarting loop {loop + 1} with top_k={top_k}...\n")
            time.sleep(4)

    # ── Final report ───────────────────────────────────────────────────────
    best = max(all_loops, key=lambda x: x.get("avg_confidence", 0))
    banner("FINAL REPORT — BEST RESULT")
    p(f"  Best avg confidence : {best['avg_confidence']}%  (loop {best['loop']})")
    p(f"  Best top_k used     : {best['top_k']}")
    p(f"  Queries above 80%   : {best['above_80_pct']}/{best['total_queries']}")
    p(f"  Report file         : {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        p("\n  Interrupted — stopping services...")
        stop_services()
        sys.exit(0)
