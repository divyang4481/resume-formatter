# build locally

```
docker compose up --build -d

```

# Drop all tables

```
docker compose exec api python scripts/clean_db.py
```

# Recreate all tables

```
docker compose exec api python scripts/init_db.py
```
