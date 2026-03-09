# Python Virtual Environment Setup Guide

This project uses **uv** as its package manager and environment handler. Since virtual environments (`.venv/`) are platform-specific and excluded from GitHub, you will need to set up a new environment when running this project on a different computer (e.g., when moving from Windows to macOS).

## Prerequisites

- **[uv](https://docs.astral.sh/uv/)**: A fast Python package installer and resolver.
- **Git**: To clone and pull the latest changes.

## Setup Instructions

### 1. Install `uv`
If you don't have `uv` installed, run one of the following commands based on your OS:

- **macOS / Linux**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

### 2. Configure the Environment
Navigate to the root of the `idf_reader` project in your terminal:

```bash
cd path/to/idf_reader
```

Then, run the sync command to automatically create a `.venv` folder and install all necessary dependencies (like `eppy`, `geopandas`, etc.):

```bash
uv sync
```

### 3. Run the Project
You can now run the project using the newly created environment:

- **Via `uv` (recommended)**:
  ```bash
  uv run main.py
  ```
- **Via the activated environment**:
  ```bash
  # macOS / Linux
  source .venv/bin/activate
  python main.py

  # Windows
  .venv\Scripts\activate
  python main.py
  ```

## Why we don't push `.venv` to GitHub
- **Platform Specific**: Windows uses `.exe` and a `Scripts/` folder, while macOS uses a `bin/` folder.
- **Size**: Virtual environments can be hundreds of megabytes.
- **Paths**: The environment contains hardcoded paths to your local user directory that will not work on other machines.

---
*Created on 2026-03-09 to support cross-platform development (Windows/macOS).*
