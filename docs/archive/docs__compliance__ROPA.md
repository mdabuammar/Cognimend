# Records of Processing Activities (ROPA)
## GDPR Article 30 Compliance

**Organization:** DriftGuard  
**Document Version:** 1.0  
**Last Updated:** January 2024  
**Data Protection Officer:** dpo@driftguard.com  

---

## Controller Information

| Field | Value |
|-------|-------|
| Organization Name | [Your Organization Name] |
| Address | [Business Address] |
| Country | [Country] |
| Representative (if outside EU) | [Representative Name/Address] |
| DPO Contact | dpo@driftguard.com |

---

## Processing Activity 1: User Account Management

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-001 |
| **Activity Name** | User Account Management |
| **Purpose** | Create and maintain user accounts for service access |
| **Categories of Data Subjects** | Registered users |
| **Categories of Personal Data** | Email address, hashed password, user ID, account preferences |
| **Special Categories** | None |
| **Source of Data** | Directly from data subject |
| **Legal Basis** | Contract (Art. 6(1)(b)) |
| **Recipients** | None (internal only) |
| **International Transfers** | USA (Supabase) - SCCs in place |
| **Retention Period** | 3 years after last activity |
| **Technical Measures** | Password hashing (bcrypt), TLS encryption, access controls |
| **Organizational Measures** | Staff training, access logging |

---

## Processing Activity 2: Document Processing (RAG)

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-002 |
| **Activity Name** | Document Upload and Processing |
| **Purpose** | Process uploaded documents for AI-powered search and retrieval |
| **Categories of Data Subjects** | Registered users, potentially third parties mentioned in documents |
| **Categories of Personal Data** | Document content (may contain any personal data uploaded by user) |
| **Special Categories** | Potentially (user responsibility to not upload) |
| **Source of Data** | User uploads |
| **Legal Basis** | Consent (Art. 6(1)(a)) |
| **Recipients** | OpenAI/OpenRouter (AI processing), Qdrant (vector storage) |
| **International Transfers** | USA (OpenAI) - SCCs in place |
| **Retention Period** | 2 years or until user deletion |
| **Technical Measures** | PII scanning, encryption at rest, access controls |
| **Organizational Measures** | Terms of service, PII warnings, DPAs with processors |

---

## Processing Activity 3: Query Processing

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-003 |
| **Activity Name** | Search Query Processing |
| **Purpose** | Process natural language queries to search documents |
| **Categories of Data Subjects** | Registered users |
| **Categories of Personal Data** | Query text, timestamps, user ID |
| **Special Categories** | Potentially (if user includes in query) |
| **Source of Data** | User input |
| **Legal Basis** | Consent for AI processing (Art. 6(1)(a)) |
| **Recipients** | OpenAI/OpenRouter (AI processing) |
| **International Transfers** | USA (OpenAI) - SCCs in place |
| **Retention Period** | 90 days |
| **Technical Measures** | Query sanitization, logging without PII |
| **Organizational Measures** | Clear disclosure in privacy policy |

---

## Processing Activity 4: User Feedback

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-004 |
| **Activity Name** | User Feedback Collection |
| **Purpose** | Collect feedback on AI response quality for improvement |
| **Categories of Data Subjects** | Registered users |
| **Categories of Personal Data** | Feedback ratings, optional comments, user ID |
| **Special Categories** | None |
| **Source of Data** | User input |
| **Legal Basis** | Consent (Art. 6(1)(a)) |
| **Recipients** | None (internal only) |
| **International Transfers** | None |
| **Retention Period** | 1 year |
| **Technical Measures** | Encryption, access controls |
| **Organizational Measures** | Optional collection, clear purpose |

---

## Processing Activity 5: Analytics

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-005 |
| **Activity Name** | Usage Analytics |
| **Purpose** | Understand service usage to improve performance |
| **Categories of Data Subjects** | All users |
| **Categories of Personal Data** | Page views, feature usage, session duration (anonymized) |
| **Special Categories** | None |
| **Source of Data** | Automatic collection |
| **Legal Basis** | Consent (Art. 6(1)(a)) |
| **Recipients** | None (internal only) |
| **International Transfers** | None |
| **Retention Period** | 2 years |
| **Technical Measures** | Anonymization, aggregation |
| **Organizational Measures** | Consent required, opt-out available |

---

## Processing Activity 6: Audit Logging

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-006 |
| **Activity Name** | Security Audit Logging |
| **Purpose** | Security monitoring and compliance |
| **Categories of Data Subjects** | All users, administrators |
| **Categories of Personal Data** | Hashed user ID, masked IP, action performed, timestamp |
| **Special Categories** | None |
| **Source of Data** | Automatic system logging |
| **Legal Basis** | Legal obligation (Art. 6(1)(c)), Legitimate interest (Art. 6(1)(f)) |
| **Recipients** | None (internal only) |
| **International Transfers** | None |
| **Retention Period** | 7 years (legal requirement) |
| **Technical Measures** | User ID hashing, IP masking, immutable logs |
| **Organizational Measures** | Access restricted to security team |

---

## Processing Activity 7: Consent Management

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-007 |
| **Activity Name** | Consent Record Keeping |
| **Purpose** | Maintain records of consent for GDPR compliance |
| **Categories of Data Subjects** | All users |
| **Categories of Personal Data** | User ID, consent choices, timestamps, IP address |
| **Special Categories** | None |
| **Source of Data** | User consent actions |
| **Legal Basis** | Legal obligation (Art. 6(1)(c)) |
| **Recipients** | None (internal only) |
| **International Transfers** | None |
| **Retention Period** | 7 years (compliance requirement) |
| **Technical Measures** | Immutable consent records |
| **Organizational Measures** | Versioned consent policies |

---

## Processing Activity 8: DSAR Processing

| Field | Description |
|-------|-------------|
| **Processing ID** | PA-008 |
| **Activity Name** | Data Subject Access Requests |
| **Purpose** | Respond to user rights requests (access, deletion, etc.) |
| **Categories of Data Subjects** | Users who submit DSARs |
| **Categories of Personal Data** | Request details, user identity verification |
| **Special Categories** | None |
| **Source of Data** | User request |
| **Legal Basis** | Legal obligation (Art. 6(1)(c)) |
| **Recipients** | None (internal only) |
| **International Transfers** | None |
| **Retention Period** | 7 years (compliance evidence) |
| **Technical Measures** | Secure DSAR portal |
| **Organizational Measures** | 30-day response deadline tracking |

---

## Summary of International Transfers

| Recipient | Country | Data Transferred | Safeguard | DPA Status |
|-----------|---------|------------------|-----------|------------|
| Supabase | USA | Account data, documents | SCCs | ⬜ Pending |
| OpenAI | USA | Queries, document chunks | SCCs | ⬜ Pending |
| OpenRouter | USA | Queries, document chunks | SCCs | ⬜ Pending |
| Qdrant | EU (Germany) | Vector embeddings | Adequacy | ⬜ Pending |
| Upstash | EU | Session cache | Adequacy | ⬜ Pending |

---

## Summary of Retention Periods

| Data Category | Retention Period | Auto-Delete | Legal Basis |
|---------------|------------------|-------------|-------------|
| User accounts | 3 years after last activity | No | Contract |
| Documents | 2 years | Yes | Consent |
| Queries | 90 days | Yes | Consent |
| Feedback | 1 year | Yes | Consent |
| Analytics | 2 years | Yes | Consent |
| Audit logs | 7 years | No | Legal obligation |
| Consent records | 7 years | No | Legal obligation |
| DSAR records | 7 years | No | Legal obligation |

---

## Review and Update History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2024 | [Author] | Initial version |

---

## Certification

I certify that this record of processing activities is accurate and complete to the best of my knowledge.

**Data Protection Officer:**  
Name: _______________________  
Signature: ___________________  
Date: _______________________
