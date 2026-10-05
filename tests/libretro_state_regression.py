#!/usr/bin/env python3
"""Verify deterministic Libretro save/load with a locally supplied game ROM.

The JSON report contains hashes and diagnostics only, never ROM bytes, audio,
video pixels, or save-state contents. Each invocation uses isolated directories.
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

from libretro_regression import Frontend, GameInfo, SystemInfo


SH2_SHA1 = "80f576af01d6413c0b92073e2f947b0431f12a74"
MAX_STATE_BYTES = 128 * 1024 * 1024


class Capture:
    def __init__(self):
        self.video_hash = hashlib.sha256()
        self.audio_hash = hashlib.sha256()
        self.video = []
        self.audio = bytearray()

    def add_video(self, frame, packed, width, height):
        self.video_hash.update(struct.pack("<III", frame, width, height))
        self.video_hash.update(packed)
        self.video.append({
            "frame": frame, "width": width, "height": height,
            "sha256": hashlib.sha256(packed).hexdigest(),
        })

    def add_audio(self, packed):
        self.audio_hash.update(packed)
        self.audio.extend(packed)

    def summary(self):
        return {
            "video_sha256": self.video_hash.hexdigest(),
            "audio_sha256": self.audio_hash.hexdigest(),
            "video_frames": len(self.video),
            "audio_stereo_frames": len(self.audio) // 4,
            "video_frame_hashes": self.video,
        }


class StateFrontend(Frontend):
    def __init__(self, core, rom, input_mode):
        self.input_mode = input_mode
        self.capture = None
        self.record_uninterrupted = True
        self.uninterrupted_audio_hash = hashlib.sha256()
        self.uninterrupted_audio_frames = 0
        super().__init__(core, rom, [], enable_input=True)

    def input_state(self, port, device, index, control):
        if self.input_mode == "scripted":
            return super().input_state(port, device, index, control)
        if port != 0 or device != 1:
            return 0
        if control == 3:  # Start: title, menu, selector, stage confirmation.
            return int(any(t <= self.frame < t + 8 for t in (700, 1300, 1900, 2500)))
        if control == 7:  # Three Right presses select SH2 stage 4.
            return int(any(t <= self.frame < t + 3 for t in (2020, 2180, 2360)))
        return 0

    def video(self, data, width, height, pitch):
        super().video(data, width, height, pitch)
        if self.capture is not None and self.last_frame is not None:
            packed, width, height = self.last_frame
            self.capture.add_video(self.frame, packed, width, height)

    def receive_audio(self, packed):
        if self.record_uninterrupted:
            self.uninterrupted_audio_hash.update(packed)
            self.uninterrupted_audio_frames += len(packed) // 4
        if self.capture is not None:
            self.capture.add_audio(packed)

    def audio(self, left, right):
        self.receive_audio(struct.pack("<hh", left, right))

    def audio_batch(self, data, frames):
        packed = C.string_at(data, frames * 4)
        if sys.byteorder != "little":
            samples = array.array("h", packed)
            samples.byteswap()
            packed = samples.tobytes()
        self.receive_audio(packed)
        return frames

    def run_window(self, first_frame, count):
        result = Capture()
        self.capture = result
        try:
            for self.frame in range(first_frame, first_frame + count):
                self.core.retro_run()
        finally:
            self.capture = None
        return result


def first_video_difference(first, replay):
    for left, right in zip(first.video, replay.video):
        if left != right:
            return {"first": left, "replay": right}
    if len(first.video) != len(replay.video):
        index = min(len(first.video), len(replay.video))
        return {
            "first": first.video[index] if index < len(first.video) else None,
            "replay": replay.video[index] if index < len(replay.video) else None,
        }
    return None


def first_audio_difference(first, replay):
    # The offset is within the replay window, not within the whole emulation.
    for offset, (left, right) in enumerate(zip(first.audio, replay.audio)):
        if left != right:
            sample_offset = offset // 2 * 2
            return {
                "stereo_frame": offset // 4,
                "channel": (offset // 2) % 2,
                "first_sample": struct.unpack_from("<h", first.audio, sample_offset)[0],
                "replay_sample": struct.unpack_from("<h", replay.audio, sample_offset)[0],
            }
    if len(first.audio) != len(replay.audio):
        return {
            "stereo_frame": min(len(first.audio), len(replay.audio)) // 4,
            "reason": "different stream lengths",
        }
    return None


def roundtrip(frontend, warmup, frames, report):
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
    core.retro_serialize_size.argtypes = []
    core.retro_serialize_size.restype = C.c_size_t
    core.retro_serialize.argtypes = [C.c_void_p, C.c_size_t]
    core.retro_serialize.restype = C.c_bool
    core.retro_unserialize.argtypes = [C.c_void_p, C.c_size_t]
    core.retro_unserialize.restype = C.c_bool

    loaded = False
    core.retro_init()
    try:
        info = SystemInfo()
        core.retro_get_system_info(C.byref(info))
        blob = frontend.rom.read_bytes()
        content = C.create_string_buffer(blob)
        game = GameInfo(os.fsencode(frontend.rom), C.cast(content, C.c_void_p), len(blob), None)
        loaded = bool(core.retro_load_game(C.byref(game)))
        if not loaded:
            raise RuntimeError("retro_load_game returned false")
        for frontend.frame in range(1, warmup + 1):
            core.retro_run()
        if frontend.last_frame is None:
            raise RuntimeError("no video received during warmup")

        size = int(core.retro_serialize_size())
        report["serialize_size"] = size
        if not 0 < size <= MAX_STATE_BYTES:
            raise RuntimeError(f"invalid serialization size: {size}")
        state = C.create_string_buffer(size)
        report["serialize_return"] = bool(core.retro_serialize(state, size))
        if not report["serialize_return"]:
            raise RuntimeError("retro_serialize returned false")
        if not any(state.raw):
            raise RuntimeError("retro_serialize produced an all-zero buffer")

        saved_frame = frontend.frame
        saved_last_frame = frontend.last_frame
        saved_frames_seen = frontend.frames_seen
        first = frontend.run_window(saved_frame + 1, frames)
        report["uninterrupted_audio_sha256"] = frontend.uninterrupted_audio_hash.hexdigest()
        report["uninterrupted_audio_stereo_frames"] = frontend.uninterrupted_audio_frames
        frontend.record_uninterrupted = False

        report["unserialize_return"] = bool(core.retro_unserialize(state, size))
        if not report["unserialize_return"]:
            raise RuntimeError("retro_unserialize returned false")
        restored_size = int(core.retro_serialize_size())
        report["serialize_size_after_restore"] = restored_size
        if restored_size != size:
            raise RuntimeError("serialization size changed after restore")
        # Rewind host input timing and its cache used for duplicate video frames.
        frontend.frame = saved_frame
        frontend.last_frame = saved_last_frame
        frontend.frames_seen = saved_frames_seen
        replay = frontend.run_window(saved_frame + 1, frames)
        report["first"] = first.summary()
        report["replay"] = replay.summary()
        report["first_video_difference"] = first_video_difference(first, replay)
        report["first_audio_difference"] = first_audio_difference(first, replay)
        if len(first.video) != frames or len(replay.video) != frames:
            raise RuntimeError("missing video callbacks in a comparison window")
        if not first.audio or not replay.audio:
            raise RuntimeError("no audio samples in a comparison window")
        report["video_identical"] = report["first_video_difference"] is None
        report["audio_identical"] = report["first_audio_difference"] is None
        report["passed"] = report["video_identical"] and report["audio_identical"]
    finally:
        if loaded:
            core.retro_unload_game()
        core.retro_deinit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--warmup", type=int, help="default: SH2 stage 4 at 3000, otherwise 1200")
    parser.add_argument("--frames", type=int, default=180, help="frames to compare after saving")
    parser.add_argument("--input", choices=("auto", "scripted", "sh2-stage4"), default="auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.frames <= 0 or (args.warmup is not None and args.warmup <= 0):
        parser.error("--frames and --warmup must be positive")

    report = {"schema_version": 1, "passed": False}
    try:
        rom_sha1 = hashlib.sha1(args.rom.read_bytes()).hexdigest()
        input_mode = args.input
        if input_mode == "auto":
            input_mode = "sh2-stage4" if rom_sha1 == SH2_SHA1 else "scripted"
        warmup = args.warmup or (3000 if input_mode == "sh2-stage4" else 1200)
        report.update({
            "core_sha256": hashlib.sha256(args.core.read_bytes()).hexdigest(),
            "rom_sha1": rom_sha1, "input": input_mode,
            "warmup": warmup, "frames": args.frames,
        })
        with tempfile.TemporaryDirectory(prefix="shmdp-state-") as temporary:
            directory = Path(temporary)
            (directory / "system").mkdir()
            (directory / "save").mkdir()
            frontend = StateFrontend(args.core, args.rom, input_mode)
            frontend.system_dir = os.fsencode(directory / "system")
            frontend.save_dir = os.fsencode(directory / "save")
            # Environment changes stay within this standalone test process.
            os.environ.pop("MDP_SPRITE_PERSIST", None)
            roundtrip(frontend, warmup, args.frames, report)
    except Exception as error:
        report["error"] = str(error)
    document = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(document, encoding="utf-8")
    print(document, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
