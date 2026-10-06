#!/usr/bin/env python3
"""Exercise two Libretro loads in one process using privately supplied ROMs.

The report contains statuses and stream hashes only. This opt-in script is not
part of unittest discovery and does not write ROMs, screenshots or save states.
"""

import argparse
import array
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

from libretro_regression import Frontend, GameInfo


class ReloadFrontend(Frontend):
    def __init__(self, core, rom):
        self.reset_measurement()
        super().__init__(core, rom, [], enable_input=False)

    def reset_measurement(self):
        self.video_digest = hashlib.sha256()
        self.audio_digest = hashlib.sha256()
        self.video_count = 0
        self.audio_count = 0
        self.last_frame = None

    def video(self, data, width, height, pitch):
        super().video(data, width, height, pitch)
        if self.last_frame is not None:
            packed, width, height = self.last_frame
            self.video_digest.update(struct.pack("<III", self.frame, width, height))
            self.video_digest.update(packed)
            self.video_count += 1

    def audio(self, left, right):
        self.audio_digest.update(struct.pack("<hh", left, right))
        self.audio_count += 1

    def audio_batch(self, data, frames):
        packed = C.string_at(data, frames * 4)
        if sys.byteorder != "little":
            samples = array.array("h", packed)
            samples.byteswap()
            packed = samples.tobytes()
        self.audio_digest.update(packed)
        self.audio_count += frames
        return frames

    def stream_summary(self):
        return {
            "video_frames": self.video_count,
            "video_sha256": self.video_digest.hexdigest(),
            "audio_stereo_frames": self.audio_count,
            "audio_sha256": self.audio_digest.hexdigest(),
        }


def exercise(core_path, roms, lifecycle, frames, report):
    saved_environment = {
        name: os.environ.get(name)
        for name in ("SH_MDP_SAVE_DIR", "MDP_SPRITE_PERSIST")
    }
    try:
        with tempfile.TemporaryDirectory(prefix="shmdp-reload-") as directory:
            directory = Path(directory)
            for name in ("save", "system"):
                (directory / name).mkdir()
            os.environ["SH_MDP_SAVE_DIR"] = str(directory / "save")
            os.environ.pop("MDP_SPRITE_PERSIST", None)
            frontend = ReloadFrontend(core_path, roms[0])
            frontend.system_dir = os.fsencode(directory / "system")
            core = frontend.core
            setters = (
                "retro_set_environment", "retro_set_video_refresh",
                "retro_set_audio_sample", "retro_set_audio_sample_batch",
                "retro_set_input_poll", "retro_set_input_state",
            )
            for setter, callback in zip(setters, frontend._callbacks):
                getattr(core, setter)(callback)
            core.retro_load_game.argtypes = [C.POINTER(GameInfo)]
            core.retro_load_game.restype = C.c_bool
            initialized = False
            loaded = False
            try:
                core.retro_init()
                initialized = True
                for index, rom in enumerate(roms):
                    name = "first" if index == 0 else "second"
                    report[name + "_attempted"] = True
                    blob = rom.read_bytes()
                    content = C.create_string_buffer(blob)
                    info = GameInfo(
                        os.fsencode(rom), C.cast(content, C.c_void_p), len(blob), None
                    )
                    loaded = bool(core.retro_load_game(C.byref(info)))
                    report["loaded_" + name] = loaded
                    run = {
                        "load": name, "loaded": loaded,
                        "rom_sha1": hashlib.sha1(blob).hexdigest(),
                        "frames_completed": 0,
                    }
                    report["runs"].append(run)
                    if not loaded:
                        report["error"] = "retro_load_game returned false on " + name + " load"
                        break
                    frontend.reset_measurement()
                    for frontend.frame in range(1, frames + 1):
                        core.retro_run()
                        run["frames_completed"] += 1
                    run.update(frontend.stream_summary())
                    if not run["video_frames"]:
                        report["error"] = "no video callbacks on " + name + " load"
                        break
                    core.retro_unload_game()
                    loaded = False
                    if index == 0 and lifecycle == "deinit-init":
                        core.retro_deinit()
                        initialized = False
                        core.retro_init()
                        initialized = True
            finally:
                if loaded:
                    core.retro_unload_game()
                if initialized:
                    core.retro_deinit()
    finally:
        for name, value in saved_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--second-rom", type=Path, help="Defaults to --rom.")
    parser.add_argument(
        "--lifecycle", choices=("same-init", "deinit-init"), default="same-init",
        help="Whether to call retro_deinit/init between the two loads.",
    )
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    core = args.core.resolve()
    roms = [args.rom.resolve(), (args.second_rom or args.rom).resolve()]
    for path in (core, *roms):
        if not path.is_file():
            parser.error("file not found: " + str(path))
    if args.output.resolve() in (core, *roms):
        parser.error("--output must not overwrite a core or ROM")
    report = {
        "schema_version": 1,
        "core_sha256": hashlib.sha256(core.read_bytes()).hexdigest(),
        "lifecycle": args.lifecycle,
        "requested_frames_per_load": args.frames,
        "first_attempted": False, "second_attempted": False,
        "loaded_first": False, "loaded_second": False,
        "runs": [], "passed": False,
        "scope": "Two loads of the same library in one process; no UI automation or native M2 reset equivalence is claimed.",
    }
    try:
        exercise(core, roms, args.lifecycle, args.frames, report)
        report["passed"] = (
            report["loaded_first"] and report["loaded_second"]
            and "error" not in report
            and all(run["frames_completed"] == args.frames for run in report["runs"])
        )
        if report["passed"] and report["runs"][0]["rom_sha1"] == report["runs"][1]["rom_sha1"]:
            report["same_rom_stream_comparison"] = {
                kind: report["runs"][0][kind] == report["runs"][1][kind]
                for kind in ("video_sha256", "audio_sha256", "audio_stereo_frames")
            }
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "loaded_first", "loaded_second", "passed"
    )}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
