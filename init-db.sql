-- init-db.sql
-- Create the reservation database if it doesn't exist
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'reservation_db')
BEGIN
    CREATE DATABASE reservation_db;
    PRINT 'Database reservation_db created successfully.';
END
ELSE
BEGIN
    PRINT 'Database reservation_db already exists.';
END
GO
