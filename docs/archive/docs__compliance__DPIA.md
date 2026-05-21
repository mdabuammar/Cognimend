# Data Protection Impact Assessment (DPIA)
## DriftGuard RAG System

**Document Version:** 1.0  
**Date:** January 2024  
**Status:** Draft  
**Owner:** Data Protection Officer  

---

## 1. Project Overview

### 1.1 Description
DriftGuard is a Retrieval-Augmented Generation (RAG) system that allows users to:
- Upload documents for AI-powered search and retrieval
- Query documents using natural language
- Receive AI-generated responses based on document content
- Track model drift and performance

### 1.2 Purpose of Processing
To provide AI-powered document search and question-answering services to users.

### 1.3 Data Controller
**Organization:** [Your Organization Name]  
**Address:** [Business Address]  
**Contact:** privacy@driftguard.com  

### 1.4 Data Protection Officer
**Name:** [DPO Name]  
**Email:** dpo@driftguard.com  
**Phone:** [DPO Phone]  

---

## 2. Necessity and Proportionality

### 2.1 Lawful Basis for Processing

| Data Type | Lawful Basis | Justification |
|-----------|--------------|---------------|
| Account data | Contract (Art. 6(1)(b)) | Required to provide service |
| Document content | Consent (Art. 6(1)(a)) | User explicitly uploads |
| Query history | Legitimate interest (Art. 6(1)(f)) | Service improvement |
| Analytics | Consent (Art. 6(1)(a)) | Optional, can be disabled |
| AI processing | Consent (Art. 6(1)(a)) | Explicit opt-in required |

### 2.2 Data Minimization

| Principle | Implementation |
|-----------|----------------|
| Collection limitation | Only collect data necessary for service |
| Purpose limitation | Data used only for stated purposes |
| Storage limitation | Defined retention periods with auto-deletion |
| Accuracy | Users can correct their data via DSAR |

### 2.3 Necessity Assessment

**Question:** Is this processing necessary to achieve the purpose?

**Answer:** Yes. The core functionality requires:
- Document upload for retrieval
- Query processing for search
- AI models for response generation

**Alternatives Considered:**
1. **On-premise only processing:** Rejected - reduces service availability
2. **No AI processing:** Rejected - defeats purpose of service
3. **Anonymous processing only:** Partially implemented - queries can be anonymized

---

## 3. Data Processing Activities

### 3.1 Data Categories

| Category | Data Elements | Special Category? |
|----------|---------------|-------------------|
| Identity | Email, user ID, name | No |
| Documents | File content, metadata | Potentially (user-uploaded) |
| Queries | Search text, timestamps | No |
| Feedback | Ratings, comments | No |
| Technical | IP address, browser | No |
| AI Outputs | Generated responses | No |

### 3.2 Data Flow Diagram

```
[User] --> [Frontend] --> [Backend API] --> [Vector DB]
                |              |                |
                v              v                v
           [Auth Service] [OpenAI/OpenRouter] [PostgreSQL]
                                |
                                v
                         [AI Processing]
```

### 3.3 Third-Party Processors

| Processor | Purpose | Data Shared | DPA Signed? |
|-----------|---------|-------------|-------------|
| OpenAI | LLM processing | Queries, document chunks | ⬜ Required |
| OpenRouter | LLM routing | Queries, document chunks | ⬜ Required |
| Supabase | Database | All user data | ⬜ Required |
| Qdrant | Vector storage | Document embeddings | ⬜ Required |
| Upstash | Redis caching | Session data | ⬜ Required |

---

## 4. Risk Assessment

### 4.1 Risk Matrix

| Risk | Likelihood | Impact | Overall | Mitigation |
|------|------------|--------|---------|------------|
| Unauthorized data access | Medium | High | High | Access controls, encryption |
| Data breach | Low | High | Medium | Security monitoring, encryption |
| PII in documents | High | Medium | High | PII scanner, user warnings |
| Third-party data exposure | Medium | High | High | DPAs, minimal data sharing |
| Model hallucination | High | Low | Medium | Disclaimer, human review |
| User rights violation | Low | High | Medium | Automated DSAR system |
| Cross-border transfer | High | Medium | Medium | SCCs with processors |

### 4.2 Detailed Risk Analysis

#### Risk 1: PII in Uploaded Documents
**Description:** Users may upload documents containing personal data of third parties.

**Impact:** High - Could constitute unauthorized processing of third-party data.

**Mitigations:**
- ✅ PII scanner warns users before upload
- ✅ Terms require user to have rights to upload
- ✅ Automatic PII redaction available
- ⬜ Manual review for enterprise accounts

#### Risk 2: AI Processing of Sensitive Data
**Description:** Queries and documents are sent to third-party AI providers.

**Impact:** High - Data leaves our infrastructure.

**Mitigations:**
- ✅ Explicit consent required for AI processing
- ✅ Clear disclosure in privacy policy
- ⬜ DPA with OpenAI/OpenRouter
- ⬜ Option for on-premise LLM

#### Risk 3: Data Retention Exceeds Necessity
**Description:** Data stored longer than necessary.

**Impact:** Medium - Violates storage limitation principle.

**Mitigations:**
- ✅ Defined retention policies
- ✅ Automatic deletion for some categories
- ✅ User can request deletion (DSAR)

---

## 5. Safeguards and Controls

### 5.1 Technical Measures

| Measure | Status | Notes |
|---------|--------|-------|
| Encryption in transit (TLS 1.3) | ✅ Implemented | All connections |
| Encryption at rest (AES-256) | ⬜ Partial | Database encrypted |
| Access controls | ✅ Implemented | Role-based access |
| Audit logging | ✅ Implemented | All data access logged |
| PII detection | ✅ Implemented | Pre-upload scanning |
| Data minimization | ✅ Implemented | Only necessary data |
| Pseudonymization | ⬜ Partial | User IDs hashed in logs |

### 5.2 Organizational Measures

| Measure | Status | Notes |
|---------|--------|-------|
| Privacy policy | ✅ Published | v1.0 |
| Staff training | ⬜ Planned | Q2 2024 |
| Incident response plan | ⬜ Draft | In progress |
| DPA with processors | ⬜ In progress | 3/5 signed |
| Regular audits | ⬜ Planned | Quarterly |

### 5.3 Data Subject Rights

| Right | Implementation | Automation |
|-------|----------------|------------|
| Access (Art. 15) | ✅ DSAR endpoint | Full |
| Rectification (Art. 16) | ✅ Manual process | Partial |
| Erasure (Art. 17) | ✅ DSAR endpoint | Full |
| Restriction (Art. 18) | ✅ Manual process | Partial |
| Portability (Art. 20) | ✅ Export endpoint | Full |
| Objection (Art. 21) | ✅ Consent manager | Full |

---

## 6. Consultation

### 6.1 Data Subject Consultation
**Method:** User research, beta feedback
**Findings:** Users want clear control over AI processing of their data

### 6.2 DPO Consultation
**Date:** [Date]
**Recommendations:**
1. Implement explicit consent for AI processing ✅
2. Add PII scanning before upload ✅
3. Create data export functionality ✅
4. Sign DPAs with all processors ⬜

### 6.3 Supervisory Authority Consultation
**Required?** No - risks adequately mitigated
**If required, contact:** [Relevant supervisory authority]

---

## 7. Decision and Sign-Off

### 7.1 Residual Risks
After implementing all mitigations, the following residual risks remain:

1. **Low:** Users may still upload third-party PII despite warnings
2. **Low:** AI providers may have security incidents
3. **Low:** Complex DSAR requests may exceed 30-day deadline

### 7.2 Decision

☐ **Proceed** - Risks are acceptable with current mitigations  
☐ **Proceed with conditions** - Additional mitigations required (listed below)  
☐ **Do not proceed** - Risks are unacceptable  
☐ **Consult supervisory authority** - High residual risk  

### 7.3 Conditions (if applicable)
1. Sign DPAs with all processors before production launch
2. Complete staff privacy training
3. Finalize incident response plan

### 7.4 Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Project Owner | | | |
| Data Protection Officer | | | |
| IT Security | | | |
| Legal | | | |

---

## 8. Review Schedule

| Review Type | Frequency | Next Review |
|-------------|-----------|-------------|
| Annual review | Yearly | January 2025 |
| Post-incident | As needed | N/A |
| Significant change | As needed | N/A |

---

## Appendix A: Data Processing Register

| Processing Activity | Purpose | Data Categories | Recipients | Retention | Legal Basis |
|---------------------|---------|-----------------|------------|-----------|-------------|
| User registration | Account creation | Email, password | None | 3 years | Contract |
| Document upload | RAG indexing | Document content | AI providers | 2 years | Consent |
| Query processing | Search | Query text | AI providers | 90 days | Consent |
| Analytics | Improvement | Usage data | None | 2 years | Consent |

## Appendix B: International Transfers

| Recipient | Country | Safeguard |
|-----------|---------|-----------|
| OpenAI | USA | SCCs + DPA |
| Supabase | USA/EU | SCCs |
| Qdrant | EU | Adequacy |

## Appendix C: Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2024 | [Author] | Initial version |
