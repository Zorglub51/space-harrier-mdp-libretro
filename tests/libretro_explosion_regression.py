#!/usr/bin/env python3
"""Opt-in integration probe for the SH2 enemy-explosion option.

Supply private ROMs explicitly. Each run copies them to isolated temporary
directories. Reports contain statuses and hashes, never ROMs, pixels, PCM, or
save-state bytes. This verifies loading, fallback and save/load; visual pose
fidelity and which game objects are eligible require separate game traces.
"""

import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import shutil
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
MOD_PREFIX = b"SH2EXPL0\x01\x00\x00\x00\x00\x00\x00\x00"


class Message(C.Structure):
    _fields_ = [("msg", C.c_char_p), ("frames", C.c_uint)]


class ExplosionFrontend(StateFrontend):
    def __init__(self, core, rom, style, input_mode, report):
        self.style = style
        self.option_value = style.encode()
        self.report = report
        super().__init__(core, rom, input_mode)

    def environment(self, command, data):
        if command == 15:
            variable = C.cast(data, C.POINTER(Variable)).contents
            if variable.key == OPTION.encode():
                self.report["option_queried"] = True
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
        if self.input_mode in ("stage4", "stage4fire") and control == 7 and self.frame < 2600:
            return int(any(t <= self.frame < t + 3 for t in (2020, 2180, 2360)))
        if self.input_mode in ("reference", "stage4fire") and self.frame >= 2600:
            if control == 0:
                return 1
            return int(control == (4, 7, 5, 6)[((self.frame - 2600) // 90) % 4])
        return 0


def snapshot(core):
    size = int(core.retro_serialize_size())
    if not 0 < size <= MAX_STATE_BYTES:
        raise RuntimeError(f"invalid serialization size: {size}")
    state = C.create_string_buffer(size)
    if not core.retro_serialize(state, size) or not any(state.raw):
        raise RuntimeError("serialization failed or produced an empty state")
    return state, size


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
            frontend = ExplosionFrontend(args.core, rom, args.style, args.input, report)
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
                if expected_active and "SH2: SH1 enemy explosions enabled." not in report["messages"]:
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
    parser.add_argument("--input", choices=("attract", "scripted", "reference", "stage4", "stage4fire"), default="attract")
    parser.add_argument("--frames", type=int, default=2400)
    parser.add_argument("--state-frames", type=int, default=120)
    parser.add_argument("--baseline", type=Path, help="Require identical warmup video/PCM to this probe's earlier report.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 1 or args.state_frames < 0:
        parser.error("--frames must be positive and --state-frames nonnegative")
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
    report = {
        "schema_version": 1, "passed": False, "loaded": False,
        "core_sha256": hashlib.sha256(args.core.read_bytes()).hexdigest(),
        "style": args.style, "donor_kind": args.donor_kind,
        "donor_location": args.donor_location, "input": args.input,
        "frames": args.frames, "messages": [], "option_queried": False,
        "scope": "Single content load, option/donor result, stream hashes and same-mode save/load. No pose or native-timing equivalence is inferred.",
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
