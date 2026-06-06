# Nepal Form Autofill

## Funding Presentation Brief

**Concept:** AI-assisted document extraction and safe browser autofill for Nepali public-service portals.

**Stage:** Working local prototype with deployable beta plan.

**Target users:** Nepali citizens applying for passports, driving licenses, voter registration, college/admission forms, and government jobs.

**Funding goal:** Deploy the product online, add secure user accounts, build a browser extension for portal autofill, and run a controlled beta with 7-9 users.

---

## 1. Executive Summary

Nepal Form Autofill is a digital assistant that helps users complete repetitive government and institutional forms. Users upload an ID document such as Nagarikta, NID, scanned image, or PDF. The system extracts structured identity data, lets the user review and correct it, then helps generate PDF forms or safely autofill visible fields inside official browser portals.

The product is designed for real Nepali workflows where users often need to fill the same personal details across multiple portals. It does not bypass login, CAPTCHA, OTP, payment, or final submit. Instead, it keeps the user in control while reducing repetitive typing and data-entry errors.

---

## 2. Problem

Many Nepali public-service workflows require users to repeatedly enter the same identity data:

- Full name in English and Nepali
- Date of birth
- Gender
- Citizenship or NID number
- District, municipality, ward
- Father, mother, and family details
- Contact information
- Application reference numbers

This process is difficult because:

- Forms are spread across different portals.
- Many users work from phone photos, PDF receipts, SMS, or email references.
- Portals may have login, CAPTCHA, OTP, and multi-page forms.
- A single mistake can delay applications.
- Users often do not know which official portal link to use.

---

## 3. Solution

Nepal Form Autofill acts as a guided application assistant.

The system:

1. Extracts user data from ID documents.
2. Shows the extracted data for review.
3. Highlights which fields were auto-filled and which need manual input.
4. Generates downloadable/printable PDFs.
5. Provides official portal links for common Nepal services.
6. Uses a browser companion to autofill safe visible fields inside official portals.
7. Watches multi-page portals and fills safe fields as the user moves across pages.

The product is not a bypass tool. It is a user-controlled assistant.

---

## 4. Key Features After Deployment

1. **AI document extraction**  
   Reads Nepali ID documents, NID, scanned images, and PDFs using Gemini document extraction.

2. **Multiple form types**  
   Supports passport, driving license, voter registration, government job, college admission, and later bank forms.

3. **Structured user profile**  
   Converts extracted data into reusable profile fields.

4. **Review-before-use workflow**  
   User can edit every field before generating a PDF or filling a portal.

5. **Auto-filled/manual field indicators**  
   Green fields show extracted data; manual fields remain visible for review.

6. **PDF generation**  
   Creates filled PDF forms for download or printing.

7. **e-Passport workflow support**  
   Includes Online Pre-Enrollment Form, Passport Status Check, and Application ID/reference-number guidance.

8. **Official portal directory**  
   Provides portal suggestions for passport, driving license, voter registration, government jobs, and admission forms.

9. **Browser portal autofill**  
   Opens a connected browser profile and fills visible safe fields in official portals.

10. **Multi-page portal watcher**  
    Watches for up to 20 minutes and fills safe fields as page 1, page 2, page 3, etc. appear.

11. **Security boundaries**  
    Does not fill passwords, CAPTCHA, OTP, payment, PIN, CVV, or final submit buttons.

12. **Persistent browser profile**  
    Keeps portal login sessions available for repeated use.

13. **OCR usage limits**  
    Can limit scans per user to control API cost.

14. **Sample/demo mode**  
    Allows product demos without uploading a real ID.

15. **Future Chrome extension**  
    Required for public users so autofill can run inside their own logged-in browser sessions.

---

## 5. Product Flow

1. User selects a form type.
2. User uploads ID photo, NID, Nagarikta, scanned PDF, or searchable PDF.
3. Backend extracts structured data.
4. User reviews and edits fields.
5. User downloads a PDF or chooses a portal.
6. If portal is used, user manually completes login/CAPTCHA/OTP.
7. Browser autofill watches safe visible fields across pages.
8. User reviews each page and submits manually.

---

## 6. Deployment Architecture

| Layer | Recommended beta setup | Purpose |
|---|---|---|
| Frontend | Vercel free/Hobby | Public web app and review UI |
| Backend | Render free/low-cost FastAPI service | OCR, PDF generation, rate limits |
| Database/Auth | Supabase free tier | User login, profile fields, usage counters |
| AI OCR | Google AI Studio Gemini API | Document extraction |
| Portal autofill | Chrome extension/browser companion | Autofill inside user's own browser |
| Monitoring | Hosting logs first; Sentry later | Error and usage tracking |

---

## 7. Why Browser Extension Is Needed

A normal hosted website cannot directly control another website after a user logs in. Browser security prevents that.

For public users, portal autofill must run in the user's browser through:

- Chrome extension, or
- local browser companion

This is necessary because login cookies, CAPTCHA, OTP, and portal sessions live inside the user's browser.

Correct product architecture:

```text
User Browser
  |
  |-- Web App on Vercel
  |
  |-- Chrome Extension for portal autofill
  |
Backend API on Render
  |
Supabase Database
  |
Gemini API
```

---

## 8. Estimated Beta Cost

For 7-9 users, the product can run close to free if usage is controlled.

| Item | Free beta estimate | Paid/production expectation | Notes |
|---|---:|---:|---|
| Frontend hosting | $0 | Vercel Pro about $20/month if needed | Free is enough for early testing |
| Backend hosting | $0 to low cost | About $7-$25/month starter range | Free services may sleep |
| Database/auth | $0 | Supabase Pro from $25/month | Free tier is enough for small beta |
| Gemini OCR | $0 within free quota | Usage-based when billing enabled | Main cost risk |
| File storage | $0 if not storing files | $5-$25/month if needed | Do not store raw IDs in beta |
| Domain | Optional | $10-$20/year typical | Use free subdomain first |
| Chrome Web Store | Manual install for private beta | One-time developer registration fee | Needed for public extension |
| Legal/privacy | Founder-written draft | $100-$500+ if reviewed | Important for ID data |

---

## 9. Cost-Control Plan

For beta:

- Keep Gemini billing off or use a hard billing cap.
- Limit OCR to 1-2 scans per user per day.
- Do not store raw ID images or PDFs.
- Store only reviewed profile fields.
- Reject very large files.
- Use free Vercel/Render/Supabase tiers.
- Keep portal autofill browser-side so it does not add server cost.

Recommended beta limits:

```text
Users: 7-9
OCR scans: 1 per user per day
PDF downloads: unlimited
Portal autofill: unlimited browser-side
Raw ID storage: none
Profile fields: stored only after user consent
```

---

## 10. Safety and Compliance Position

Nepal Form Autofill should be presented as a review-first assistant.

It must not:

- bypass CAPTCHA
- bypass OTP
- fill login passwords
- fill payment/card/CVV/PIN fields
- click final submit
- submit applications without user review

It should:

- require user consent before OCR
- show extracted data before use
- let users delete saved data
- avoid storing raw documents by default
- keep audit logs for user actions

---

## 11. Funding Use

Funding or incubation support would be used for:

1. Production deployment
2. Secure user login
3. Supabase database setup
4. Chrome extension development
5. Portal field mapping for priority Nepal portals
6. Privacy/security hardening
7. Usage limits and monitoring
8. Legal/privacy documentation
9. Beta testing with 7-9 real users
10. Preparing a public launch

---

## 12. Beta Milestones

| Timeline | Goal |
|---|---|
| Week 1 | Deploy frontend/backend and configure Gemini |
| Week 2 | Add user login, profile saving, and OCR limits |
| Week 3 | Build private Chrome extension/browser companion |
| Week 4 | Test passport and driving license flows |
| Week 5 | Add voter registration and PSC flows |
| Week 6 | Run 7-9 user beta and collect metrics |

---

## 13. Success Metrics

The beta should measure:

- extraction accuracy
- time saved per application
- number of fields filled automatically
- number of fields corrected by user
- portal pages successfully assisted
- OCR cost per successful application
- failed portal mappings
- user satisfaction

---

## 14. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Portals change layouts | Maintain portal-specific field maps |
| Gemini quota runs out | Add OCR limits and billing cap |
| Sensitive ID data risk | Do not store raw documents; encrypt stored profile fields |
| User expects full automation | Clearly explain manual login/CAPTCHA/submit boundaries |
| Website cannot fill logged-in portals alone | Use Chrome extension/browser companion |
| Free hosting sleeps | Accept for beta; upgrade if users grow |

---

## 15. Investor / Company Ask

We are seeking support to turn a working prototype into a controlled public beta.

The first goal is not national-scale deployment. The first goal is to prove:

- users save time
- ID extraction is accurate enough
- portal autofill works safely across multi-page forms
- users trust the review-first workflow
- operating cost is manageable

The proposed beta cohort is 7-9 users across passport, driving license, voter registration, government job, and admission workflows.

---

## 16. Source References

- Vercel Hobby Plan: https://vercel.com/docs/accounts/plans/hobby
- Vercel Pricing: https://vercel.com/pricing
- Render Free Services: https://render.com/free
- Supabase Pricing: https://supabase.com/pricing
- Gemini API Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Chrome Web Store Registration: https://developer.chrome.google.cn/docs/webstore/register

