# Publishing Kyromesh Python SDK to PyPI

## Automated Publishing (Recommended)

The repository includes GitHub Actions workflows that automatically:
1. Sync the SDK to the public OSS repository
2. Publish to PyPI
3. Create GitHub Releases

This happens when you create a git tag matching `sdk-python-v*`.

### Steps

1. **Update version** in `pyproject.toml`:
   ```toml
   [project]
   version = "0.2.0"  # Update to new version
   ```

2. **Create and push a git tag**:
   ```bash
   git tag sdk-python-v0.2.0
   git push origin sdk-python-v0.2.0
   ```

3. **GitHub Actions will automatically**:
   - Build the distribution packages
   - Verify the packages
   - Publish to PyPI
   - Create a GitHub Release

### Setup (One-time)

To enable automated publishing, configure PyPI Trusted Publisher:

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new trusted publisher:
   - **PyPI Project Name**: `kyromesh`
   - **GitHub Repository Owner**: Your GitHub org/user
   - **Repository Name**: `kyromesh`
   - **Workflow Name**: `publish-python-sdk.yml`
   - **Environment Name**: `pypi`

## Manual Publishing

If you prefer to publish manually:

```bash
# Install build tools
pip install build twine

# Build packages
cd packages/sdk-python
python -m build

# Verify packages
twine check dist/*

# Upload to PyPI
twine upload dist/*
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH** (e.g., 0.1.0)
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes
