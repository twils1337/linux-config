# linux-config

`config-me` sets up a fresh **Ubuntu VM or WSL distro** in one run. It walks you through three sections: programming languages, a container engine, and AI CLI tools. Then it installs, updates or removes everything, with live logs or a progress bar.

It's a single Python file that uses only the standard library, so it runs on a stock Ubuntu with nothing to `pip install`.

## Quick start

```bash
git clone https://github.com/twils1337/linux-config.git
cd linux-config
./config-me            # interactive
```

Or grab just the script:

```bash
curl -fsSL https://raw.githubusercontent.com/twils1337/linux-config/main/config-me -o ~/.local/bin/config-me
chmod +x ~/.local/bin/config-me
```

**Requirements:** Ubuntu 22.04 or 24.04 (other apt-based Ubuntu releases usually work), `python3` (preinstalled on Ubuntu), and `sudo`. Run it as your **normal user**. It calls `sudo` itself for system packages (you're asked for your password once), and installs per-user tools such as nvm, rustup, uv and the AI CLIs into your home directory.

## How a run works

1. **Languages:** a checkbox list. Use ↑/↓ (or j/k) to move, space to toggle, `a` to select all or none, and Enter to confirm.

   ```text
   1) Programming languages  ↑/↓ move · space toggle · a all/none · Enter confirm
    › [x] Node.js
      [ ] C# (.NET SDK)
      [ ] Java (Eclipse Temurin JDK)
      [x] Go
      [ ] Python
      [ ] Rust
   ```

   For each selected language you're asked:

   - **Version:** Enter or `y` installs the **latest LTS**, `latest` installs the newest release regardless of LTS, a version installs that version (`22`, `22.11.0`, `3.12`, `1.24.3`, `21`…), and `n` skips it. Languages without an LTS (Go, Python, Rust) fall back to latest. The prompt shows what LTS and latest currently resolve to.
   - **Version manager (optional):** Enter or `n` uses the default install method; otherwise type a manager's name (table below).

2. **Container engine:** a radio list where at most one can be selected. Press Enter with nothing selected to skip the section. If a different engine is already installed, you get a warning.

3. **AI CLI tools:** a checkbox list, each followed by a version prompt.

4. **Already installed?** For anything that's already on the system you choose **[U]pdate / [r]emove / [k]eep**. Enter means update.

5. **Plan and confirm:** you see the full list of actions, then **Go ahead? [Y/n]**.

6. **Execution:** a log of every command and its output, then a summary. A failed item doesn't stop the rest: it's reported in the summary and the exit code is 1.

When stdin isn't a terminal (piped input, CI), the checkbox lists become numbered prompts: type `1 3 4` and press Enter.

## What it installs

### Languages

| Language | Default install (no version manager) | Optional version managers | "LTS" means |
|---|---|---|---|
| **Node.js** | official nodejs.org build in `/usr/local/lib/nodejs`, linked into `/usr/local/bin` | `nvm`, `fnm`, `mise` | current Node LTS line |
| **C# / .NET** | Microsoft's `dotnet-install.sh` into `~/.dotnet` | `mise` | newest .NET LTS SDK |
| **Java** | Eclipse Temurin JDK from Adoptium's apt repo | `sdkman`, `mise` | newest Java LTS (e.g. 25) |
| **Go** | official go.dev tarball in `/usr/local/go` | `mise` | no LTS → latest |
| **Python** | `deadsnakes` PPA packages (`python3.X`, `-venv`, `-dev`) | `uv`, `pyenv`, `mise` | no LTS → latest |
| **Rust** | `rustup` (Rust's official installer and manager) | `mise` | no LTS → current stable |

Notes:

- **Python:** Ubuntu's own `/usr/bin/python3` is never replaced or removed, because the OS depends on it. New versions are installed alongside it (`python3.13`, or `uv`/`pyenv` shims).
- **Java via SDKMAN!:** you can give a full SDKMAN id, such as `21.0.5-tem`.
- **.NET:** you can give a channel (`8`, `9.0`) or an exact SDK version (`8.0.404`).

### Container engine (one at most)

| Engine | Installs |
|---|---|
| **Docker Engine** | `docker-ce`, CLI, `containerd.io`, Buildx and Compose plugins from Docker's apt repo. Removes conflicting distro packages, adds you to the `docker` group. |
| **Podman** | `podman` plus rootless helpers (`uidmap`, `slirp4netns`, `fuse-overlayfs`) |
| **containerd** | `containerd` + `runc`, plus the `nerdctl` CLI (Docker-compatible) |

Engines have no LTS, so Enter installs the newest packaged version. A specific version is matched against `apt-cache madison`.

### AI CLI tools (multi-select)

| Tool | Installed with | Version prompt |
|---|---|---|
| **Claude Code** | Anthropic's native installer (`claude.ai/install.sh`), auto-updating | Enter = `stable` channel, `latest`, or a version |
| **OpenAI Codex CLI** | `npm` package `@openai/codex` into `~/.local` | Enter = latest, or a version |
| **GitHub Copilot CLI** | GitHub's install script (`gh.io/copilot-install`) into `~/.local/bin` | Enter = latest, or a version |
| **Google Gemini CLI** | `npm` package `@google/gemini-cli` into `~/.local` | Enter = latest, or a version |

The npm-based tools need Node.js 20 or newer. If Node is missing or older, `config-me` installs the Node LTS first. Global npm packages go into `~/.local`, so no `sudo npm` is needed, and they work with any Node install method.

## Flags

| Flag | What it does |
|---|---|
| *(none)* | Interactive setup (the flow above). |
| `-y` | Agree to everything, like `apt -y`: no questions, every default. That means **all languages** at LTS with their default install method, **Docker**, and **all AI CLIs**, and already-installed software is updated. With `-rm`, it skips the confirmation. |
| `-blang` | Install the **latest LTS of every language** (latest where there's no LTS), and nothing else. No questions. |
| `-rm [SECTION/TOOL…]` | Uninstall. With no arguments, everything `config-me` manages (plus mise, if `config-me` installed it). Otherwise only the given sections or tools, for example `-rm ai`, `-rm containers`, `-rm lang`, `-rm node rust`. It scans the system and only touches what's actually installed, and it asks for confirmation unless `-y` is given. |
| `-stat` | List managed software by section with installed versions and install methods, plus the version managers it found. |
| `-mute` | No log output. Shows a progress bar (`[██████░░░░] 60% (3/5) install Go latest`) instead. The full log is still written to the log file, and warnings and errors are still shown. |
| `--dry-run` | Print every command that would run, without changing anything. |
| `--version`, `-h` | Version and help. |

Section names for `-rm`: `lang` (also `languages`), `containers` (also `images`, `engine`), `ai`. Tool ids: `node dotnet java go python rust docker podman containerd claude codex copilot gemini`.

```bash
config-me -y                 # whole machine, no questions
config-me -blang -mute       # just the languages, with a progress bar
config-me -stat              # what's installed?
config-me -rm ai             # remove Claude Code, Codex, Copilot, Gemini
config-me -rm docker -y      # remove Docker without asking
config-me -rm                # remove everything config-me manages
config-me --dry-run -y       # preview a full run
```

## Details worth knowing

- **apt is refreshed only when needed.** `apt-get update` runs at most once per run: only if the package lists are more than 6 hours old, or right after a repository is added (Docker, Adoptium, deadsnakes). apt waits for the dpkg lock instead of failing when `unattended-upgrades` is running.
- **Shell setup** goes in one marked block in `~/.bashrc` (and `~/.zshrc` if you have one):

  ```bash
  # >>> config-me >>>
  export PATH="/usr/local/go/bin:$HOME/go/bin:$PATH"  # config-me:go
  [ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"  # config-me:rust
  # <<< config-me <<<
  ```

  Each line is tagged, so uninstalling removes exactly its own lines, and the block disappears when it's empty. Open a new terminal (or run `exec $SHELL -l`) after installing.
- **State and logs** live in `~/.local/state/config-me/`: `state.json` records what was installed and how (so updates and removals use the right method), and `config-me.log` holds the full output of every run.
- **Kept on uninstall:** Docker's data (`/var/lib/docker`) and Claude Code's settings (`~/.claude`). The summary tells you where they are.
- **WSL:** on distros without systemd, services (Docker, containerd) are started with `service`. To have them start automatically, enable systemd in `/etc/wsl.conf` (`[boot]` and `systemd=true`) and run `wsl --shutdown`.
- **Switching methods:** if you update a language using a different method than it was installed with (say Node from the official build to nvm), both stay installed and the first one on `PATH` wins. `config-me` warns you; remove the old one with `-rm`.

## Development

```bash
python3 -m unittest discover -s tests -v     # unit tests (network lookups are mocked)
./config-me --dry-run -y                     # see every command a full run would execute
```

CI (`.github/workflows/test.yml`) runs the unit tests on Python 3.9 and 3.12. It also does **real installs** in fresh `ubuntu:22.04` and `ubuntu:24.04` containers as a normal sudo user, in three scenarios: `-blang`, `-y`, and an interactive run with nvm, SDKMAN!, mise and uv. Each scenario then checks that the tools work in a new login shell, runs `-stat`, and finishes with `-rm` to confirm nothing is left behind.
