# Nepal Form Autofill Real User Launch Checklist

## What is ready now

- Local web app prototype.
- Gemini document extraction.
- Reviewed fields and PDF generation.
- Local browser automation for user-side portal autofill.
- No Chrome extension required for the current workflow.

## What is not production-ready yet

- No public user accounts.
- No database-backed per-user quota.
- No production privacy policy/terms screen.
- Portal automation needs real portal-by-portal testing before public release.

## Browser autofill cost

No Chrome extension cost is required for the current workflow.

For portal autofill without an extension, the app must run a local backend/automation runner on the user's own computer. A remote website alone cannot safely control a user's browser.

## Free beta path

1. Host the website/backend using free or low-cost tiers.
2. Run the local app/backend on each beta user's PC.
3. Use `Open & Autofill` from the app after the user reviews extracted fields.
4. Collect portal screenshots and field failures.
5. Fix field maps.
6. Package a simple local runner/installer when ready.

## Production path

1. Deploy frontend.
2. Deploy backend.
3. Add auth.
4. Add database and usage quotas.
5. Add privacy policy and data deletion policy.
6. Finalize portal field maps.
7. Package the local browser runner.
8. Add user onboarding for installing/running the local app.
