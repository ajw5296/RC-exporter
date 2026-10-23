# RC-exporter

Desktop app to download REDCap reports (or a project's full dataset) through the REDCap API.
Built with tkinter + [PyCap](https://github.com/redcap-tools/PyCap); runs on Ubuntu and Windows.

## Use

```
pixi run app
```

1. API URL defaults to Penn State's server (`https://redcap.ctsi.psu.edu/api/`).
2. Enter the project ID and your API token (REDCap → project → API), click **Connect**.
   The app checks that the token belongs to that project ID.
3. Choose a **Report ID** (shown in the "Report ID" column on the project's *Reports* page; the API
   cannot list reports) or **All records**, pick raw codes or labels and CSV or Excel, then **Download…**.

The token is never written to disk. Exports usually contain PHI: save them only to approved storage.

## Build a standalone executable

```
pixi run build      # -> dist/RC-Exporter (Linux) or dist\RC-Exporter.exe (Windows)
```

PyInstaller does not cross-compile: build the Windows `.exe` on Windows (`pixi install`, then `pixi run build`).

## Tests

Live tests read `.env` (gitignored):

```
REDCAP_API_URL=https://redcap.ctsi.psu.edu/api/
REDCAP_PROJECT_ID=...
REDCAP_API_TOKEN=...
REDCAP_REPORT_ID=...   # optional
```

```
pixi run test
```
