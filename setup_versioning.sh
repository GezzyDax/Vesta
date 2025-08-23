#!/bin/bash
# Setup automatic versioning for Vesta

echo "Setting up automatic semantic versioning for Vesta..."

# Make scripts executable
chmod +x scripts/version_bump.py

# Setup git hooks (if not already done)
if [ ! -f ".git/hooks/post-commit" ] || ! grep -q "version_bump.py" .git/hooks/post-commit; then
    echo "Setting up git post-commit hook..."
    cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
# Post-commit hook for automatic version bumping

# Change to repository root
cd "$(git rev-parse --show-toplevel)"

# Run version bump script
if [ -f "scripts/version_bump.py" ]; then
    echo "Updating version..."
    python3 scripts/version_bump.py --type auto
    
    # Show new version
    python3 scripts/version_bump.py --show
fi
EOF
    chmod +x .git/hooks/post-commit
    echo "✓ Git hook installed"
fi

# Test version script
echo "Testing version script..."
python3 scripts/version_bump.py --show

echo ""
echo "🎉 Automatic versioning is now set up!"
echo ""
echo "How it works:"
echo "• Every commit will automatically bump the version"
echo "• Use conventional commit messages:"
echo "  - feat: new feature → minor bump (1.0.0 → 1.1.0)"
echo "  - fix: bug fix → patch bump (1.0.0 → 1.0.1)"
echo "  - BREAKING CHANGE → major bump (1.0.0 → 2.0.0)"
echo ""
echo "Current version is shown in the app footer and /about page"