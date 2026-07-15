# Anonymous-Review Precheck

Check date: 2026-07-15.

## Changes made

- Removed the personal contact email from the HTTP user-agent strings in all five first-party independent-set network scripts.
- Replaced two identifying local absolute paths in `phase0_report.md` with `<WORKSPACE>`.
- Removed first-party Python bytecode caches whose compiled `co_filename` metadata embedded the local absolute workspace path.

## First-party text scan

Scopes scanned:

- `paper/`;
- `pipeline/`;
- `reports/`;
- `results/` metadata and Markdown;
- `paper_build/`;
- root-level first-party scripts and Markdown.

Patterns checked:

- personal names and known username fragments;
- email addresses;
- university/affiliation terms;
- `/Users/<username>/...` local paths;
- identifying personal GitHub/GitLab repository URLs;
- author, affiliation, and acknowledgment fields.

Post-scrub result: no known personal name, username, email address, university name, local absolute user path, or personal repository URL remains in the scanned first-party text.

## Manuscript issue still requiring drafting-time correction

`paper/authguard7702.tex` contains a placeholder `Anonymous Author(s)` block, “Affiliation withheld,” and `contact@example.com`. These are nonidentifying placeholders, but the submission brief requires no author names, affiliations, or contact block. Remove the entire author block in the eventual manuscript revision rather than substituting another placeholder.

## Figures and metadata

- Existing PNG figures expose a generic `Software` text chunk from the plotting stack; string inspection found no author, email, username, or local path.
- No first-party PDF build exists to inspect for PDF Author/Creator metadata.
- The task-alignment and runtime JSON/CSV outputs use relative artifact names and contain no user identity. Read-only RPC endpoint URLs are infrastructure provenance, not author-identifying repository URLs.

## Third-party material

Third-party paper authors, project names, licenses, and official provenance URLs were not modified. The directories containing the USENIX, PhishingHook, PTXPhish, and scam-source artifacts retain their original authorship and repository references, as required for attribution. They should be excluded or clearly separated from any anonymized first-party artifact bundle rather than rewritten.

## Artifact-release checklist

Before anonymous artifact upload:

1. regenerate figures and inspect PNG/PDF metadata;
2. compile the paper with an empty author block and inspect PDF metadata;
3. exclude `.git`, shell history, editor settings, caches, and OS metadata files;
4. scan the packaged archive again for names, emails, usernames, home-directory paths, and personal repository remotes;
5. retain third-party citations and licenses unchanged;
6. use an anonymous artifact URL not linked to a personal account.
