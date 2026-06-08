# Passport Local Autofill Notes

## Current Goal

This build is intentionally passport-only. The local app should turn a packet of passport source documents into a reviewed applicant profile, then open the Nepal ePassport portal in a local Chromium browser profile and fill safe visible fields.

## Review Contract

- Only extracted fields at or above the confidence cutoff are auto-filled into the review form.
- Lower-confidence fields stay blank on purpose so the user can inspect and enter them manually.
- The UI surfaces `field_confidence` and `validation_warnings` when Gemini provides them, so review-required states are visible before any portal work starts.
- If the reviewer edits a field in the form, the portal payload treats that value as manually confirmed instead of keeping the original low-confidence source metadata.
- The portal flow is page-local only: the user manually moves through pages, completes login/CAPTCHA/OTP, and handles appointment booking, payment, and final submit.
- Current cutoff in the React client is 95 percent, matching the safe-fill behavior used elsewhere in the portal automation path.

## Extraction Mechanism

- Frontend sends repeated `files` form-data entries to `POST /api/extract` with `form_type=passport`.
- Backend requires `GEMINI_API_KEY` unless explicit demo mode is enabled.
- Backend defaults to `GEMINI_MODEL=gemini-3.5-flash`.
- Gemini receives all uploaded image/PDF inputs as one packet and returns one normalized applicant profile.
- The API returns normalized field values only; raw extracted document text is not returned to the browser.
- Google Vision OCR is not part of the intended path.

## Limits And Secret Handling

- `GEMINI_REQUESTS_PER_MINUTE` is clamped between 1 and 60; invalid values fall back to 15.
- A packet can contain at most 6 files.
- Each file can be at most 12 MB.
- The combined packet can be at most 32 MB.
- Gemini provider errors are converted to short local messages before being returned to the browser.
- API keys must stay in ignored local env files or process environment and must never be committed.

## Portal Mechanism

- `POST /api/portal/autofill` starts `scripts/portal-fill.js`.
- The script uses Playwright with a persistent local Chrome/Edge/Brave profile.
- Browser discovery checks the common macOS app bundle paths as well as the Windows install locations, so local Chrome/Edge/Brave installs are found on this machine class too.
- The user handles login, CAPTCHA, OTP, payment, appointment booking, page navigation, and final submit manually.
- The script may fill text inputs, selects, radio buttons, checkboxes/tick questions, and date widgets when labels match reviewed applicant values.
- The script intentionally skips fields below the confidence threshold instead of guessing.
- Gender, application type, passport type, DOB, issued date, and expiry date should be treated as first-class portal-fill cases.
- `portal-fill-report.json` now carries per-field `field_events` plus before/after snapshots for fills and skips so reviewers can see the stimulus, the matched control, and the resulting state without replaying the browser session.

## Safety Boundary

Never automate:

- password or login submission
- CAPTCHA or OTP
- payment details
- appointment booking or slot selection
- page-to-page navigation
- final application submit
- government identity verification challenges

The automation should fill and pause for review.
