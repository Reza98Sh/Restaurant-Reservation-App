#!/bin/bash
# init-db.sh
# Wait for SQL Server to be ready and then create the database

# Wait for SQL Server to start
echo "Waiting for SQL Server to start..."
sleep 15

# Run the SQL script to create the database
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C -i /docker-entrypoint-initdb.d/init-db.sql

echo "Database initialization completed."
