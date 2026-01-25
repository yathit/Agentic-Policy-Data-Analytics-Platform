#!/bin/bash
# Database seeding script for mock IMDA internal datasets
# Seeds PostgreSQL with policy-plausible synthetic data

set -e  # Exit on error

# Database connection parameters (can be overridden by environment variables)
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-policy_analytics}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/seed_internal_data.sql"

echo "========================================="
echo "IMDA Policy Analytics - Database Seeding"
echo "========================================="
echo ""
echo "Database: ${DB_NAME}"
echo "Host: ${DB_HOST}:${DB_PORT}"
echo "User: ${DB_USER}"
echo ""

# Wait for database to be ready
echo "Waiting for database to be ready..."
for i in {1..30}; do
    if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1" > /dev/null 2>&1; then
        echo "✓ Database is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "✗ Database connection timeout"
        exit 1
    fi
    echo "  Attempt $i/30 - waiting..."
    sleep 2
done

echo ""
echo "Seeding internal datasets..."

# Execute SQL file
if [ -f "${SQL_FILE}" ]; then
    PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -f "${SQL_FILE}"
    echo "✓ Internal datasets seeded successfully"
else
    echo "✗ SQL file not found: ${SQL_FILE}"
    exit 1
fi

echo ""
echo "Verifying seeded data..."

# Verify each table
TABLES=("digital_sector_employment" "ai_workforce_programmes" "online_safety_incidents_summary" "emerging_tech_adoption_index")

for table in "${TABLES[@]}"; do
    COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT COUNT(*) FROM ${table};")
    echo "  ${table}: ${COUNT} rows"
done

echo ""
echo "========================================="
echo "✓ Database seeding completed successfully"
echo "========================================="

exit 0
