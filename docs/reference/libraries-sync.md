# Libraries-sync reference

> [!WARNING]
> Deze pagina is door AI gegenereerd en nog niet door een mens gereviewd.

Exacte details van `scripts/sync_libraries.py` (sync van `knowledge-documents/` naar Mistral-libraries). Gedrag geverifieerd tegen de code; zie ook [GLOSSARY.md](../../GLOSSARY.md) en [ADR-0005](../adr/0005-library-bevat-alleen-actuele-versies.md).

## Commando

```bash
python scripts/sync_libraries.py [--apply] [--library NAAM] [--config PAD]
```

| Flag | Default | Betekenis |
| --- | --- | --- |
| `--apply` | uit (dry-run) | Voert create/upload/delete echt uit; zonder deze flag is de run read-only |
| `--library NAAM` | alle geconfigureerde libraries | Synct alleen deze library; unbekende naam → exit-code 2 |
| `--config PAD` | `scripts/libraries_config.json` | Alternatief configbestand |

## Environment variables

| Variabele | Verplicht | Bron |
| --- | --- | --- |
| `MISTRAL_API_KEY` | ja | `.env` in de repo-root |

Python-omgeving: gebruik de project-venv (`.venv`); zonder venv geeft het script een foutmelding met hint.

## Config (`scripts/libraries_config.json`)

| Veld | Type | Betekenis |
| --- | --- | --- |
| `rag_folder` | string | Lokale bronmap; relatieve paden worden omgezet relatief aan het configbestand (nu `../knowledge-documents`), Onafhankelijk van de huidige map |
| `libraries` | array | Eén entry per library |
| `libraries[].name` | string | Librarynaam; moet exact gelijk zijn aan de submapnaam (lowercase) |
| `libraries[].description` | string | Wordt meegegeven bij create en bijgewerkt als deze wijzigt |

## Sync-regels

- Per library worden de lokale bestanden (plat, alle bestandstypen) vergeleken met de remote documenten (alle pagina's opgehaald).
- Identiteit van een document = bestandsnaam + bestandsgrootte. Bij een mismatch worden alle remote documenten met die naam verwijderd en wordt er één nieuwe geüpload (de API dedupliceert niet zelf).
- Remote documenten zonder lokale tegenhanger worden uit de library verwijderd.
- Lege (of ontbrekende) lokale map = lege library: alle remote documenten worden verwijderd.
- Lokale mappen die niet in de config staan: warning, worden overgeslagen.
- Na upload is een document asynchroon in processing (`process_status`); het script wacht hier niet op.
- `versions.json` wordt niet aangeraakt (handmatig beheer, ADR-0005).

## Exit-codes

| Code | Betekenis |
| --- | --- |
| 0 | Succes (dry-run of apply zonder fouten) |
| 1 | Eén of meer fouten tijdens `--apply` (zie summary) |
| 2 | Config- of argumentfout (ontbrekende rag-folder, onbekende `--library`, ongeldige JSON) |

## Workspace-overzicht: `scripts/list_libraries.py`

Read-only listing van de remote inhoud per geconfigureerde library (de web-UI biedt geen workspace-breed overzicht).

```bash
python scripts/list_libraries.py           # tabel op stdout
python scripts/list_libraries.py --json    # JSON (raw bytes, ISO-8601 datums)
```

| Kolom (tabel) | JSON-veld | Betekenis |
| --- | --- | --- |
| `library` | `libraries[].name` | Library = submapnaam uit de config |
| `bestand` | `documents[].name` | Documentnaam |
| `grootte` | `documents[].size` | Tabel: human-readable (MB/KB); JSON: raw bytes |
| `aangemaakt` | `documents[].created_at` | ISO-8601 datetime |
| `status` | `documents[].process_status` | Processing-status (`done`, `in_progress`, `error`, ...) |

- Library die wel in de config staat maar niet remote: `exists: false`, geen documenten.
- Remote libraries die niet in de config staan: warning op stderr; in JSON als `unconfigured_remote` (per library `name`, `nb_documents`, `total_size`).
- De totalenregel telt alleen geconfigureerde libraries; in JSON staat bovendien `totals` (`documents`, `size_bytes`, `libraries_existing`, `libraries_configured`). Groottes van documenten met `size = null` tellen als 0 mee.
- `--config PAD` wijzigt het configbestand (default `scripts/libraries_config.json`).

## Tests

`pytest tests/` — gemockte Mistral-client, geen live API-calls (`test_sync_libraries.py`, `test_list_libraries.py`).
