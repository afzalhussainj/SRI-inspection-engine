# Structured Wellbeing Risk Inspection Program  
## Admin Guide / Handoff Guide  

**Date:** April 23, 2026  
**Subtitle:** Operational guide for non-technical administrators

---

# 1. Title Page

**Product Name:** SRI Inspection Engine / Structured Wellbeing Risk Inspection Program  
**Document Type:** Admin Guide / Handoff Guide  
**Audience:** Non-technical hospital/program administrators  
**Purpose:** Day-to-day operations, safe configuration management, and report review

---

# 2. Purpose of This Guide

This guide explains how to operate the Structured Wellbeing Risk Inspection system without needing developer support for normal tasks.

It is written for non-technical operators who need to:
- manage branding (program name, logo, color, tagline, footer)
- manage inspection instances and campaign workflows
- manage questionnaire/configuration versions safely
- create and test recipient links
- review submissions and parent-facing PDF reports
- verify English and Spanish behavior

This guide focuses on practical, safe operation of the current implemented system.

---

# 3. System Overview

The SRI Inspection Engine is a structured questionnaire system used to collect caregiving workflow information and generate a parent-facing structural report.

In simple terms:
- A participant opens a recipient link and completes a questionnaire.
- The system evaluates responses using preconfigured deterministic rules.
- The system produces a parent-facing report in the selected output language (English or Spanish).

Important:
- The report is **informational and structural**.
- It is **not diagnostic** and does not provide medical advice.
- The system supports hospital/program branding so the form and report match your organization identity.

**Default public branding (no organization id, or no branding row yet):** the respondent form and parent-facing PDF use the program name **SRI Program** and the footer line **Structured Risk Inspection Technology**. Creating an **Organization Branding** record for your `organization_id` overrides the program name, tagline, logo, colors, and footer text as you configure them.

**Internal vs public credit:** Repository and operating-rule documents may name the software owner for internal accountability. That ownership context is **not** shown to respondents as a public footer or vendor line; public fallback credit is **Structured Risk Inspection Technology** only (unless your organization branding supplies its own footer).

**Already-submitted links:** If someone reopens a link after a submission, the public form shows a **confirmation-style** message (“Submission received”) rather than a disabled-error pattern. NRB links that allow public PDF download still show the download action when applicable; QuietRisk (organization-linked) campaigns do **not** expose a public PDF button—summaries are distributed per program policy.

**Reference details:** Inspection and link identifiers, and the pinned form version id, appear only in a small **Reference details** disclosure at the bottom of the respondent page (for support), not as prominent headings.

**Reports (PDF):** Classification tiers are shown in **standard title-style wording** for readers; stored evaluation values remain the canonical `Cleared` / `Watch` / `Elevated` strings. Selected structural considerations list **the consideration text only**—mechanical “Question 1 / Question 2” prefixes are not used in reader-facing PDF sections.

---

# 4. Admin Areas You Will Use

The main admin areas you will use are:

1. **Organization Branding**
   - Set program name, logo, primary color, tagline, and footer text.

2. **Inspection Instances**
   - Manage templates/campaigns and run campaign-level aggregation updates.

3. **Inspection Config Versions**
   - Manage draft vs published configurations.
   - Validate, clone drafts, publish, and create recipient links.

4. **Recipient Links**
   - Review/share public links and create one-click test submissions.

5. **Submissions**
   - Review individual submissions and download parent-facing PDF reports.

6. **Aggregated Reports**
   - Download campaign-level aggregated PDF outputs.


---

# 5. Safe vs Unsafe Edits

This is the most important section for operational safety.

## Safe (normal operator tasks)
- Updating branding:
  - hospital/program name
  - logo
  - primary color
  - tagline
  - footer text
- Reviewing reports and checking language/branding quality
- Creating recipient links from **published** config versions
- Running test submissions
- Cloning existing versions/instances for safe edits

## Caution (allowed, but be deliberate)
- Editing questionnaire wording in a **draft** config
- Editing language text (English/Spanish phrasing)
- Publishing a new config version
- Creating new campaign instances from templates

## Unsafe / needs extra care
- Editing evaluation/rule logic in config JSON
- Changing scoring-related thresholds
- Renaming/removing internal IDs or option values used by rules
- Editing advanced structure without validation and review

## Golden safety rules
1. **Do not edit published versions.**  
2. **Clone as new draft first.**  
3. **Validate before publish.**  
4. **Test with a recipient link before live use.**  
5. If unsure, escalate to technical support before publishing.

---

# 6. Managing Branding

Branding is managed in **Organization Branding**.

You can update:
- Organization ID linkage
- Hospital/program display name
- Logo file
- Primary color
- Tagline
- Footer text

## Step-by-step
1. Open **Organization Branding** in admin.
2. Select the branding record for your organization.
3. Update desired fields.
4. Save changes.
5. Open a recipient link and a generated report to confirm updates are visible.

## Adding a new organization and linking it correctly

Use this flow when onboarding a new hospital/program.

### A) Create the organization branding record
1. Go to **Admin > Organization Branding**.
2. Click **Add Organization Branding**.
3. Enter:
   - **Organization ID** (this must be unique and exact)
   - hospital/program name
   - logo, color, tagline, and footer (optional but recommended)
4. Save.

### B) Link the organization to an inspection instance
1. Go to **Admin > Inspection Instances**.
2. Open the template/campaign instance you want to brand.
3. In the instance, set **Organization ID** to exactly match the Organization Branding record.
4. Save.

### C) Verify the link is active
1. Open a recipient link for that instance.
2. Confirm public form header branding is correct.
3. Submit a test and confirm parent PDF branding is correct.

### Important linking rule
- Branding is applied by matching **Inspection Instance Organization ID** to **Organization Branding Organization ID**.
- If they do not match exactly, fallback branding is shown.

## How branding is applied
- Branding appears in the public form header.
- Branding is used in generated parent-facing PDFs.
- If no organization-specific branding exists, the system uses fallback presentation values (**SRI Program** and **Structured Risk Inspection Technology** for program name and footer line on the public form and in PDF when no org footer is set).





---

# 7. Managing Questionnaire / Configuration Versions

## What a config version is
A config version is the questionnaire and rule package used for submissions at that point in time.

## Draft vs Published
- **Draft**: editable
- **Published**: locked/immutable in admin workflow and used for live recipient links

## Safe workflow
1. In **Inspection Config Versions**, select a known-good version.
2. Use **Clone selected version(s) as new draft**.
3. Open draft and make only intended edits.
4. Use **Validate selected config versions**.
5. Use **Publish selected config versions** when ready.
6. Create recipient links from published version and test.

## Why this matters
This workflow prevents accidental changes to live behavior and creates a clear audit trail.



---

# 8. Managing Inspections / Campaigns / Public Links

## Inspection Instances
Use this area to manage templates/campaigns and related inlines for versions/links.

Available bulk actions include:
- **Clone selected as new template(s)**
- **Create campaign(s) from selected template(s)**
- **Generate aggregated PDF now (campaigns only)**

## Recipient Links
Create recipient links from published config versions.

Important:
- Links are tied to a specific inspection instance and published version.
- A link can be opened and submitted once per recipient link token.

## Safe form testing
- Use **Create test submission(s) (lowest-signal answers)** in Recipient Links for a quick admin-side test submission.




---

# 9. English and Spanish Operation

The current implementation supports both English and Spanish in the participant flow and parent-facing reports.

## How language selection works
- **Form language** controls questionnaire text display.
- **Output language** controls generated report language.

## Operator checks for language quality
When testing both languages, verify:
- headings are in the selected language
- domain names are in the selected language
- classification and confidence labels match selected language
- no mixed-language fallback text appears
- no placeholder/demo text appears

## Quick language test checklist
- [ ] Open link in English mode and submit
- [ ] Review English report wording consistency
- [ ] Open link in Spanish mode and submit
- [ ] Review Spanish report wording consistency
- [ ] Confirm no mixed-language fragments




---

# 10. Running and Reviewing Reports

## Generate a test report (quick path)
1. Open **Recipient Links**.
2. Select a link and run **Create test submission(s) (lowest-signal answers)**.
3. Open **Submissions**.
4. Click **Download** in the Submission PDF column.

## Review checklist for each PDF
Check:
- branding (name/logo/color/footer)
- language is correct
- report metadata present
- sections render correctly (overview, domains, strengths, methodology, scope)
- no placeholder/demo text

## Aggregated reports
For campaign-level summary:
1. Run **Generate aggregated PDF now (campaigns only)** from Inspection Instances.
2. Open **Aggregated Reports**.
3. Click **Download** in Aggregated PDF column.





---

# 11. What to Check Before Sharing With a Hospital / Program

Use this release checklist before sending forms/reports to stakeholders:

- [ ] Correct branding record is applied (name/logo/color/tagline/footer)
- [ ] Correct inspection/campaign selected
- [ ] Correct config version is **Published**
- [ ] Recipient link opens successfully
- [ ] Form language and output language behave correctly
- [ ] English report has no Spanish leakage
- [ ] Spanish report has no English leakage (except formal standard name if intentionally preserved)
- [ ] No placeholder/demo text appears anywhere
- [ ] Parent report downloads successfully
- [ ] If needed, aggregated campaign report downloads successfully

---

# 12. Troubleshooting Basics

## Logo not showing
**Likely cause:** Missing/invalid logo in branding record.  
**Check first:** Organization Branding record has logo uploaded and saved.  
**Escalate when:** Logo file uploads but still never appears.

## Wrong language showing
**Likely cause:** Form language/output language not set as expected during test.  
**Check first:** Re-open link and verify both language selectors before submitting.  
**Escalate when:** PDF language does not match selected output language.

## Report still contains old wording
**Likely cause:** Submission used an older published config version.  
**Check first:** Confirm which config version was used; publish new version if intended.  
**Escalate when:** New submissions still show old text after correct version publish.

## Form not loading
**Likely cause:** Link expired, invalid, or mismatch.  
**Check first:** Open link from Recipient Links list; confirm status/expiry.  
**Escalate when:** Multiple fresh links fail to load.

## Report not appearing
**Likely cause:** No submission exists for that link yet.  
**Check first:** Verify submission row exists in Submissions admin.  
**Escalate when:** Submission exists but PDF download fails.

## Branding not applied
**Likely cause:** Organization ID/branding record mismatch.  
**Check first:** Organization ID on instance aligns with Organization Branding entry.  
**Escalate when:** IDs match but branding still never appears.

## Wrong config/version appears live
**Likely cause:** Link created from unintended published version.  
**Check first:** Confirm link’s pinned config version; create new link from correct published version.  
**Escalate when:** Link behavior does not match its shown config version.

---

# 13. Recommended Test Flow for Non-Technical Review

Use this mini script for final operational sign-off:

1. Open a test recipient link from admin.
2. Set **Form language = English**, **Output language = English**.
3. Submit and download parent report from Submissions.
4. Confirm English text consistency and branding.
5. Open a fresh test link (or equivalent test path).
6. Set **Form language = Spanish**, **Output language = Spanish**.
7. Submit and download parent report.
8. Confirm Spanish text consistency and branding.
9. Confirm footer/metadata appear correctly.
10. Confirm no placeholder/demo text appears in either language.

---

# 14. Appendix: Screenshot Checklist

Use this checklist to capture all screenshots needed for final document packaging.

1. **Main Admin Sections**  
   - Section: 4 (Admin Areas You Will Use)  
   - Navigate: Admin home page

2. **Organization Branding Edit Screen**  
   - Section: 6 (Managing Branding)  
   - Navigate: Admin > Organization Branding > open record

3. **Branding Reflected on Public Form**  
   - Section: 6 (Managing Branding)  
   - Navigate: Public recipient link page

4. **Config Version List (Draft vs Published)**  
   - Section: 7 (Managing Questionnaire / Configuration Versions)  
   - Navigate: Admin > Inspection Config Versions

5. **Config Version Detail and Actions**  
   - Section: 7  
   - Navigate: Admin > Inspection Config Versions > open version

6. **Inspection Instances List and Bulk Actions**  
   - Section: 8  
   - Navigate: Admin > Inspection Instances

7. **Recipient Links List and Public URL**  
   - Section: 8  
   - Navigate: Admin > Recipient Links

8. **Public Form Screen (Participant View)**  
   - Section: 8  
   - Navigate: Open recipient link

9. **Language Selectors on Public Form**  
   - Section: 9  
   - Navigate: Public form

10. **English Report Example**  
    - Section: 9  
    - Navigate: Admin > Submissions > Download English PDF

11. **Spanish Report Example**  
    - Section: 9  
    - Navigate: Admin > Submissions > Download Spanish PDF

12. **Submissions List with PDF Download Link**  
    - Section: 10  
    - Navigate: Admin > Submissions

13. **Parent Report First Page Review**  
    - Section: 10  
    - Navigate: Downloaded parent PDF page 1

14. **Parent Report Domain Detail Page**  
    - Section: 10  
    - Navigate: Downloaded parent PDF domain detail section

15. **Footer and Branding in PDF**  
    - Section: 10  
    - Navigate: Downloaded parent PDF footer area

16. **Add New Organization Branding Record**  
    - Section: 6  
    - Navigate: Admin > Organization Branding > Add Organization Branding

17. **Link Organization ID to Inspection Instance**  
    - Section: 6  
    - Navigate: Admin > Inspection Instances > open instance (Organization ID field)

---

## Final Note

For routine operation, stay inside draft/validate/publish workflows and test each change before sharing externally.  
When in doubt about rule logic or JSON structure changes, pause and request technical review before publishing.

