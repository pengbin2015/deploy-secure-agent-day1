# Setup

Kestrel runs locally with no containers and one required dependency: LangGraph.

## Clean machine prerequisites

Install Python 3.10 or newer, Git, and VS Code before cloning the repository.

### Windows

Download and install these applications:

- [Python 3](https://www.python.org/downloads/windows/) - select **Add Python
  to PATH** in the installer.
- [Git for Windows](https://git-scm.com/download/win)
- [Visual Studio Code](https://code.visualstudio.com/download)

Close and reopen VS Code after installing them so Python and Git are available
in its integrated terminal.

### macOS

Install [Homebrew](https://brew.sh/) if it is not already installed, then run:

```bash
brew install python@3.12 git
brew install --cask visual-studio-code
```

### Linux (Debian or Ubuntu)

Run:

```bash
sudo apt update
sudo apt install --yes python3 python3-venv python3-pip git
```

Install VS Code using the package for your Linux distribution from the
[VS Code download page](https://code.visualstudio.com/download).

## Local environment

Clone the repository, then use a project-local virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On macOS or Linux, use a POSIX shell instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Select `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on macOS
and Linux as the VS Code Python interpreter. The virtual environment is already
excluded from Git.

Initialize and check the project:

```
python -m kestrel seed
python -m kestrel doctor
```

The doctor checks the Python version, database, tool registry, and an
end-to-end scenario. It also checks the gateway and Langfuse when configured.

## Persistence

Kestrel stores its local state in SQLite. Commit and push your work at the end
of each workshop so it is available from any machine you use later.
