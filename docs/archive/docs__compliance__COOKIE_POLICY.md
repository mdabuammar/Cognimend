# Cookie Policy
## DriftGuard Cookie Notice

**Last Updated:** January 2024  
**Version:** 1.0

---

## 1. What Are Cookies?

Cookies are small text files placed on your device when you visit our website. They help us recognize your device and remember your preferences.

---

## 2. How We Use Cookies

### 2.1 Strictly Necessary Cookies

These cookies are essential for the website to function properly. They cannot be disabled.

| Cookie Name | Purpose | Duration | Type |
|-------------|---------|----------|------|
| `session_id` | Session management | Session | First-party |
| `csrf_token` | Security (CSRF protection) | Session | First-party |
| `auth_token` | Authentication | 7 days | First-party |

**Legal Basis:** Legitimate interest (necessary for service)

### 2.2 Functional Cookies

These cookies remember your preferences and settings.

| Cookie Name | Purpose | Duration | Type |
|-------------|---------|----------|------|
| `theme` | Dark/light mode preference | 1 year | First-party |
| `language` | Language preference | 1 year | First-party |
| `sidebar_state` | UI preferences | 1 year | First-party |

**Legal Basis:** Consent (can be disabled)

### 2.3 Analytics Cookies

These cookies help us understand how visitors use our website.

| Cookie Name | Purpose | Duration | Type |
|-------------|---------|----------|------|
| `_analytics_id` | Anonymous usage tracking | 2 years | First-party |
| `_session_count` | Session counting | 30 days | First-party |

**Legal Basis:** Consent (requires opt-in)

**Note:** We do NOT use third-party analytics (Google Analytics, etc.) by default.

### 2.4 Consent Cookies

These cookies store your cookie preferences.

| Cookie Name | Purpose | Duration | Type |
|-------------|---------|----------|------|
| `driftguard_consent` | Cookie consent preferences | 1 year | First-party |
| `consent_timestamp` | When consent was given | 1 year | First-party |

**Legal Basis:** Legitimate interest (required for compliance)

---

## 3. Third-Party Cookies

We minimize third-party cookies. Currently we use:

| Provider | Purpose | Cookies | Privacy Policy |
|----------|---------|---------|----------------|
| None | N/A | N/A | N/A |

**Note:** We do not use advertising cookies or social media tracking cookies.

---

## 4. Managing Cookies

### 4.1 Our Consent Manager

You can manage your cookie preferences at any time:
1. Click the "Cookie Settings" link in the footer
2. Or visit: [yoursite.com/privacy-settings]

### 4.2 Browser Settings

You can also control cookies through your browser:

| Browser | Instructions |
|---------|--------------|
| Chrome | Settings → Privacy and Security → Cookies |
| Firefox | Settings → Privacy & Security → Cookies |
| Safari | Preferences → Privacy → Cookies |
| Edge | Settings → Cookies and site permissions |

### 4.3 Opt-Out Links

- **Analytics:** Disable in Privacy Settings
- **Functional:** Disable in Privacy Settings

---

## 5. Cookie Details by Category

### Strictly Necessary (Cannot be disabled)

```
session_id
├── Purpose: Maintain your login session
├── Duration: Session (deleted when browser closed)
├── Data: Encrypted session identifier
└── Sharing: None

csrf_token
├── Purpose: Prevent cross-site request forgery attacks
├── Duration: Session
├── Data: Random security token
└── Sharing: None

auth_token
├── Purpose: Keep you logged in
├── Duration: 7 days (or until logout)
├── Data: Encrypted authentication token
└── Sharing: None
```

### Functional (Consent required)

```
theme
├── Purpose: Remember your dark/light mode preference
├── Duration: 1 year
├── Data: "dark" or "light"
└── Sharing: None

language
├── Purpose: Remember your language preference
├── Duration: 1 year
├── Data: Language code (e.g., "en", "de")
└── Sharing: None
```

### Analytics (Consent required)

```
_analytics_id
├── Purpose: Count unique visitors
├── Duration: 2 years
├── Data: Random anonymous identifier
└── Sharing: None (first-party only)
```

---

## 6. Data Retention

| Cookie Category | Retention Period |
|-----------------|------------------|
| Session cookies | Until browser closed |
| Authentication | 7 days or until logout |
| Preferences | 1 year |
| Analytics | 2 years |
| Consent records | 1 year |

---

## 7. Legal Information

### 7.1 Legal Basis

| Cookie Type | Legal Basis | GDPR Article |
|-------------|-------------|--------------|
| Strictly Necessary | Legitimate Interest | Art. 6(1)(f) |
| Functional | Consent | Art. 6(1)(a) |
| Analytics | Consent | Art. 6(1)(a) |

### 7.2 Your Rights

Under GDPR, you have the right to:
- Access your cookie data
- Withdraw consent at any time
- Request deletion of cookie data
- Object to processing

### 7.3 Supervisory Authority

If you have concerns, you can contact your local data protection authority.

---

## 8. Updates to This Policy

We may update this Cookie Policy periodically. Changes will be posted on this page with an updated revision date.

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2024 | Initial version |

---

## 9. Contact Us

For questions about our use of cookies:

**Email:** privacy@driftguard.com  
**Address:** [Your Business Address]  
**DPO:** dpo@driftguard.com

---

## 10. Cookie Consent Implementation

### For Developers

Our cookie consent is implemented as follows:

```javascript
// Consent check before setting non-essential cookies
if (hasConsent('analytics')) {
  setAnalyticsCookie();
}

if (hasConsent('functional')) {
  setPreferenceCookie();
}

// Strictly necessary cookies are always set
setSessionCookie(); // No consent needed
```

### Consent Storage

Consent preferences are stored in:
- `localStorage`: `driftguard_consent`
- Backend: For compliance records

### Consent Record

Each consent record includes:
- Timestamp
- Policy version
- Consent choices
- IP address (masked)
