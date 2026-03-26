# Contributing

Thanks for your interest in contributing to Ops Automation Using SRE Agent!

## Development Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/<org>/ops-automation-using-sre-agent.git
   cd ops-automation-using-sre-agent
   ```

2. **Create a Python virtual environment (3.11+):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Install the portal frontend (optional):**
   ```bash
   cd portal && npm install && cd ..
   ```

## Running Tests

```bash
pytest
```

To run with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

## Pull Request Guidelines

- **Branch from `main`** — create a feature branch (e.g., `feature/add-cmdb-adapter`).
- **Keep PRs focused** — one logical change per PR.
- **Write tests** — new features and bug fixes should include tests.
- **Update docs** — if your change affects architecture, setup, or usage, update the relevant files in `docs/`.
- **Pass CI** — ensure `pytest` passes and there are no linting errors before submitting.
- **Describe your changes** — include a clear title and description in the PR explaining what and why.

## Code Style

- Python: follow [PEP 8](https://peps.python.org/pep-0008/). Use type hints where practical.
- TypeScript (portal): follow the existing ESLint configuration.

## Reporting Issues

Open a GitHub issue with a clear description, steps to reproduce, and expected vs. actual behavior.
