# Nepal Form Autofill Startup Launch Plan

## Goal

Launch Nepal Form Autofill as a real service for Nepali users who need help filling passport, driving license, voter, college, job, and similar online forms from document photos/PDFs.

Monthly first revenue target: NPR 10,000.

## Product Position

Nepal Form Autofill is not a CAPTCHA bypass tool and not a government portal clone. It is a review-first assistant:

- User uploads a document.
- App extracts actual details.
- User reviews and corrects fields.
- The app opens a controlled local browser profile and fills safe fields.
- User manually completes CAPTCHA, login, OTP, payment, location, appointment, and final submit.

## First Public Offer

Start with a small assisted beta, not full self-serve public release.

Recommended first offer:

- NPR 299 per successful form assist.
- NPR 499 for passport/pre-enrollment support.
- NPR 999 monthly plan for cyber/cafe operators or form-filling agents with fair usage.

To reach NPR 10,000/month:

- 34 users/month at NPR 299, or
- 21 users/month at NPR 499, or
- 10 operator users/month at NPR 999.

## MVP Launch Scope

Launch only the flows that are already strongest:

1. Passport/e-passport pre-enrollment support.
2. Driving license support.
3. Voter registration support.
4. College/admission form support.
5. Government job form support.

Keep bank account forms for later because each bank has different risk, KYC rules, and manual verification.

## What Must Be True Before Charging Users

- Public app URL works without using `127.0.0.1`.
- Backend is deployed with a real Gemini API key.
- The browser autofill runner works on the user's own computer.
- Privacy policy and terms are published.
- Users clearly understand that final submission is their responsibility.
- Every upload is processed in memory or deleted quickly.
- Support channel exists: WhatsApp, email, or phone.
- You have tested each supported portal with at least 5 real sample cases.

## Launch Phases

### Phase 1: Private Beta

Target: 5 to 10 trusted users.

- Use free hosting where possible.
- Run the local app/backend on each tester's PC.
- Collect screenshots of field failures.
- Fix field maps.
- Charge lightly or free in exchange for feedback.

### Phase 2: Paid Assisted Beta

Target: first NPR 10,000/month.

- Keep user volume small.
- Use manual support for failures.
- Charge per successful form assist.
- Track each form type, success rate, and support time.

### Phase 3: Public Self-Serve

Target: public website + installable local runner/desktop package.

- Package the local browser automation runner.
- Add account login and usage quota.
- Add payment collection.
- Add dashboard for remaining credits.
- Add production analytics and error reporting.

## Main Risks

- Government portals can change field names and layouts.
- CAPTCHA/login/OTP cannot be automated.
- Some portals may block automation-like behavior.
- Users may upload sensitive ID data, so privacy handling must be strict.
- A remote website alone cannot control a user's browser. For no-extension portal autofill, each user needs the local runner installed/running on their PC.

## Success Metrics

- Extraction accuracy: 90 percent or higher after user review.
- Portal fill success: 80 percent or higher on supported portals.
- Average time saved: at least 10 minutes per form.
- Support time: less than 5 minutes per user after beta fixes.
- Monthly revenue: NPR 10,000 by first 30 to 60 paying users.
