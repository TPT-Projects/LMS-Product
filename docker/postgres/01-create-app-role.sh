#!/bin/sh
# Runs once, when the postgres volume is first created.
# Creates a NON-superuser role for the app. Superusers bypass Row Level
# Security, so the app must never connect as `postgres`.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-SQL
  CREATE ROLE "$APP_DB_USER" WITH LOGIN PASSWORD '$APP_DB_PASSWORD' CREATEDB NOSUPERUSER NOBYPASSRLS;
  CREATE DATABASE "$APP_DB" OWNER "$APP_DB_USER" ENCODING 'UTF8';
SQL
