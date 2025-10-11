# Postgres Setup Instructions

## Option 1: Docker (Recommended)

The project includes a `docker-compose.yml` file for easy Postgres setup.

### Prerequisites
Install Docker Desktop from: https://www.docker.com/products/docker-desktop

### Start Postgres
```bash
docker compose up -d
```

### Check Status
```bash
docker compose ps
```

### View Logs
```bash
docker compose logs postgres
```

### Stop Postgres
```bash
docker compose down
```

### Stop and Remove Data
```bash
docker compose down -v
```

## Option 2: Local Postgres Installation

### macOS (Homebrew)
```bash
brew install postgresql@15
brew services start postgresql@15
```

### Create Database
```bash
createdb mcp_chat
createuser mcp_user
psql -c "ALTER USER mcp_user WITH PASSWORD 'mcp_pass';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE mcp_chat TO mcp_user;"
```

### Update .env
If using local Postgres, update the DATABASE_URL in `.env`:
```
DATABASE_URL=postgresql+asyncpg://mcp_user:mcp_pass@localhost:5432/mcp_chat
```

## Verify Connection

Once Postgres is running, test the connection:
```bash
uv run python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://mcp_user:mcp_pass@localhost:5432/mcp_chat'))"
```

## Database Configuration

- **Database Name**: mcp_chat
- **User**: mcp_user
- **Password**: mcp_pass
- **Port**: 5432
- **Host**: localhost

## Next Steps

After Postgres is running:
1. Install dependencies: `uv add asyncpg sqlalchemy[asyncio] alembic`
2. Run migrations to create tables
3. Start the application
