# Pricing and Cost Plan

## Revenue Target

Target: NPR 10,000/month.

Simple paths:

- NPR 299 per form: 34 completed assists/month.
- NPR 499 per passport/e-passport assist: 21 completed assists/month.
- NPR 999 monthly operator plan: 10 operator users/month.

Recommended first pricing:

- Free trial: 1 extraction.
- Pay-per-form: NPR 299.
- Passport/e-passport support: NPR 499.
- Local agent/cyber plan: NPR 999/month.

## Cost Categories

### Browser Autofill

- No Chrome extension is required.
- No Chrome Web Store registration fee is required for the current no-extension workflow.
- The tradeoff is that portal autofill must run on the user's own PC through the local backend/browser runner.

### Hosting

Possible free start:

- Frontend on free/hobby hosting.
- Backend on free/low-cost server until usage grows.
- Vercel currently lists Hobby as "Free forever" and Pro at $20/month plus additional usage.
- Railway currently lists a 30-day free trial with $5 credits, then small paid usage-based plans.
- Official references: https://vercel.com/pricing and https://railway.com/pricing

Expected paid range after real users:

- Frontend: NPR 0 to NPR 2,000/month.
- Backend: NPR 0 to NPR 3,000/month at small scale.
- Domain: usually yearly, not monthly.

### AI Extraction

Gemini API cost depends on:

- model used,
- document size,
- number of extractions,
- input/output token usage.

The app should track usage per user before full launch.

Google's Gemini API pricing page currently says developers can start free, then scale to paid production usage with higher limits. Official reference: https://ai.google.dev/gemini-api/docs/pricing

## First Month Budget

Cheapest beta:

- Hosting: NPR 0 to NPR 1,500.
- Chrome extension: NPR 0 because this workflow does not use one.
- Domain: optional at first.
- Gemini usage: likely low for 5 to 10 testers, but monitor it.

Professional public launch:

- Local runner packaging/installer: optional setup cost later.
- Domain: yearly cost.
- Hosting: likely NPR 1,000 to NPR 5,000/month.
- AI usage: depends on users.

## Break-Even Example

If monthly running cost is NPR 3,000:

- At NPR 299/form, need 11 forms to cover cost.
- To net NPR 10,000 after cost, need about 44 forms/month.

If monthly running cost is NPR 5,000:

- At NPR 499/form, need 11 forms to cover cost.
- To net NPR 10,000 after cost, need about 31 forms/month.

## Best First Customer

The best early customer is not a random one-time user. It is:

- cyber cafe,
- documentation service shop,
- passport/driving-license helper,
- education consultancy,
- local form-filling agent.

They can use the app repeatedly and tell you which portals matter most.
