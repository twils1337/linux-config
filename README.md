# linux-config

`config-me` sets up a fresh **Ubuntu VM or WSL distro** in one run. It walks you through three sections: programming languages, a container engine, and AI CLI tools. Then it installs, updates or removes everything, with live logs or a progress bar.

It's a single Python file that uses only the standard library, so it runs on a stock Ubuntu with nothing to `pip install`.

## Quick start

```bash
git clone https://github.com/twils1337/linux-config.git
cd linux-config
./config-me            # interactive
```

Or download just the script into the current folder:

```bash
curl -fsSLO https://raw.githubusercontent.com/twils1337/linux-config/main/config-me
chmod +x config-me
./config-me
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

Before the first question, `config-me` gathers everything it needs in one go, in parallel: what's already installed, and the current LTS/latest versions of every tool. One progress line ("checking what's installed and looking up the latest versions online… 18/28") shows while this runs, usually for a few seconds. After that, every question answers instantly, and the install steps reuse the same data.

6. **Execution:** a log of every command and its output, then a summary. The script always says what it's waiting on: a notice when another apt process (such as `unattended-upgrades`) holds the package lock, and a "still downloading… (45s so far)" line whenever a step has been quiet for 15 seconds. With `-mute`, those notices appear in the progress bar instead. A failed item doesn't stop the rest: it's reported in the summary and the exit code is 1.

When stdin isn't a terminal (piped input, CI), the checkbox lists become numbered prompts: type `1 3 4` and press Enter.

## What it installs

### Languages

| Language | Default install (no version manager) | Optional version managers | "LTS" means |
|---|---|---|---|
| **Node.js** | official nodejs.org build in `/usr/local/lib/nodejs`, linked into `/usr/local/bin` | `nvm`, `fnm`, `mise` | current Node LTS line |
| **C# / .NET** | Microsoft's `dotnet-install.sh` into `~/.dotnet` | `mise` | newest .NET LTS SDK |
| **Java** | Eclipse Temurin JDK from Adoptium's apt repo | `sdkman`, `mise` | newest Java LTS (e.g. 25) |
| **Go** | official go.dev tarball in `/usr/local/go` | `mise` | no LTS → latest |
| **Python** | `python3.X` (with `-venv`, `-dev`) from Ubuntu's own repos when available, otherwise the `deadsnakes` PPA (signing key verified by fingerprint) | `uv`, `pyenv`, `mise` | no LTS → latest |
| **Rust** | `rustup` (Rust's official installer and manager) | `mise` | no LTS → current stable |

Notes:

- **Python:** if deadsnakes doesn't support your Ubuntu release yet (it can lag behind brand-new releases), `config-me` says so; pick `uv` or `pyenv` instead. Ubuntu's own `/usr/bin/python3` is never replaced or removed, because the OS depends on it. New versions are installed alongside it (`python3.13`, or `uv`/`pyenv` shims).
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
| `-y` | Answer **yes to confirmations**, like `apt -y`: "Go ahead?", the `-rm` confirmation, and every package-manager prompt behind the scenes. Your choices (which languages, versions, version managers, engine and AI tools, and update/remove/keep) are **still asked**. |
| `-blang` | Install the **latest LTS of every language** (latest where there's no LTS), and nothing else. Fully automatic: no questions at all. |
| `-rm [SECTION/TOOL…]` | Uninstall. With no arguments, everything `config-me` manages (plus mise, if `config-me` installed it). Otherwise only the given sections or tools, for example `-rm ai`, `-rm containers`, `-rm lang`, `-rm node rust`. It scans the system and only touches what's actually installed, and it asks for confirmation unless `-y` is given. |
| `-stat` | List managed software by section with installed versions and install methods, plus the version managers it found. |
| `-mute` | No log output. Shows a progress bar (`[██████░░░░] 60% (3/5) install Go latest`) instead. The full log is still written to the log file, and warnings and errors are still shown. |
| `--dry-run` | Print every command that would run, without changing anything. |
| `--version`, `-h` | Version and help. |

Section names for `-rm`: `lang` (also `languages`), `containers` (also `images`, `engine`), `ai`. Tool ids: `node dotnet java go python rust docker podman containerd claude codex copilot gemini`.

```bash
config-me -y                 # interactive choices, but no "Go ahead?" confirmations
config-me -blang -mute       # just the languages, with a progress bar
config-me -stat              # what's installed?
config-me -rm ai             # remove Claude Code, Codex, Copilot, Gemini
config-me -rm docker -y      # remove Docker without asking
config-me -rm                # remove everything config-me manages
config-me --dry-run -blang   # preview a run without changing anything
```

## Details worth knowing

- **IPv4 for its own `curl` calls.** Every `curl` command `config-me` runs itself uses `curl -4`, because broken IPv6 routes (common on WSL) can stall connections for minutes. Nothing else is changed: apt, and the vendor install scripts it runs (nvm, mise, uv, SDKMAN!, Claude Code and others), use your system's normal network settings.
- **apt is refreshed only when needed.** `apt-get update` runs at most once per run: only if the package lists are more than 6 hours old, or right after a repository is added (Docker, Adoptium, deadsnakes). apt waits for the dpkg lock instead of failing when `unattended-upgrades` is running.
- **Shell setup** goes in one marked block in `~/.bashrc` (and `~/.zshrc` if you have one):

  ```bash
  # >>> config-me >>>
  export PATH="/usr/local/go/bin:$HOME/go/bin:$PATH"  # config-me:go
  [ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"  # config-me:rust
  # <<< config-me <<<
  ```

  Each line is tagged with its tool. A tool's lines are only added if they're missing; if they're already there they're left exactly as they are, including any edits you made. Uninstalling removes exactly that tool's lines, and the block disappears when it's empty. Open a new terminal (or run `exec $SHELL -l`) after installing.
- **State and logs** live in `~/.local/state/config-me/`: `state.json` records what was installed and how (so updates and removals use the right method), and `config-me.log` holds the full output of every run.
- **Kept on uninstall:** Docker's data (`/var/lib/docker`) and Claude Code's settings (`~/.claude`). The summary tells you where they are.
- **WSL:** on distros without systemd, services (Docker, containerd) are started with `service`. To have them start automatically, enable systemd in `/etc/wsl.conf` (`[boot]` and `systemd=true`) and run `wsl --shutdown`.
- **Switching methods:** if you update a language using a different method than it was installed with (say Node from the official build to nvm), both stay installed and the first one on `PATH` wins. `config-me` warns you; remove the old one with `-rm`.

## Development

```bash
python3 -m unittest discover -s tests -v     # unit tests (network lookups are mocked)
./config-me --dry-run -blang                  # see every command a run would execute
```

CI (`.github/workflows/test.yml`) runs the unit tests on Python 3.9 and 3.12. It also does **real installs** in fresh `ubuntu:22.04`, `ubuntu:24.04` and `ubuntu:26.04` containers as a normal sudo user, in three scenarios: `-blang`, a full run with `-y` (choices piped in), and an interactive run with nvm, SDKMAN!, mise and uv. Each scenario then checks that the tools work in a new login shell, runs `-stat`, and finishes with `-rm` to confirm nothing is left behind.
