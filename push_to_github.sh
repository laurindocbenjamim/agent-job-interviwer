#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Default commit message if none is provided
COMMIT_MSG=${1:-"feat(admin): add real-time CV dashboard and fix camera permissions"}

# Current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "📦 Staging changes..."
git add .

echo "📝 Committing changes..."
git commit -m "$COMMIT_MSG"

echo "🚀 Pushing to origin $BRANCH..."
git push origin "$BRANCH"

echo "✅ Successfully pushed to GitHub!"
