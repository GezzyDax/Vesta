#!/bin/bash
# Build script that passes git information to Docker

set -e

echo "🔧 Building Vesta with git information..."

# Get git information
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Git Commit: $GIT_COMMIT"
echo "Git Branch: $GIT_BRANCH"
echo "Build Date: $BUILD_DATE"

# Export for docker-compose
export GIT_COMMIT
export GIT_BRANCH
export BUILD_DATE

# Build with docker-compose
echo "🐳 Building Docker containers..."
docker-compose down
docker-compose build --no-cache

echo "🚀 Starting services..."
docker-compose up -d

echo "✅ Build complete!"
echo "🌐 Application available at: http://localhost:5000"
echo "ℹ️  Version info at: http://localhost:5000/about"