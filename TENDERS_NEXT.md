# TendersMW — Next Actions

## Priority

1. Finish Playwright scanner integration for AfDB and UNGM/UNDP without bypassing
   verification.
2. Run a dry-run verification sample for every new source before cron integration.
3. Review the current untracked UNGM tender JSON files before any commit or push.
4. Keep PPDA scraper in no-output mode until ppda.mw publishes real tenders again.
5. Create a regular source-backed tender report for Jammi.

## Verification Checklist Before Publishing New Tenders

1. `git status --short --branch --untracked-files=all`
2. Confirm new files are from a scraper, not hand-written content.
3. Run `python3 tools/verify_tender.py --batch src/content/tenders/ --existing-slugs-file <tracked-slugs-file>`.
4. Open a sample of source URLs and confirm title/entity/reference/country manually.
5. Run `npm run build`.
6. Only then commit, push, and submit indexing.

## Do Not

- Do not send any email without explicit "send it" approval.
- Do not create sample/placeholder/seed tenders under any circumstances.
- Do not remove the AI verification gate.
- Do not treat untracked JSON files as verified just because they are already on disk.
- Do not touch the disclaimer page without approval.
