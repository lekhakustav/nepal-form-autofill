# Passport Local Autofill Notes

## Current Goal

This build is intentionally passport-only. The local app should turn a packet of passport source documents into a reviewed applicant profile, then open the Nepal ePassport portal in a local Chromium browser profile and fill safe visible fields.

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
- The user handles login, CAPTCHA, OTP, payment, and final submit manually.
- The script may fill text inputs, selects, radio buttons, checkboxes/tick questions, and date widgets when labels match reviewed applicant values.
- Gender, application type, passport type, DOB, issued date, and expiry date should be treated as first-class portal-fill cases.

## Safety Boundary

Never automate:

- password or login submission
- CAPTCHA or OTP
- payment details
- final application submit
- government identity verification challenges

The automation should fill and pause for review.
