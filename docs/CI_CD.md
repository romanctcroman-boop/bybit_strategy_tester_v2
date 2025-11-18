# CI/CD Documentation

## GitHub Actions Workflow

This project uses GitHub Actions for continuous integration and deployment. The workflow runs automatically on:
- Push to `main`, `develop`, or `feature/*` branches
- Pull requests to `main` or `develop`

### Jobs

#### 1. **Tests Job**
- **Matrix**: Runs on Python 3.13 and 3.14
- **Services**: PostgreSQL 15 + Redis 7
- **Steps**:
  1. Checkout code
  2. Set up Python environment
  3. Install dependencies (including bcrypt, pytest plugins)
  4. Run Alembic migrations
  5. Run pytest with coverage (target: 15%+)
  6. Upload coverage to Codecov
  7. Upload HTML coverage report as artifact

#### 2. **Lint Job**
- Runs code quality checks:
  - **Ruff**: Fast Python linter (E, F, I, UP, B, SIM rules)
  - **Black**: Code formatting checker (line-length: 100)
  - **isort**: Import sorting checker
- All checks set to `continue-on-error: true` for gradual adoption

#### 3. **Security Job**
- Runs security scans:
  - **Bandit**: Static security analysis (low-level issues only)
  - **Safety**: Dependency vulnerability checker
- Uploads security reports as artifacts

### Coverage Requirements

Current coverage: **15.46%**
Target coverage: **70%** (future goal)

Coverage is measured with `pytest-cov` and reported in multiple formats:
- Terminal output with missing lines
- HTML report (uploaded as artifact)
- XML report (for Codecov integration)

### Local Testing

Run the same checks locally:

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run tests with coverage
pytest tests/ -v --cov=backend --cov-report=term-missing --cov-report=html

# Check coverage threshold
coverage report --fail-under=15

# Run linters
ruff check backend/
black --check backend/ --line-length=100
isort --check-only backend/

# Run security scans
bandit -r backend/ -ll
safety check
```

### Branch Protection Rules (Recommended)

Configure in GitHub repository settings:

1. **Require status checks before merging**
   - ✅ tests (python-3.13)
   - ✅ tests (python-3.14)
   - ✅ lint
   - ✅ security

2. **Require branches to be up to date**
   - ✅ Enabled

3. **Require pull request reviews**
   - Minimum: 1 approving review
   - Dismiss stale reviews on new commits

4. **Require conversation resolution**
   - ✅ All conversations must be resolved

### Artifacts

The workflow uploads the following artifacts (retained for 30 days):

1. **coverage-report-py3.13**: HTML coverage report for Python 3.13
2. **coverage-report-py3.14**: HTML coverage report for Python 3.14
3. **security-reports**: Bandit security scan results (JSON)

### Environment Variables

The workflow uses these environment variables:

- `DATABASE_URL`: PostgreSQL connection string (service)
- `TESTCONTAINERS_RYUK_DISABLED`: Allow Docker reuse on GitHub runner
- `TESTING`: Flag to enable test mode
- `CODECOV_TOKEN`: Codecov upload token (repository secret)

### Adding Codecov Integration

1. Go to [codecov.io](https://codecov.io)
2. Sign in with GitHub
3. Add this repository
4. Copy the upload token
5. Add as repository secret: `CODECOV_TOKEN`

### Quick Win Results

All 4 Quick Wins completed with comprehensive test coverage:

| Quick Win | Endpoints | Tests | Coverage |
|-----------|-----------|-------|----------|
| #1: Performance Metrics Dashboard | 4 | 12 | 71.64% |
| #2: Strategy Template Library | 4 | 18 | 89.91% |
| #3: Enhanced Health Monitoring | 4 | 15 | 76.50% |
| #4: CSV Export Functionality | 2 | 8 | 100% |
| **Total** | **14** | **53** | **~80% avg** |

### Future Improvements

- [ ] Increase overall coverage to 70%+
- [ ] Enable stricter linting rules gradually
- [ ] Add E2E integration tests
- [ ] Add performance benchmarking
- [ ] Add Docker image building and pushing
- [ ] Add automatic deployment to staging
