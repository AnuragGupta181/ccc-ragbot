Generate a locked requirements.txt from pyproject.toml
uv pip compile pyproject.toml -o requirements.txt



to use reqiremets.txt file
uv pip install -r requirements.txt

Add packages from requirements.txt to pyproject.toml
uv add -r requirements.txt


uv venv: Create a virtual environment.
uv add <package>: Add a single package.
uv pip install: Install packages (like pip).
uv sync: Install dependencies from your project's lock file.
uv pip compile: Compile dependencies into a lock file.
uv pip freeze: Generate a requirements file (or uv export for pylock.toml). 