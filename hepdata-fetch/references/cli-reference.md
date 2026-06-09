# HEPData-CLI Reference

Reference checked against HEPData/hepdata-cli and PyPI on 2026-06-09. The package is `hepdata-cli`; the executable is `hepdata-cli`.

Sources:

- https://github.com/HEPData/hepdata-cli
- https://pypi.org/project/hepdata-cli/

## Install and Check

Install from PyPI:

```bash
python3 -m pip install --user hepdata-cli
hepdata-cli --help
```

The project advertises Python >= 3.7 support. Ask for approval before installing in restricted environments because PyPI access requires network access.

## Read-Only Commands

Search HEPData:

```bash
hepdata-cli [--verbose] find [QUERY] [-kw/--keyword KEYWORD] [-i/--ids IDTYPE]
```

Download records:

```bash
hepdata-cli [--verbose] download [IDS] [-f/--file-format FORMAT] [-i/--ids IDTYPE] [-t/--table-name TABLE-NAME] [-d/--download-dir DOWNLOAD-DIR]
```

Fetch table names:

```bash
hepdata-cli [--verbose] fetch-names [IDS] [-i/--ids IDTYPE]
```

`find` searches public HEPData records and accepts the advanced search syntax used by the HEPData website. `download` downloads records or a named table. `fetch-names` returns the available table names for the supplied records.

## ID Types

Use `-i/--ids` with one of:

- `hepdata`: HEPData record IDs.
- `inspire`: Inspire record IDs.
- `arxiv`: arXiv IDs.

When piping or chaining `find` into `download` or `fetch-names`, pass an explicit ID type to `find` and use the same ID type downstream.

## Formats

Use `-f/--file-format` with one of:

- `csv`
- `root`
- `yaml`
- `yoda`
- `yoda1`
- `yoda.h5`
- `json`

For `csv`, `root`, `yaml`, `yoda`, `yoda1`, and `yoda.h5`, HEPData-CLI downloads and unpacks a `.tar.gz` archive into a directory. For `json`, it downloads a `.json` file.

If `--download-dir` is omitted, HEPData-CLI defaults to `./hepdata-downloads`.

## Examples

Search by reaction and return HEPData IDs:

```bash
hepdata-cli --verbose find 'reactions:"P P --> LQ LQ"' -i hepdata
```

Search by reaction and return a metadata keyword:

```bash
hepdata-cli --verbose find 'reactions:"P P --> LQ LQ"' -kw year
```

Download CSV by Inspire ID:

```bash
hepdata-cli --verbose download 1222326 -i inspire -f csv -d hepdata-downloads
```

Fetch table names by HEPData IDs:

```bash
hepdata-cli fetch-names 123456 234567 -i hepdata
```

Download one table by table name:

```bash
hepdata-cli download 123456 -i hepdata -f yaml -t 'Table 1' -d hepdata-downloads
```

## Python API

HEPData-CLI also exposes:

```python
from hepdata_cli.api import Client

client = Client(verbose=True)
client.find(query, keyword=None, ids=None)
client.download(id_list, file_format="csv", ids="hepdata", table_name=None, download_dir="hepdata-downloads")
client.fetch_names(id_list, ids="hepdata")
```

`client.find()` accepts `format` to choose a return type among `str`, `list`, `set`, or `tuple`; the default is `str`.

## Safety

The package also supports `upload`, but this skill should not use it by default. Uploading can require a HEPData account email, password prompt, invitation cookie, sandbox setting, and record replacement choices. Only enter an upload workflow when the user explicitly asks to upload or replace a HEPData record.
