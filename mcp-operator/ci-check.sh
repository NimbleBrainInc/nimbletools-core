#!/bin/bash

# CI Check Script - Replicates GitHub Actions workflow locally
set -e  # Exit on any error

echo "🚀 Starting Local CI Checks..."
echo "================================"

# Check if we're in the operator directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Must be run from the operator directory"
    exit 1
fi

# Step 1: Install dependencies (equivalent to CI step)
echo "📦 Installing dependencies..."
uv sync --dev --frozen

# Step 2: Run linting (exact CI command)
echo "🔍 Running linting..."
uv run ruff check src/ tests/

# Step 3: Run type checking (exact CI command) 
echo "🏷️  Running type checking..."
uv run mypy --package nimbletools_core_operator

# Step 4: Run tests with coverage (exact CI command)
echo "🧪 Running tests with coverage..."
uv run pytest tests/ --cov=nimbletools_core_operator --cov-report=xml --cov-report=term-missing

echo ""
echo "✅ All CI checks passed!"
echo "🎉 Your code is ready to commit!"