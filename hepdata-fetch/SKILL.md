---
name: hepdata-fetch
description: Search, inspect, and download public HEPData records using the third-party HEPData-CLI tool. Use when Codex needs to retrieve high-energy physics data from hepdata.net, find records by HEPData/Inspire/arXiv IDs or advanced HEPData queries, list table names, download tables in csv/root/yaml/yoda/yoda1/yoda.h5/json formats, or prepare local HEPData files for analysis.
---

# HEPData Fetch

## Overview

Use this skill to fetch public HEPData metadata and table files through `hepdata-cli`. Prefer the bundled wrapper for repeatable read-only tasks; use the raw CLI when a task needs an option the wrapper does not expose.

## Workflow

1. Clarify the identifier or search strategy.

   - Use `ids=hepdata` for HEPData record IDs.
   - Use `ids=inspire` for Inspire record IDs.
   - Use `ids=arxiv` for arXiv IDs.
   - Use a HEPData advanced search query when the user describes a physics process, collaboration, observable, title phrase, reaction, or year.

2. Check that `hepdata-cli` is installed before fetching:

   ```bash
   python3 scripts/hepdata_get.py check
   ```

   If it is missing, ask for approval before installing because installation requires network access:

   ```bash
   python3 -m pip install --user hepdata-cli
   ```

3. Search first when the user has not provided exact record IDs:

   ```bash
   python3 scripts/hepdata_get.py find 'reactions:"P P --> LQ LQ"' --ids hepdata
   ```

4. Inspect table names before downloading a subset:

   ```bash
   python3 scripts/hepdata_get.py names 123456 --ids hepdata
   ```

5. Download records or specific tables to a task-specific output directory:

   ```bash
   python3 scripts/hepdata_get.py download 123456 --ids hepdata --format csv --download-dir hepdata-downloads
   python3 scripts/hepdata_get.py download 123456 --ids hepdata --format yaml --table-name 'Table 1' --download-dir hepdata-downloads
   ```

6. For a one-step search and download, require an ID type so the search output can feed the download:

   ```bash
   python3 scripts/hepdata_get.py search-download 'reactions:"P P --> LQ LQ"' --ids inspire --format csv --download-dir hepdata-downloads
   ```

7. Summarize what was downloaded: record IDs, format, table filter, output directory, and any files created. Do not claim physics interpretation beyond the downloaded data unless the user asks for analysis.

## Output Choices

- Prefer `csv` for quick numeric inspection and plotting.
- Prefer `yaml` when preserving HEPData submission structure and metadata matters.
- Prefer `json` for programmatic metadata/table extraction without unpacked archives.
- Use `root`, `yoda`, `yoda1`, or `yoda.h5` only when the downstream analysis explicitly expects those formats.

## Resources

- `scripts/hepdata_get.py`: read-only wrapper around `hepdata-cli` for check, find, fetch table names, download, and search-then-download workflows.
- `references/cli-reference.md`: concise HEPData-CLI command reference, supported ID types, supported formats, examples, and safety notes.

Read the reference when using raw `hepdata-cli`, troubleshooting output parsing, or handling formats and IDs not obvious from the user request.

## Operational Notes

- HEPData fetching requires internet access to `www.hepdata.net`; if a command fails with a sandbox or network error, request approval to rerun with network access.
- Keep downloads inside the current workspace unless the user asks for another location.
- Do not fabricate record IDs or downloaded values. If search returns nothing, report the exact query and ask for a broader query or different ID type.
- Avoid upload workflows unless the user explicitly asks to submit data to HEPData. Uploads may require account email, password prompts, invitation cookies, and sandbox/production choices.
