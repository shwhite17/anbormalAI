# Abnormal File Vault (backend)

Django + DRF file hosting API. Dockerised.

## Run

```bash
docker compose up --build        # http://localhost:8000/api/
# or locally
pip install -r requirements.txt
python manage.py migrate && python manage.py runserver
```

## Test

```bash
python manage.py test
```

## API

Every request needs a `UserId` header (stand-in for real auth).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/files/` | Upload (multipart, field `file`). Response includes `deduplicated`. |
| GET | `/api/files/` | List the caller's files |
| GET | `/api/files/<id>/` | File metadata |
| GET | `/api/files/<id>/download/` | Download original bytes |
| DELETE | `/api/files/<id>/` | Delete |

```bash
curl -H "UserId: alice" -F "file=@notes.txt" localhost:8000/api/files/
```

## Design: deduplication

- `Blob` = one physical copy, keyed by a unique SHA-256 and a `ref_count`.
- `UserFile` = a user's logical file (name, type, owner) pointing to a `Blob`.
- Upload hashes the stream in chunks. If the hash exists (any user), no new bytes are stored; `ref_count` is incremented.
- Delete decrements `ref_count`; the physical file is removed only at zero.
- Hash, create and counter updates run in a transaction; `ref_count` uses `F()` expressions to avoid lost updates.

## Roadmap

1. [done] Core upload/list/download/delete + deduplication
2. Search & filtering (filename, type, size range, date) with DB indexes
3. Per-user rate limiting and storage quota
