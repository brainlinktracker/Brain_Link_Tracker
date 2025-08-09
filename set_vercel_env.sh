#!/bin/bash
# Helper script to set environment variables in Vercel for Brain Link Tracker
# Usage:
#   1. Install Vercel CLI if not already installed: npm i -g vercel
#   2. Log in to Vercel: vercel login
#   3. Run this script: sh set_vercel_env.sh
#   4. Follow prompts to enter your secrets.

echo "=== Setting environment variables for Vercel project ==="
read -p "Enter your Vercel project name: " PROJECT_NAME
read -p "Enter your Vercel scope (team/org slug or leave blank for personal): " SCOPE
read -p "Enter DATABASE_URL: " DATABASE_URL
read -p "Enter SECRET_KEY: " SECRET_KEY

if [ -z "$SCOPE" ]; then
  vercel env add DATABASE_URL production <<EOF
$DATABASE_URL
EOF

  vercel env add SECRET_KEY production <<EOF
$SECRET_KEY
EOF

  vercel env add DATABASE_TYPE production <<EOF
postgresql
EOF
else
  vercel env add DATABASE_URL production --scope "$SCOPE" --project "$PROJECT_NAME" <<EOF
$DATABASE_URL
EOF

  vercel env add SECRET_KEY production --scope "$SCOPE" --project "$PROJECT_NAME" <<EOF
$SECRET_KEY
EOF

  vercel env add DATABASE_TYPE production --scope "$SCOPE" --project "$PROJECT_NAME" <<EOF
postgresql
EOF
fi

echo "=== All environment variables set successfully in Vercel ==="
