# notuv — deprecated

> **notuv is deprecated.** Use [veneer](https://github.com/alik-git/veneer-py) instead:
> ```
> uv tool install veneer-py
> veneer <same arguments>
> ```
> veneer is a drop-in replacement. Rename `notuv.toml` → `veneer.toml` and change `[notuv]` → `[veneer]`.

---

Editable Python installs in git worktrees without copying heavy dependencies.

`notuv` runs commands inside a shared conda environment with a
git-worktree-local `.venv` overlay. Use it when conda owns the heavy dependency
stack and each worktree needs its own editable Python installs.

## Why

If you have ever used Git worktrees for deep learning, you might be familiar
with the following problem:

You are working on your project as an editable package installed locally,
you have a conda env with big heavy packages like PyTorch and CUDA, and then
you make a new git worktree to work on a feature in parallel.

You run your code and it does not behave as expected, because the editable
Python package was still pointing to your original repo, not the new worktree.
Ouch.

So now you either have install the worktree as an editable package, which
breaks your original repo!

Or you can set PYTHONPATH= each time you run a command! Ew!

Or you can just set up a new conda env to stay sane, but then after 3 worktrees
you have 25GB of conda envs on your machine!

`notuv` solves this specific problem:

- one shared conda env owns the heavy dependency stack
- each worktree gets a tiny `.venv` overlay for its editable installs
- `notuv.toml` says which conda env and editable packages belong to that
  worktree
- `notuv <command>` runs inside the conda env, then puts the worktree `.venv`
  first

`notuv` keeps the split explicit:

- conda env: heavy shared dependencies
- worktree `.venv`: editable local packages and console scripts
- `notuv.toml`: the worktree's configuration

You do not need to `conda activate` the shared environment before running
`notuv` commands. `notuv` reads `notuv.toml`, applies the configured conda
environment to the child process, and keeps the worktree `.venv/bin` first on
`PATH`.

## Install

From PyPI:

```bash
python -m pip install notuv
```

For development from this checkout:

```bash
python -m pip install -e ".[dev]"
```

Check the command:

```bash
notuv --help
```

## Quick Start

Create one shared conda environment that has your normal dependencies, but not
the editable package you are developing:

```bash
conda create -n myproject-shared python=3.11 pip -y
conda run -n myproject-shared python -m pip install -U pip
```

For a real project, this is where you install PyTorch, CUDA-related packages,
MuJoCo, Isaac Sim, or whatever heavy dependencies the project needs.

In a git worktree, add `notuv.toml` at the git root:

```toml
[python]
base_conda_env = "myproject-shared"

[editables]
packages = [
  ".",
]
```

Create the worktree `.venv` and install configured editables:

```bash
notuv update-editables
```

Run commands through the worktree environment:

```bash
notuv python -c "import sys; print(sys.executable)"
notuv pytest
notuv python scripts/example.py
```

These commands do not require `conda activate myproject-shared` first. The
configured conda env still supplies native libraries, activation-script
environment variables, and shared dependencies.

Verify that your editable package is imported from the current worktree:

```bash
notuv python -c "import your_package; print(your_package.__file__)"
```

## Worktree-Local Config

If `notuv.toml` is local machine config, ignore it with the git worktree's
exclude file. In git worktrees, `.git` may be a file, so use `git rev-parse`:

```bash
EXCLUDE="$(git rev-parse --git-path info/exclude)"
mkdir -p "$(dirname "$EXCLUDE")"
printf '\n# Local notuv config\n/notuv.toml\n/.venv/\n' >> "$EXCLUDE"
```

If `notuv.toml` should be shared by the team, commit it instead and only ignore
`.venv/`.

## Multiple Editable Packages

One worktree can own an environment for several local packages:

```toml
[python]
base_conda_env = "myproject-shared"

[editables]
packages = [
  ".",
  "../some-sibling-package",
  "~/Projects/repos/some-canonical-package",
  "../another-sibling-package",
]
```

Relative editable paths are resolved from the git root. Editable paths may also
use absolute paths or `~`, which is useful for canonical shared checkouts such
as `~/Projects/repos/IsaacLab`. The `.venv` path defaults to `.venv` and must
stay inside the git root.

## Explicit Stack Configs

Several repos can share one dependency stack when they belong to the same local
development context. Keep that relationship explicit with a small repo-local
pointer config:

```text
worksets/my-feature/
  notuv.backend.toml
  .notuv/backend/.venv

  api-service/
    notuv.toml

  worker-service/
    notuv.toml
```

The shared stack config owns the base conda env, venv, and editable packages:

```toml
# worksets/my-feature/notuv.backend.toml
[notuv]
kind = "stack"

[python]
base_conda_env = "backend-shared"
venv = ".notuv/backend/.venv"

[editables]
packages = [
  "api-service",
  "worker-service",
  "~/Projects/repos/shared-library",
]
```

Each repo opts into that stack explicitly:

```toml
# worksets/my-feature/api-service/notuv.toml
[notuv]
extends = "../notuv.backend.toml"
```

Run commands from the repo you are working in:

```bash
cd worksets/my-feature/api-service
notuv info
notuv update-editables
notuv pytest
```

Commands run from the active repo root, while relative paths in the stack config
resolve from the stack config directory. A workset can have more than one stack
config when repos need different base conda environments.

Stack venvs may be shared by several repos. `notuv clean` refuses to remove a
shared stack venv unless you say so explicitly:

```bash
notuv clean --shared
```

## Commands

Show configuration without creating `.venv`:

```bash
notuv info
```

Create `.venv` if needed and install configured editables:

```bash
notuv update-editables
```

Run normal commands inside the configured conda env, with `.venv/bin` first on
`PATH`:

```bash
notuv python -m pytest
notuv pytest
notuv my-console-script --help
```

Remove the worktree `.venv`:

```bash
notuv clean
```

Remove a shared stack `.venv`:

```bash
notuv clean --shared
```

## Editable Installs

Editable installs are configured in `notuv.toml`, not through ad hoc pip
commands.

These intentionally fail:

```bash
notuv pip install -e .
notuv pip install --editable ../some-package
notuv python -m pip install -e .
```

Use this instead:

```toml
[editables]
packages = [
  ".",
  "../some-package",
]
```

```bash
notuv update-editables
```

By default, `update-editables` uses `pip install --no-deps -e ...` because the
base conda environment is expected to own dependencies. If a repo really needs
editable dependencies installed into `.venv`, set:

```toml
[editables]
install_deps = true
packages = ["."]
```

## Config Reference

Repo-local config:

```toml
[python]
base_conda_env = "myproject-shared"
venv = ".venv"

[editables]
packages = ["."]
install_deps = false
```

Pointer config:

```toml
[notuv]
extends = "../notuv.backend.toml"
```

Stack config:

```toml
[notuv]
kind = "stack"

[python]
base_conda_env = "backend-shared"
venv = ".notuv/backend/.venv"

[editables]
packages = ["api-service", "worker-service"]
install_deps = false
```

Fields:

- `notuv.extends`: optional path from a repo-local pointer config to one stack
  config.
- `notuv.kind`: set to `"stack"` in stack configs.
- `python.base_conda_env`: required conda environment name.
- `python.venv`: optional virtual environment path. Defaults to `.venv`. In
  repo configs, it must stay inside the repo root. In stack configs, it must
  stay inside the stack config directory. Absolute paths are accepted only when
  they remain inside the allowed root.
- `editables.packages`: editable package paths. Relative paths resolve from the
  config file that declares them. Absolute paths and `~` are also accepted.
- `editables.install_deps`: whether pip should install dependencies while
  installing editables. Defaults to `false`.

## Troubleshooting

If `notuv` is not found, install it in the active Python environment:

```bash
python -m pip install --upgrade notuv
```

If `notuv` says `missing notuv.toml`, make sure you are inside a git worktree
and that `notuv.toml` exists at the git root:

```bash
git rev-parse --show-toplevel
```

If imports come from the wrong place, check the active paths:

```bash
notuv info
notuv python -c "import your_package; print(your_package.__file__)"
```

If `.venv` gets stale, remove and recreate it:

```bash
notuv clean
notuv update-editables
```

## Unsupported By Design

Version 1 does not support uv-managed environments, non-conda base
environments, or automatic dependency solving. Those can be added later if the
conda-backed overlay workflow proves useful.
