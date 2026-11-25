"""Unit tests for config-me. Run: python3 -m unittest discover -s tests -v

Network lookups are replaced with fixtures, and HOME/state live in a temp dir.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
_TMP = tempfile.TemporaryDirectory()
os.environ["XDG_STATE_HOME"] = str(Path(_TMP.name) / "state")


def load():
    loader = importlib.machinery.SourceFileLoader("config_me", str(ROOT / "config-me"))
    spec = importlib.util.spec_from_loader("config_me", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["config_me"] = mod
    loader.exec_module(mod)
    return mod


cm = load()

FIXTURES = {
    cm.Node.INDEX: [
        {"version": "v26.0.0-alpha.0.1.1", "lts": False},
        {"version": "v25.2.0", "lts": False},
        {"version": "v24.11.1", "lts": "Krypton"},
        {"version": "v24.10.0", "lts": False},
        {"version": "v22.21.0", "lts": "Jod"},
        {"version": "v22.9.0", "lts": False},
        {"version": "v20.19.5", "lts": "Iron"},
    ],
    cm.DotNet.INDEX: {"releases-index": [
        {"channel-version": "11.0", "latest-sdk": "11.0.100-preview.1", "release-type": "sts", "support-phase": "preview"},
        {"channel-version": "10.0", "latest-sdk": "10.0.100", "release-type": "lts", "support-phase": "active"},
        {"channel-version": "9.0", "latest-sdk": "9.0.307", "release-type": "sts", "support-phase": "active"},
        {"channel-version": "8.0", "latest-sdk": "8.0.416", "release-type": "lts", "support-phase": "active"},
        {"channel-version": "7.0", "latest-sdk": "7.0.410", "release-type": "sts", "support-phase": "eol"},
    ]},
    cm.Java.API: {"most_recent_lts": 25, "most_recent_feature_release": 25, "available_releases": [8, 11, 17, 21, 25]},
    cm.Go.DL: [{"version": "go1.25.4", "stable": True}, {"version": "go1.24.10", "stable": True}],
    cm.Go.DL + "&include=all": [
        {"version": "go1.25.4", "stable": True}, {"version": "go1.25rc1", "stable": False},
        {"version": "go1.24.10", "stable": True}, {"version": "go1.24.9", "stable": True},
        {"version": "go1.22.12", "stable": True},
    ],
    cm.Python.EOL: [
        {"cycle": "3.14", "latest": "3.14.0"}, {"cycle": "3.13", "latest": "3.13.9"},
        {"cycle": "3.12", "latest": "3.12.12"},
    ],
    "https://registry.npmjs.org/@openai/codex": {"dist-tags": {"latest": "0.63.0"}},
    "https://registry.npmjs.org/@google/gemini-cli": {"dist-tags": {"latest": "0.17.1"}},
}


def fake_http_json(url):
    if url in FIXTURES:
        return FIXTURES[url]
    raise cm.urllib.error.URLError(f"no fixture for {url}")


class Base(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(cm, "HOME", Path(self.home.name)),
            mock.patch.object(cm, "http_json", side_effect=fake_http_json),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.home.cleanup()

    def ctx(self, dry_run=True, mute=True):
        ui = cm.UI(mute=mute)
        run = cm.Runner(ui, dry_run=dry_run)
        return cm.Ctx(ui=ui, run=run, apt=cm.Apt(run), rc=cm.ShellRc(ui, dry_run), state=cm.State(dry_run=True),
                      dry_run=dry_run)


class VersionAnswers(unittest.TestCase):
    def test_enter_and_y_mean_lts(self):
        for a in ("", "y", "Y", "yes", "lts", "  "):
            self.assertEqual(cm.parse_version_answer(a), "lts", a)

    def test_latest_skip_and_explicit(self):
        self.assertEqual(cm.parse_version_answer("latest"), "latest")
        self.assertEqual(cm.parse_version_answer("LATEST"), "latest")
        self.assertIsNone(cm.parse_version_answer("n"))
        self.assertIsNone(cm.parse_version_answer("N"))
        self.assertEqual(cm.parse_version_answer("22.11.0"), "22.11.0")


class PickVersion(unittest.TestCase):
    def test_prefix_and_exact(self):
        vs = ["v22.9.0", "v22.21.0", "v20.19.5", "v2.1.0"]
        self.assertEqual(cm.pick_version(vs, "22"), "v22.21.0")
        self.assertEqual(cm.pick_version(vs, "v22.9"), "v22.9.0")
        self.assertEqual(cm.pick_version(vs, "2"), "v2.1.0", "'2' must not match 22.x")
        self.assertEqual(cm.pick_version(vs, "20.19.5"), "v20.19.5")
        self.assertIsNone(cm.pick_version(vs, "18"))

    def test_vkey_orders_numerically(self):
        self.assertGreater(cm.vkey("1.22.10"), cm.vkey("1.22.9"))


class Resolution(Base):
    def test_node(self):
        n = cm.Node()
        self.assertEqual(n.lts(), "v24.11.1")
        self.assertEqual(n.latest(), "v25.2.0", "prereleases are not 'latest'")
        self.assertEqual(n.resolve_specific("26", "official") if False else n.lts(), "v24.11.1")
        with self.assertRaises(ValueError):
            n.resolve_specific("26", "official")
        self.assertEqual(n.resolve_specific("22", "official"), "v22.21.0")

    def test_dotnet_skips_preview_and_eol(self):
        d = cm.DotNet()
        self.assertEqual(d.lts(), "10.0.100")
        self.assertEqual(d.latest(), "10.0.100")
        self.assertEqual(d.resolve_specific("8", "dotnet-install"), "8.0.416")
        self.assertEqual(d.resolve_specific("9.0", "dotnet-install"), "9.0.307")
        self.assertEqual(d.resolve_specific("8.0.100", "dotnet-install"), "8.0.100")

    def test_java(self):
        j = cm.Java()
        self.assertEqual(j.lts(), "25")
        self.assertEqual(j.resolve_specific("21", "temurin-apt"), "21")
        self.assertEqual(j.resolve_specific("21.0.5-tem", "sdkman"), "21.0.5-tem")
        with self.assertRaises(ValueError):
            j.resolve_specific("latest-ish", "temurin-apt")

    def test_go_has_no_lts_so_falls_back_to_latest(self):
        g = cm.Go()
        self.assertEqual(g.lts(), "1.25.4")
        self.assertEqual(g.resolve_specific("1.24", "official"), "1.24.10")
        self.assertEqual(g.resolve_specific("go1.22.12", "official"), "1.22.12")

    def test_python(self):
        p = cm.Python()
        self.assertEqual(p.lts(), "3.14.0")
        self.assertEqual(p.resolve_specific("3.12", "deadsnakes"), "3.12.12")

    def test_npm_cli_latest(self):
        self.assertEqual(cm.ITEMS["codex"].latest(), "0.63.0")

    def test_lookup_failure_is_a_clear_error_outside_dry_run(self):
        ctx = self.ctx(dry_run=False)
        with mock.patch.object(cm, "http_json", side_effect=cm.urllib.error.URLError("offline")):
            with self.assertRaises(cm.CommandError):
                cm.Node().resolve(ctx, "lts", "official")
            self.assertEqual(cm.Node().resolve(self.ctx(dry_run=True), "lts", "official"), "<lts>")


class Sdkman(Base):
    # Real `sdk list java` output format (SDKMAN 5.24, Nov 2026).
    LIST = """
 Temurin        |     | 27.0.1.1+4         | 27.0.1.1+4-tem
                |     | 25.0.5.1+2         | 25.0.5.1+2-tem
                |     | 21.0.13.1+2        | 21.0.13.1+2-tem
                |     | 21.0.9             | 21.0.9-tem
                |     | 17.0.21.1+2        | 17.0.21.1+2-tem
 Liberica       |     | 21.0.13.1-fx+5     | 21.0.13.1-fx+5-librca
                |     | 121.0.0            | 121.0.0-tem
"""

    def test_newest_temurin_for_major(self):
        ctx = self.ctx()
        with mock.patch.object(ctx, "probe", return_value=self.LIST):
            self.assertEqual(cm.Java()._sdkman_id(ctx, "21"), "21.0.13.1+2-tem")
            self.assertEqual(cm.Java()._sdkman_id(ctx, "17"), "17.0.21.1+2-tem")
            with self.assertRaises(ValueError):
                cm.Java()._sdkman_id(ctx, "99")


class AskItem(Base):
    def test_automatic_mode_never_waits_on_network_lookups(self):
        ctx = self.ctx()
        prompt = cm.Prompt(ctx.ui, automatic=True)
        with mock.patch.object(cm.Go, "detect", return_value=None), \
             mock.patch.object(cm.Go, "version_hint", side_effect=AssertionError("looked up versions under -y")), \
             contextlib.redirect_stdout(io.StringIO()):
            act = cm.ask_item(prompt, ctx, cm.ITEMS["go"], ask_manager=True)
        self.assertEqual((act.kind, act.spec, act.method), ("install", "lts", "official"))

    def test_interactive_prints_the_question(self):
        ctx = self.ctx(mute=False)
        prompt = cm.Prompt(ctx.ui)
        asked = []
        with mock.patch.object(cm.Go, "detect", return_value=None), \
             mock.patch("builtins.input", side_effect=lambda q: asked.append(q) or ""), \
             contextlib.redirect_stdout(io.StringIO()):
            cm.ask_item(prompt, ctx, cm.ITEMS["go"], ask_manager=True)
        self.assertTrue(any("Which version of Go" in q for q in asked), asked)
        self.assertTrue(any("version manager" in q for q in asked), asked)


class Waiting(Base):
    def test_quiet_command_gets_a_still_working_notice(self):
        ui = cm.UI(mute=False)
        run = cm.Runner(ui)
        buf = io.StringIO()
        with mock.patch.object(cm.time, "time", side_effect=cm.itertools_count(0, 20)), \
             contextlib.redirect_stdout(buf):
            run.run("sleep 1.5; echo done", check=False)
        self.assertIn("still", buf.getvalue())

    def test_describe(self):
        self.assertIn("apt", cm.Runner.describe("apt-get -o x install -y curl"))
        self.assertEqual(cm.Runner.describe("curl -fsSL x | tar -x"), "downloading")


class Prefetch(Base):
    def test_everything_is_looked_up_once_before_questions(self):
        ctx = self.ctx(mute=False)
        calls = {"detect": 0, "hint": 0}

        def det(self_, c):
            calls["detect"] += 1
            return None

        def hint(self_):
            calls["hint"] += 1
            cm.time.sleep(0.2)  # slow lookups run in parallel, not one after another
            return "latest=1.0"

        with mock.patch.object(cm.Item, "detect", det), mock.patch.object(cm.Item, "version_hint", hint), \
             mock.patch.object(cm.NpmCli, "version_hint", hint), mock.patch.object(cm.Rust, "version_hint", hint), \
             mock.patch.object(cm.AptEngine, "version_hint", hint), mock.patch.object(cm.ClaudeCode, "version_hint", hint), \
             mock.patch.object(cm.Copilot, "version_hint", hint), \
             mock.patch.object(cm.Node, "detect", det), mock.patch.object(cm.DotNet, "detect", det), \
             mock.patch.object(cm.Java, "detect", det), mock.patch.object(cm.Go, "detect", det), \
             mock.patch.object(cm.Python, "detect", det), mock.patch.object(cm.Rust, "detect", det), \
             mock.patch.object(cm.AptEngine, "detect", det), mock.patch.object(cm.Containerd, "detect", det), \
             mock.patch.object(cm.NpmCli, "detect", det), mock.patch.object(cm.ClaudeCode, "detect", det), \
             mock.patch.object(cm.Copilot, "detect", det), contextlib.redirect_stdout(io.StringIO()):
            start = cm.time.time()
            cm.prefetch(ctx, list(cm.ITEMS.values()))
            elapsed = cm.time.time() - start
            self.assertEqual(calls, {"detect": len(cm.ITEMS), "hint": len(cm.ITEMS)})
            self.assertLess(elapsed, 0.2 * len(cm.ITEMS) / 2, "lookups should run in parallel")
            with mock.patch("builtins.input", return_value=""):
                cm.ask_item(cm.Prompt(ctx.ui), ctx, cm.ITEMS["go"], ask_manager=True)
            self.assertEqual(calls, {"detect": len(cm.ITEMS), "hint": len(cm.ITEMS)}, "questions reuse the cache")


class IPv4(unittest.TestCase):
    def test_vendor_installers_curl_is_left_alone(self):
        self.assertNotIn("CURL_HOME", cm.Runner(cm.UI(mute=True)).env())


class Sudo(unittest.TestCase):
    def test_sudo_passes_env_explicitly_without_dash_e(self):
        run = cm.Runner(cm.UI(mute=True))
        run.is_root, run._sudo_ok = False, True
        with mock.patch.object(cm.subprocess, "Popen") as popen:
            popen.return_value.stdout = io.StringIO("")
            popen.return_value.wait.return_value = 0
            run.run("apt-get install -y curl", sudo=True)
        argv = popen.call_args.args[0]
        self.assertEqual(argv[:2], ["sudo", "env"])
        self.assertNotIn("-E", argv, "sudo-rs (Ubuntu 25.10+) rejects -E")
        self.assertIn("DEBIAN_FRONTEND=noninteractive", argv)


class Deadsnakes(Base):
    def test_added_with_curl_and_verified_key_not_add_apt_repository(self):
        ctx = self.ctx(dry_run=True, mute=False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cm.Python().add_deadsnakes(ctx, "3.14")
        out = buf.getvalue()
        self.assertNotIn("add-apt-repository", out)
        self.assertIn("curl -4", out)
        self.assertIn(cm.Python.DEADSNAKES_FPR, out, "key must be checked against its fingerprint")


class StaleGoroot(Base):
    def test_go_with_a_stale_goroot_is_detected_and_explained(self):
        ctx = self.ctx()
        answers = {"go version": None, "env -u GOROOT go version": "go version go1.27.4 linux/amd64",
                   "command -v go": "/usr/local/go/bin/go"}
        with mock.patch.dict(os.environ, {"GOROOT": "/home/x/.goenv/versions/1.25.5"}), \
             mock.patch.object(ctx, "probe", side_effect=lambda c: answers.get(c)):
            det = cm.Go().detect(ctx)
        self.assertIsNotNone(det, "a stale GOROOT must not make Go look uninstalled")
        self.assertEqual((det.version, det.method), ("1.27.4", "official"))
        self.assertIn("GOROOT", det.problem)
        self.assertIn("does not exist", det.problem)


class RcLinesOnUpdate(Base):
    """A tool whose manager already exists (earlier run, manual install) must still get its
    ~/.bashrc line; otherwise it looks uninstalled in every new terminal."""

    def bashrc(self):
        return (Path(self.home.name) / ".bashrc").read_text()

    def test_existing_rustup_still_gets_its_path_line(self):
        cargo_bin = Path(self.home.name) / ".cargo" / "bin"
        cargo_bin.mkdir(parents=True)
        (cargo_bin / "rustup").write_text("")
        (Path(self.home.name) / ".bashrc").write_text("")
        ctx = self.ctx(dry_run=False)
        ctx.rc = cm.ShellRc(ctx.ui)  # really write the rc file
        with mock.patch.object(ctx, "sh", return_value=(0, "")), mock.patch.object(ctx.apt, "install"), \
             mock.patch.object(ctx, "probe", return_value="rustc 1.91.0"), mock.patch.object(ctx.state, "set"):
            cm.Rust().install(ctx, "lts", "rustup")
        self.assertIn("# config-me:rust", self.bashrc())

    def test_existing_nvm_still_gets_its_lines(self):
        nvm = Path(self.home.name) / ".nvm"
        nvm.mkdir()
        (nvm / "nvm.sh").write_text("")
        (Path(self.home.name) / ".bashrc").write_text("")
        ctx = self.ctx(dry_run=False)
        ctx.rc = cm.ShellRc(ctx.ui)
        with mock.patch.object(ctx, "sh", return_value=(0, "")), mock.patch.object(ctx.apt, "install"), \
             mock.patch.object(ctx.state, "set"):
            cm.Node().install(ctx, "22.21.0", "nvm")
        self.assertIn("# config-me:nvm", self.bashrc())


class Executor(Base):
    def test_one_failing_item_does_not_stop_the_rest(self):
        ctx = self.ctx(dry_run=True)
        boom = mock.patch.object(cm.Go, "install", side_effect=ValueError("kaboom"))
        fine = mock.patch.object(cm.Rust, "install", return_value="1.91.0")
        with boom, fine as rust_install, contextlib.redirect_stdout(io.StringIO()) as out:
            code = cm.execute(ctx, cm.Plan([cm.Action(cm.ITEMS["go"], "install", "lts", "official"),
                                            cm.Action(cm.ITEMS["rust"], "install", "lts", "rustup")]))
        self.assertEqual(code, 1)
        rust_install.assert_called_once()
        self.assertIn("kaboom", out.getvalue())


class ShellRcBlock(Base):
    def test_add_replace_remove(self):
        rc_path = Path(self.home.name) / ".bashrc"
        rc_path.write_text("# user stuff\nalias ll='ls -l'\n")
        rc = cm.ShellRc(cm.UI(mute=True))
        rc.add("go", 'export PATH="/usr/local/go/bin:$PATH"')
        rc.add("rust", '. "$HOME/.cargo/env"')
        before = rc_path.read_text()
        rc.add("go", 'export PATH="/usr/local/go/bin:$HOME/go/bin:$PATH"')  # already there: untouched
        rc.add("rust", '. "$HOME/.cargo/env"')
        text = rc_path.read_text()
        self.assertEqual(text, before, "existing lines are left alone (no rewrite, no reordering)")
        self.assertIn("alias ll='ls -l'", text)
        self.assertEqual(text.count(cm.RC_BEGIN), 1)
        self.assertEqual(text.count("# config-me:go"), 1)
        rc.remove("go")
        rc.remove("rust")
        text = rc_path.read_text()
        self.assertNotIn(cm.RC_BEGIN, text, "empty block is removed entirely")
        self.assertIn("alias ll='ls -l'", text)

    def test_user_edits_to_a_line_are_kept(self):
        rc_path = Path(self.home.name) / ".bashrc"
        rc = cm.ShellRc(cm.UI(mute=True))
        rc.add("go", 'export PATH="/usr/local/go/bin:$PATH"')
        edited = rc_path.read_text().replace('export PATH="/usr/local/go/bin', 'PATH="/usr/local/go/bin')
        rc_path.write_text(edited)
        rc.add("go", 'export PATH="/usr/local/go/bin:$PATH"')
        self.assertEqual(rc_path.read_text(), edited)

    def test_zshrc_only_if_present(self):
        rc = cm.ShellRc(cm.UI(mute=True))
        rc.add("x", "true")
        self.assertFalse((Path(self.home.name) / ".zshrc").exists())
        (Path(self.home.name) / ".zshrc").write_text("")
        rc.add("y", "true")
        self.assertIn("# config-me:y", (Path(self.home.name) / ".zshrc").read_text())


class Targets(unittest.TestCase):
    def test_sections_aliases_and_tools(self):
        ids = lambda names: [i.id for i in cm.resolve_targets(names)]  # noqa: E731
        self.assertEqual(ids(["ai"]), ["claude", "codex", "copilot", "gemini"])
        self.assertEqual(ids(["images"]), ["docker", "podman", "containerd"])
        self.assertEqual(ids(["lang"]), ["node", "dotnet", "java", "go", "python", "rust"])
        self.assertEqual(ids(["node", "c#"]), ["node", "dotnet"])
        self.assertEqual(len(ids([])), len(cm.ITEMS))
        with self.assertRaises(SystemExit):
            cm.resolve_targets(["cobol"])


class Flags(unittest.TestCase):
    def test_single_dash_long_flags(self):
        p = cm.build_parser()
        a = p.parse_args(["-blang", "-mute"])
        self.assertTrue(a.blang and a.mute)
        self.assertEqual(p.parse_args(["-rm"]).rm, [])
        self.assertEqual(p.parse_args(["-rm", "ai", "node"]).rm, ["ai", "node"])
        self.assertIsNone(p.parse_args([]).rm)
        self.assertTrue(p.parse_args(["-stat"]).stat)
        self.assertTrue(p.parse_args(["-y"]).yes)
        self.assertTrue(p.parse_args(["--yes"]).yes)


class Apt(Base):
    def test_update_skipped_when_lists_are_fresh(self):
        ctx = self.ctx(dry_run=True)
        with mock.patch.object(ctx.apt, "lists_age", return_value=60), mock.patch.object(ctx.run, "run") as run:
            ctx.apt.update()
            run.assert_not_called()
        self.assertTrue(ctx.apt.fresh)

    def test_update_runs_once_when_stale_and_again_after_repo_change(self):
        ctx = self.ctx(dry_run=True)
        with mock.patch.object(ctx.apt, "lists_age", return_value=10**9), \
             mock.patch.object(ctx.run, "run", return_value=(0, "")) as run:
            ctx.apt.update()
            ctx.apt.update()
            self.assertEqual(sum("update" in c.args[0] for c in run.call_args_list), 1)
            ctx.apt.update(force=True)
            self.assertEqual(sum("update" in c.args[0] for c in run.call_args_list), 2)


class Prompts(unittest.TestCase):
    def test_plain_checklist(self):
        ui = cm.UI(mute=False)
        p = cm.Prompt(ui)
        p.interactive = False
        opts = [("a", "A"), ("b", "B"), ("c", "C")]
        with mock.patch("builtins.input", return_value="1, 3"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(p.checklist("t", opts), ["a", "c"])
        with mock.patch("builtins.input", return_value="2 3"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(p.checklist("t", opts, radio=True), ["b"], "radio keeps only one")
        with mock.patch("builtins.input", return_value=""), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(p.checklist("t", opts, radio=True), [], "Enter skips the radio")

    def test_assume_yes_only_answers_confirmations(self):
        p = cm.Prompt(cm.UI(mute=True), assume_yes=True)
        p.interactive = False
        with contextlib.redirect_stdout(io.StringIO()), \
             mock.patch("builtins.input", side_effect=["2", "3.12"]) as inp:
            self.assertTrue(p.confirm("Proceed?", default=False), "-y answers yes/no confirmations")
            self.assertEqual(p.checklist("t", [("a", "A"), ("b", "B")]), ["b"], "choices are still asked")
            self.assertEqual(p.line("Which version? ", "y"), "3.12", "versions are still asked")
        self.assertEqual(inp.call_count, 2)

    def test_automatic_answers_everything(self):
        p = cm.Prompt(cm.UI(mute=True), automatic=True)
        with contextlib.redirect_stdout(io.StringIO()), \
             mock.patch("builtins.input", side_effect=AssertionError("asked under -blang")):
            self.assertEqual(p.checklist("t", [("a", "A")], default_if_yes=["a"]), ["a"])
            self.assertTrue(p.confirm("ok?", default=True))
            self.assertEqual(p.line("v? ", "y"), "y")


class ProgressBar(unittest.TestCase):
    def test_mute_hides_logs_but_shows_bar(self):
        ui = cm.UI(mute=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ui.info("noisy log line")
            ui.bar(1, 4, "installing Go")
            ui.end_bar()
        out = buf.getvalue()
        self.assertNotIn("noisy log line", out)
        self.assertIn("25%", out)
        self.assertIn("installing Go", out)


class DryRunEndToEnd(Base):
    def run_main(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), mock.patch.object(cm.Item, "detect", return_value=None), \
             mock.patch.object(cm.Python, "detect", return_value=None):
            code = cm.main(["--dry-run", *argv])
        return code, buf.getvalue()

    def test_blang_installs_every_language_at_lts(self):
        detectors = [mock.patch.object(type(i), "detect", return_value=None) for i in cm.ITEMS.values()]
        for d in detectors:
            d.start()
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = cm.main(["--dry-run", "-blang"])
        finally:
            for d in detectors:
                d.stop()
        out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertIn("node-v24.11.1-linux-", out)
        self.assertIn("dotnet-install.sh --version 10.0.100", out)
        self.assertIn("temurin-25-jdk", out)
        self.assertIn("go1.25.4.linux-", out)
        self.assertIn("python3.14", out)
        self.assertIn("sh.rustup.rs", out)
        self.assertNotIn("docker", out.lower())
        self.assertNotIn("curl -f", out, "every curl must be forced to IPv4 (-4)")
        self.assertIn("curl -4 ", out)
        self.assertNotIn("ForceIPv4", out, "IPv4 forcing applies to config-me's curl calls only")

    def test_stat_runs(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(cm.main(["-stat"]), 0)
        out = buf.getvalue()
        for title in ("Languages", "Container engine", "AI CLI tools", "Version managers"):
            self.assertIn(title, out)


if __name__ == "__main__":
    unittest.main()
