# Final Anonymity Audit

Audit date: 2026-07-16. Scope: every file under `paper_build/overleaf/`, including the consolidated TeX driver, BibTeX, inline TikZ, Python, JSON figure data, PDFs, comments, filenames, and README text.

## Submission identity

- `main.tex` uses only `\author{\IEEEauthorblockN{Anonymous Authors}}`.
- No affiliation block, email address, acknowledgment, grant, funding statement, repository owner, author contribution statement, or identifying footnote is present.
- The working title contains no author or institutional identifier.
- The package contains no acknowledgment section.

## Text and path scan

Recursive text/binary-string searches covered:

- local absolute paths (`/Users/`, `/home/`, Windows drive paths, `file://`, `vscode://`);
- the local username and known name fragments;
- email-address patterns;
- affiliation, institution, acknowledgment, grant, and funding terms;
- repository-owner and personal GitHub URL patterns;
- hard-coded paths back to `paper_build` or the local source artifact directory.

Results: **no identifying match** and **no local absolute path** was found. All TeX inputs, graphic paths, and figure-script data paths are package-relative.

The URLs in `references.bib` are legitimate official EIP, arXiv, DOI, and venue records for third-party literature. They do not identify the submission authors. Legitimate cited-author names were retained as required for scholarly attribution.

## File-by-file class review

| File class | Count | Checks | Result |
|---|---:|---|---|
| Consolidated `main.tex` | 1 | Author block, section/table/TikZ content, comments, paths, affiliations, acknowledgments, URLs, custom metadata | Anonymous |
| BibTeX | 1 | Submission-author leakage, personal/repository URLs, non-source metadata | Only third-party publication metadata |
| Python figure scripts | 3 | Docstrings, comments, path construction, PDF metadata fields | Package-relative paths; `Author`/`Creator` explicitly anonymous |
| Figure-data JSON | 4 | Paths, usernames, author metadata, repository ownership | No identifying fields or paths |
| Vector PDF figures | 3 | Document metadata and extractable strings | Anonymous metadata; no local path or personal string |
| README | 1 | Personal paths, names, contact information, institution | Practical anonymous instructions only |

## PDF metadata

`pdfinfo` reports the following for all three PDFs:

- `Author: Anonymous`;
- `Creator: Anonymous reproducible figure script`;
- `Producer: Matplotlib`;
- descriptive protocol-only title, subject, and keywords;
- no creation or modification date field;
- no custom metadata stream, attachment, JavaScript, or form.

The PDFs contain no author email, institution, home-directory path, repository URL, or username in extractable strings.

## Filename and manifest review

All filenames are descriptive and generic (`main.tex`, section names, result-protocol figure names, table names, and task-aligned figure-data names). No filename contains a person, institution, username, project owner, or local machine name. The upload manifest records only package-relative paths, sizes, hashes, and roles.

## Remaining submission action

After Overleaf produces the review PDF, inspect the final PDF properties again because the compilation platform can add producer or timestamp metadata. This is a submission-stage check, not a detected anonymity defect in the package.

**Anonymity result: PASS for the uploaded source package.**
