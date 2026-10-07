#!/usr/bin/env python3
"""Opt-in integration probe for the SH2 explosion option.

Supply private ROMs explicitly. Each run copies them to isolated temporary
directories. Reports contain statuses and hashes, never ROMs, pixels, PCM, or
save-state bytes. This verifies loading, runtime changes, fallback and save/load; visual pose
fidelity and which game objects are eligible require separate game traces.
"""

import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from libretro_regression import Frontend, GameInfo, Variable
from libretro_state_regression import (
    MAX_STATE_BYTES, SH2_SHA1, StateFrontend,
    first_audio_difference, first_video_difference,
)


OPTION = "mame_sh2_enemy_explosions"
DONOR_NAME = "jp_jp_space_harrier.smp"
DONOR_SHA1 = "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72"
MOD_PREFIX = b"SH2EXPL0\x03\x00\x00\x00\x00\x00\x00\x00"


class Message(C.Structure):
    _fields_ = [("msg", C.c_char_p), ("frames", C.c_uint)]


class ExplosionFrontend(StateFrontend):
    def __init__(self, core, rom, style, input_mode, report):
        self.style = style
        self.option_value = style.encode()
        self.option_update_pending = False
        self.auto_save = False
        self.thread_mode_value = b"disabled"
        self.report = report
        super().__init__(core, rom, input_mode)

    def change_style(self, style):
        self.style = style
        self.option_value = style.encode()
        self.option_update_pending = True

    def environment(self, command, data):
        if command == 17:  # GET_VARIABLE_UPDATE, consumed once by retro_run.
            C.cast(data, C.POINTER(C.c_bool))[0] = self.option_update_pending
            if self.option_update_pending:
                self.report["option_update_notifications"] = self.report.get("option_update_notifications", 0) + 1
            self.option_update_pending = False
            return True
        if command == 15:
            variable = C.cast(data, C.POINTER(Variable)).contents
            if variable.key == b"mame_auto_save":
                self.report["auto_save_option_queried"] = True
                variable.value = b"enabled" if self.auto_save else b"disabled"
                return True
            if variable.key == b"mame_thread_mode":
                self.report["thread_mode_option_queried"] = True
                variable.value = self.thread_mode_value
                return True
            if variable.key == OPTION.encode():
                self.report["option_queried"] = True
                self.report["option_query_count"] = self.report.get("option_query_count", 0) + 1
                if self.style != "default":
                    variable.value = self.option_value
                    return True
        if command == 6:
            message = C.cast(data, C.POINTER(Message)).contents
            self.report["messages"].append(
                message.msg.decode(errors="replace") if message.msg else ""
            )
        return super().environment(command, data)

    def input_state(self, port, device, index, control):
        if self.input_mode == "attract" or port != 0 or device != 1:
            return 0
        if self.input_mode == "scripted":
            return Frontend.input_state(self, port, device, index, control)
        if control == 3:
            return int(any(t <= self.frame < t + 8 for t in (700, 1300, 1900, 2500)))
        if self.input_mode == "stage3fire" and control == 7 and self.frame < 2600:
            return int(any(t <= self.frame < t + 3 for t in (2020, 2180)))
        if self.input_mode in ("stage4", "stage4fire") and control == 7 and self.frame < 2600:
            return int(any(t <= self.frame < t + 3 for t in (2020, 2180, 2360)))
        if self.input_mode in ("reference", "stage3fire", "stage4fire") and self.frame >= 2600:
            if control == 0:
                return 1
            return int(control == (4, 7, 5, 6)[((self.frame - 2600) // 90) % 4])
        return 0


class StateBuffer:
    """A frontend-owned fixed allocation with guard bytes outside its capacity."""

    GUARD = b"SHMDPbufferGUARD!" * 2

    def __init__(self, size):
        if not 0 < size <= MAX_STATE_BYTES:
            raise RuntimeError(f"invalid serialization size: {size}")
        self.size = size
        self.storage = C.create_string_buffer(size + 2 * len(self.GUARD))
        self.address = C.addressof(self.storage) + len(self.GUARD)
        self._as_parameter_ = C.c_void_p(self.address)
        self.guard_checks = 0
        C.memmove(C.addressof(self.storage), self.GUARD, len(self.GUARD))
        C.memmove(self.address + size, self.GUARD, len(self.GUARD))

    def check_guards(self):
        if (C.string_at(C.addressof(self.storage), len(self.GUARD)) != self.GUARD
                or C.string_at(self.address + self.size, len(self.GUARD)) != self.GUARD):
            raise RuntimeError("core wrote outside the frontend's cached state capacity")
        self.guard_checks += 1

    @property
    def raw(self):
        self.check_guards()
        return C.string_at(self.address, self.size)


def snapshot(core, state=None):
    size = int(core.retro_serialize_size())
    if not 0 < size <= MAX_STATE_BYTES:
        raise RuntimeError(f"invalid serialization size: {size}")
    if state is None:
        state = StateBuffer(size)
    elif size != state.size:
        raise RuntimeError(f"serialization size changed from cached {state.size} to {size}")
    state.check_guards()
    # Poison the writable capacity so zero padding must be written by the core.
    C.memset(state.address, 0xA5, size)
    if not core.retro_serialize(state, size) or not any(state.raw):
        raise RuntimeError("serialization failed or produced an empty state")
    state.check_guards()
    return state, size


def native_state_files(save_directory):
    return {
        path.relative_to(save_directory).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(save_directory.rglob("*.sta"))
    }


def compact_stream(capture):
    return {
        key: value for key, value in capture.summary().items()
        if key != "video_frame_hashes"
    }


def unchanged_update_roundtrip(frontend, count, style=None, state_buffer=None):
    """The same option value must continue the game, including donor fallback."""
    state, size = snapshot(frontend.core, state_buffer)
    saved_frame, saved_last, saved_seen = frontend.frame, frontend.last_frame, frontend.frames_seen
    normal = frontend.run_window(saved_frame + 1, count)
    if not frontend.core.retro_unserialize(state, size):
        raise RuntimeError("runtime test could not restore its same-mode state")
    state.check_guards()
    frontend.frame, frontend.last_frame, frontend.frames_seen = saved_frame, saved_last, saved_seen
    message_count = len(frontend.report["messages"])
    # A frontend also sets GET_VARIABLE_UPDATE when some unrelated option changes.
    frontend.change_style(frontend.style if style is None else style)
    notified = frontend.run_window(saved_frame + 1, count)
    result = {
        "frames": count,
        "requested_style": frontend.style,
        "video_difference": first_video_difference(normal, notified),
        "audio_difference": first_audio_difference(normal, notified),
        "new_messages": frontend.report["messages"][message_count:],
        "normal": compact_stream(normal), "notified": compact_stream(notified),
    }
    result["passed"] = (
        len(normal.video) == count and len(notified.video) == count
        and bool(normal.audio) and bool(notified.audio)
        and result["video_difference"] is None and result["audio_difference"] is None
        and not result["new_messages"]
    )
    return result


def original_state_envelope(frontend, state, count):
    """The off-mode envelope must retain the legacy native payload unchanged."""
    core = frontend.core
    before = state.raw
    result = {"trailing_zero_bytes": len(MOD_PREFIX), "padding_is_zero": before[-len(MOD_PREFIX):] == bytes(len(MOD_PREFIX))}
    if not result["padding_is_zero"]:
        raise RuntimeError("original SH2 state does not contain the reserved zero padding")
    saved_frame, saved_last, saved_seen = frontend.frame, frontend.last_frame, frontend.frames_seen
    padded_buffer = C.create_string_buffer(before, len(before))
    if not core.retro_unserialize(padded_buffer, len(before)):
        raise RuntimeError("padded original SH2 state was rejected")
    after, _size = snapshot(core, state)
    padded_after = after.raw
    offsets = [i for i, (a, b) in enumerate(zip(before, padded_after)) if a != b]
    result["postload_changed_bytes"] = len(offsets)
    result["postload_first_changed_offsets"] = offsets[:8]
    padded_future = frontend.run_window(saved_frame + 1, count)
    legacy = before[:-len(MOD_PREFIX)]
    legacy_buffer = C.create_string_buffer(legacy, len(legacy))
    result["legacy_original_accepted"] = bool(core.retro_unserialize(legacy_buffer, len(legacy)))
    if not result["legacy_original_accepted"]:
        raise RuntimeError("original SH2 state without the new padding was rejected")
    after, _size = snapshot(core, state)
    result["legacy_postload_matches_padded"] = after.raw == padded_after
    frontend.frame, frontend.last_frame, frontend.frames_seen = saved_frame, saved_last, saved_seen
    legacy_future = frontend.run_window(saved_frame + 1, count)
    result["future_frames"] = count
    result["video_difference"] = first_video_difference(padded_future, legacy_future)
    result["audio_difference"] = first_audio_difference(padded_future, legacy_future)
    result["padded_future"] = compact_stream(padded_future)
    result["legacy_future"] = compact_stream(legacy_future)
    result["passed"] = (result["legacy_postload_matches_padded"]
                        and result["video_difference"] is None and result["audio_difference"] is None
                        and len(padded_future.video) == count and len(legacy_future.video) == count
                        and bool(padded_future.audio) and bool(legacy_future.audio))
    if not result["passed"]:
        raise RuntimeError("legacy original restore differs from the equivalent padded-state restore")
    return result


def runtime_toggle(frontend, args, report, save_directory, startup_reference=None, state_buffer=None):
    """Only retro_run requests restarts; the frontend loads content once."""
    modes = ["original", "sh1", "original"]
    if args.auto_save:
        modes.append("sh1")  # Existing mod autosave must not replace a fresh restart.
    result = {"modes": modes, "frontend_load_calls": 1, "frontend_unload_calls_during_test": 0,
              "state_buffer_allocated_at_load": state_buffer is not None, "phases": []}
    report["runtime_toggle"] = result
    if report["rom_sha1"] == DONOR_SHA1:
        capture = frontend.run_window(1, args.frames)
        state, _size = snapshot(frontend.core, state_buffer)
        if not capture.video or not capture.audio or state.raw.startswith(MOD_PREFIX):
            raise RuntimeError("unexpected SH1 startup state")
        result["scope"] = "SH1 ignores this SH2-only option and must continue without restarting."
        result["initial_stream"] = compact_stream(capture)
        for style in ("sh1", "original"):
            phase = unchanged_update_roundtrip(frontend, args.state_frames, style, state)
            result["phases"].append(phase)
            if not phase["passed"]:
                raise RuntimeError("changing the SH2-only option affected SH1")
        report["passed"] = True
        result["cached_state_capacity"] = state.size
        result["guard_checks_passed"] = state.guard_checks
        return
    reference_by_active = {}
    initial_video = None
    if startup_reference is not None:
        initial_video = [
            (v["width"], v["height"], v["sha256"])
            for v in startup_reference["stream"]["video_frame_hashes"]
        ]
    previous_state = None
    previous_active = None
    for index, style in enumerate(modes):
        before_messages = len(report["messages"])
        queries_before = report.get("option_query_count", 0)
        if index:
            if args.reset_before_toggle:
                frontend.core.retro_reset()
            frontend.change_style(style)
        # Input timing and duplicate-frame cache belong to the frontend, not MAME.
        frontend.last_frame = None
        frontend.frames_seen = 0
        capture = frontend.run_window(1, args.frames)
        if len(capture.video) < args.frames - 2 or not capture.audio:
            raise RuntimeError("runtime option change produced incomplete streams or repeated restarts")
        state, size = snapshot(frontend.core, state_buffer)
        if state_buffer is None:
            state_buffer = state
        state_bytes = state.raw
        result["cached_state_capacity"] = state_buffer.size
        active = state.raw.startswith(MOD_PREFIX)
        expected_active = style == "sh1" and args.donor_kind == "valid"
        phase = {
            "style": style, "expected_active": expected_active, "mod_state_tag": active,
            "serialize_size": size, "stream": compact_stream(capture),
            "initial_state_buffer_reused": state is state_buffer,
            "messages": report["messages"][before_messages:],
            "option_queries": report.get("option_query_count", 0) - queries_before,
            "native_state_files": native_state_files(save_directory),
        }
        result["phases"].append(phase)
        if active != expected_active:
            raise RuntimeError("runtime option change did not apply the requested mode")
        # Check the shared cached capacity at the first ON transition before
        # testing legacy import on return to original mode.
        if not active and index >= 2:
            phase["original_state_envelope"] = original_state_envelope(frontend, state_buffer, args.state_frames)
            state, size = snapshot(frontend.core, state_buffer)
            state_bytes = state.raw
        if index and style == "sh1":
            expected_text = "explosions enabled" if active else "original explosions retained"
            if not any(expected_text in message for message in phase["messages"]):
                raise RuntimeError("runtime option change omitted its activation/fallback notification")
        # First 600 images precede the gameplay effect. Matching them demonstrates
        # a fresh game, rather than simply changing a state tag in the running game.
        video = [(v["width"], v["height"], v["sha256"]) for v in capture.video]
        if initial_video is None:
            initial_video = video
        elif index:
            common = min(600, len(initial_video), len(video))
            phase["fresh_start_prefix_frames"] = common
            phase["fresh_start_prefix_matches"] = initial_video[:common] == video[:common]
            if not phase["fresh_start_prefix_matches"]:
                raise RuntimeError("runtime option change did not restart from the initial screen sequence")
        if args.auto_save and index == 0:
            # MAME may draw "auto.sta not found" on this initial cold load.
            # Internal restarts intentionally skip autoload and its popup.
            phase["initial_autoload_ui_excluded_from_fresh_reference"] = True
        elif active in reference_by_active:
            reference = reference_by_active[active]
            phase["same_mode_fresh_stream"] = {
                "video_difference": first_video_difference(reference, capture),
                "audio_difference": first_audio_difference(reference, capture),
            }
            if any(value is not None for value in phase["same_mode_fresh_stream"].values()):
                raise RuntimeError("returning to a mode differs from its fresh startup; check stale ROM data or autosave loading")
        else:
            reference_by_active[active] = capture
        if startup_reference is not None and index and not active:
            phase["clean_original_stream_matches"] = {
                key: phase["stream"][key] == startup_reference["stream"][key]
                for key in ("video_sha256", "audio_sha256", "audio_stereo_frames")
            }
            if not all(phase["clean_original_stream_matches"].values()):
                raise RuntimeError("original-mode restart differs from a clean startup without autosave")
        if previous_state is not None and previous_active != active:
            foreign, foreign_size = previous_state
            accepted = bool(frontend.core.retro_unserialize(foreign, foreign_size))
            after, after_size = snapshot(frontend.core, state_buffer)
            phase["foreign_state_rejected"] = not accepted
            phase["state_unchanged_after_rejection"] = after_size == size and after.raw == state_bytes
            if accepted or not phase["state_unchanged_after_rejection"]:
                raise RuntimeError("state from the previous mode was accepted or changed the restarted machine")
        phase["unchanged_update"] = unchanged_update_roundtrip(frontend, args.state_frames, state_buffer=state_buffer)
        if not phase["unchanged_update"]["passed"]:
            raise RuntimeError("unchanged option update restarted or otherwise changed the game")
        state, size = snapshot(frontend.core, state_buffer)
        # The foreign-mode rejection check needs an immutable prior-state copy;
        # all current-mode saves and restores keep the initial guarded buffer.
        previous_state, previous_active = (C.create_string_buffer(state.raw, size), size), active
    if args.auto_save and args.donor_kind == "valid":
        first_switch, second_switch, third_switch = [phase["native_state_files"] for phase in result["phases"][1:4]]
        original_paths = set(first_switch)
        mod_paths = set(second_switch) - original_paths
        result["autosave_checks"] = {
            "original_file_exists_before_return": len(original_paths) == 1,
            "separate_mod_file_exists_before_return": len(mod_paths) == 1 and all("/sh2-sh1-explosions-v3/" in path for path in mod_paths),
            "original_file_unchanged_while_mod_runs": all(first_switch[path] == second_switch.get(path) for path in original_paths),
            "mod_file_unchanged_while_original_runs": all(second_switch[path] == third_switch.get(path) for path in mod_paths),
            "exactly_two_state_paths": len(third_switch) == 2,
        }
        if not all(result["autosave_checks"].values()):
            raise RuntimeError("native autosave files were missing, shared, or modified by the other mode")
    result["guard_checks_passed"] = state_buffer.guard_checks
    result["state_size_constant"] = all(p["serialize_size"] == state_buffer.size for p in result["phases"])
    report["passed"] = True


def exercise(args, report):
    saved_environment = {
        key: os.environ.get(key) for key in ("SH_MDP_SAVE_DIR", "MDP_SPRITE_PERSIST")
    }
    try:
        with tempfile.TemporaryDirectory(prefix="shmdp-explosion-") as directory:
            directory = Path(directory)
            cart, system, save = (directory / name for name in ("cart", "system", "save"))
            for path in (cart, system, save):
                path.mkdir()
            rom = cart / args.rom.name
            shutil.copyfile(args.rom, rom)
            report["rom_sha1"] = hashlib.sha1(rom.read_bytes()).hexdigest()
            if args.donor_kind != "missing":
                destination = (cart if args.donor_location == "cart" else system) / DONOR_NAME
                if destination == rom:
                    raise RuntimeError("choose system donor location when testing SH1 itself")
                shutil.copyfile(args.donor, destination)
                if args.donor_kind == "wrong-sha1":
                    with destination.open("r+b") as stream:
                        stream.seek(-1, 2)
                        value = stream.read(1)
                        stream.seek(-1, 2)
                        stream.write(bytes([value[0] ^ 1]))
                report["donor_size"] = destination.stat().st_size
                report["donor_sha1"] = hashlib.sha1(destination.read_bytes()).hexdigest()
            expected_active = (
                args.style == "sh1" and report["rom_sha1"] == SH2_SHA1
                and args.donor_kind == "valid"
            )
            report["expected_active"] = expected_active
            os.environ["SH_MDP_SAVE_DIR"] = str(save)
            os.environ.pop("MDP_SPRITE_PERSIST", None)
            startup_reference = None
            if args.runtime_toggle and args.auto_save and report["rom_sha1"] == SH2_SHA1:
                reference_path = directory / "clean-startup.json"
                command = [
                    sys.executable, str(Path(__file__).resolve()),
                    "--core", str(args.core), "--rom", str(args.rom),
                    "--style", "original", "--donor-kind", "missing",
                    "--input", args.input, "--frames", str(args.frames),
                    "--state-frames", "0", "--thread-mode", args.thread_mode,
                    "--output", str(reference_path),
                ]
                completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if completed.returncode or not reference_path.is_file():
                    raise RuntimeError(f"clean startup reference process failed ({completed.returncode})")
                startup_reference = json.loads(reference_path.read_text())
                if not startup_reference["passed"]:
                    raise RuntimeError("clean startup reference did not pass")
                report["clean_startup_reference"] = {
                    "core_sha256": startup_reference["core_sha256"],
                    "thread_mode": startup_reference["thread_mode"],
                    "auto_save": False,
                    "stream": {key: value for key, value in startup_reference["stream"].items() if key != "video_frame_hashes"},
                }
            frontend = ExplosionFrontend(args.core, rom, args.style, args.input, report)
            frontend.auto_save = args.auto_save
            frontend.thread_mode_value = args.thread_mode.encode()
            if args.runtime_toggle:
                frontend.style = "original"
                frontend.option_value = b"original"
            frontend.system_dir = os.fsencode(system)
            frontend.save_dir = os.fsencode(save)
            core = frontend.core
            setters = (
                "retro_set_environment", "retro_set_video_refresh", "retro_set_audio_sample",
                "retro_set_audio_sample_batch", "retro_set_input_poll", "retro_set_input_state",
            )
            for setter, callback in zip(setters, frontend._callbacks):
                getattr(core, setter)(callback)
            core.retro_load_game.argtypes = [C.POINTER(GameInfo)]
            core.retro_load_game.restype = C.c_bool
            core.retro_serialize_size.restype = C.c_size_t
            for name in ("retro_serialize", "retro_unserialize"):
                getattr(core, name).argtypes = [C.c_void_p, C.c_size_t]
                getattr(core, name).restype = C.c_bool
            core.retro_init()
            loaded = False
            try:
                blob = rom.read_bytes()
                content = C.create_string_buffer(blob)
                info = GameInfo(os.fsencode(rom), C.cast(content, C.c_void_p), len(blob), None)
                loaded = bool(core.retro_load_game(C.byref(info)))
                report["loaded"] = loaded
                if not loaded:
                    raise RuntimeError("retro_load_game returned false")
                if args.runtime_toggle:
                    initial_size = int(core.retro_serialize_size())
                    report["serialize_size_at_load"] = initial_size
                    initial_buffer = StateBuffer(initial_size) if initial_size else None
                    runtime_toggle(frontend, args, report, save, startup_reference, initial_buffer)
                    return
                stream = frontend.run_window(1, args.frames)
                report["stream"] = stream.summary()
                if not stream.video or not stream.audio:
                    raise RuntimeError("missing video or audio during warmup")
                state, size = snapshot(core)
                report["serialize_size"] = size
                report["mod_state_prefix"] = state.raw.startswith(MOD_PREFIX)
                if report["mod_state_prefix"] != expected_active:
                    raise RuntimeError("state tag does not match expected option/donor result")
                if args.style != "default" and not report["option_queried"]:
                    raise RuntimeError("core never queried the requested option")
                if expected_active and not any("SH1" in message and "explosions enabled" in message for message in report["messages"]):
                    raise RuntimeError("missing activation notification")
                if args.style == "sh1" and report["rom_sha1"] == SH2_SHA1 and not expected_active:
                    if not any("original explosions retained" in text for text in report["messages"]):
                        raise RuntimeError("missing fallback notification")
                if args.state_frames:
                    saved_frame, saved_last, saved_seen = frontend.frame, frontend.last_frame, frontend.frames_seen
                    first = frontend.run_window(saved_frame + 1, args.state_frames)
                    report["unserialize_return"] = bool(core.retro_unserialize(state, size))
                    if not report["unserialize_return"]:
                        raise RuntimeError("same-mode unserialize returned false")
                    frontend.frame, frontend.last_frame, frontend.frames_seen = saved_frame, saved_last, saved_seen
                    replay = frontend.run_window(saved_frame + 1, args.state_frames)
                    report["state"] = {
                        "frames": args.state_frames,
                        "first": first.summary(), "replay": replay.summary(),
                        "video_difference": first_video_difference(first, replay),
                        "audio_difference": first_audio_difference(first, replay),
                    }
                    if len(first.video) != args.state_frames or len(replay.video) != args.state_frames or not first.audio or not replay.audio:
                        raise RuntimeError("incomplete save/load comparison streams")
                    report["state"]["passed"] = (
                        report["state"]["video_difference"] is None
                        and report["state"]["audio_difference"] is None
                    )
                    if not report["state"]["passed"]:
                        raise RuntimeError("save/load changed video or PCM")
                if args.baseline:
                    baseline = json.loads(args.baseline.read_text())
                    if any(baseline.get(key) != report[key] for key in ("frames", "input", "rom_sha1")):
                        raise RuntimeError("baseline uses different game, inputs or frame count")
                    report["baseline_equal"] = {
                        key: baseline["stream"][key] == report["stream"][key]
                        for key in ("video_sha256", "audio_sha256", "audio_stereo_frames")
                    }
                    if not all(report["baseline_equal"].values()):
                        raise RuntimeError("video or PCM differs from the supplied baseline")
                report["passed"] = True
            finally:
                if loaded:
                    core.retro_unload_game()
                core.retro_deinit()
    finally:
        for key, value in saved_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--style", choices=("default", "original", "sh1"), default="default")
    parser.add_argument("--donor", type=Path)
    parser.add_argument("--donor-kind", choices=("valid", "missing", "wrong-sha1"), default="missing")
    parser.add_argument("--donor-location", choices=("cart", "system"), default="system")
    parser.add_argument("--input", choices=("attract", "scripted", "reference", "stage3fire", "stage4", "stage4fire"), default="attract")
    parser.add_argument("--frames", type=int, default=2400)
    parser.add_argument("--state-frames", type=int, default=120)
    parser.add_argument("--runtime-toggle", action="store_true", help="Change original/sh1/original via GET_VARIABLE_UPDATE without frontend unload/load.")
    parser.add_argument("--auto-save", action="store_true", help="Enable native MAME autosave in the isolated save directory; runtime mode also switches back to sh1.")
    parser.add_argument("--thread-mode", choices=("disabled", "enabled"), default="disabled", help="Exercise the MAME worker queues used by the live threaded core.")
    parser.add_argument("--reset-before-toggle", action="store_true", help="Queue retro_reset immediately before each runtime option change.")
    parser.add_argument("--baseline", type=Path, help="Require identical warmup video/PCM to this probe's earlier report.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 1 or args.state_frames < 0:
        parser.error("--frames must be positive and --state-frames nonnegative")
    if args.runtime_toggle and (args.frames < 600 or args.state_frames < 1 or args.style not in ("default", "original") or args.baseline):
        parser.error("--runtime-toggle requires at least 600 frames, a positive state window, original/default initial style, and no external baseline")
    if args.reset_before_toggle and not args.runtime_toggle:
        parser.error("--reset-before-toggle requires --runtime-toggle")
    if args.donor_kind != "missing" and args.donor is None:
        parser.error("--donor is required for a valid or wrong-sha1 donor case")
    inputs = [args.core, args.rom] + [p for p in (args.donor, args.baseline) if p is not None]
    if any(not path.is_file() for path in inputs):
        parser.error("all input paths must be existing files")
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("--output must not overwrite an input")
    if args.donor_kind != "missing":
        if args.donor.stat().st_size != 0x3E0000 or hashlib.sha1(args.donor.read_bytes()).hexdigest() != DONOR_SHA1:
            parser.error("supply the supported original SH1 donor; the wrong-sha1 case corrupts only its temporary copy")
    args.core, args.rom = args.core.resolve(), args.rom.resolve()
    if args.runtime_toggle and hashlib.sha1(args.rom.read_bytes()).hexdigest() not in (SH2_SHA1, DONOR_SHA1):
        parser.error("--runtime-toggle targets the supported SH2 ROM or verifies the SH1 no-op")
    report = {
        "schema_version": 1, "passed": False, "loaded": False,
        "core_sha256": hashlib.sha256(args.core.read_bytes()).hexdigest(),
        "style": args.style, "donor_kind": args.donor_kind,
        "donor_location": args.donor_location, "input": args.input,
        "frames": args.frames, "messages": [], "option_queried": False,
        "auto_save": args.auto_save,
        "thread_mode": args.thread_mode,
        "reset_before_toggle": args.reset_before_toggle,
        "scope": "One frontend content load, optional internal restarts via GET_VARIABLE_UPDATE, option/donor result, stream hashes and same-mode save/load. No pose or native-timing equivalence is inferred.",
    }
    try:
        exercise(args, report)
    except Exception as error:
        report["passed"] = False
        report["error"] = type(error).__name__ + ": " + str(error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("loaded", "passed")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
