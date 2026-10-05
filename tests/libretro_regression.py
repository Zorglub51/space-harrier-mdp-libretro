#!/usr/bin/env python3
"""Small deterministic Libretro frontend used by CI for private-ROM regression."""

import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class SystemInfo(C.Structure):
    _fields_ = [
        ("library_name", C.c_char_p), ("library_version", C.c_char_p),
        ("valid_extensions", C.c_char_p), ("need_fullpath", C.c_bool),
        ("block_extract", C.c_bool),
    ]


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_BATCH = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
INPUT_POLL = C.CFUNCTYPE(None)
INPUT_STATE = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class Frontend:
    def __init__(self, core: Path, rom: Path, checkpoints: list[int], enable_input: bool = True):
        self.core = C.CDLL(str(core.resolve()))
        self.rom = rom.resolve()
        self.checkpoints = set(checkpoints)
        self.enable_input = enable_input
        self.frame = 0
        self.pixel_format = 0
        self.last_frame = None
        self.results = {}
        self.frames_seen = 0
        self.system_dir = os.fsencode(str(core.resolve().parent))
        self.save_dir = os.fsencode(str(Path(os.environ.get("SH_MDP_SAVE_DIR", "/tmp")).resolve()))
        self._callbacks = [ENV(self.environment), VIDEO(self.video), AUDIO(self.audio),
                           AUDIO_BATCH(self.audio_batch), INPUT_POLL(self.input_poll),
                           INPUT_STATE(self.input_state)]

    def environment(self, command, data):
        if command == 3:  # GET_CAN_DUPE
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        if command == 9:  # GET_SYSTEM_DIRECTORY
            C.cast(data, C.POINTER(C.c_char_p))[0] = self.system_dir
            return True
        if command == 10:  # SET_PIXEL_FORMAT
            value = C.cast(data, C.POINTER(C.c_int))[0]
            if value in (0, 1, 2):
                self.pixel_format = value
                return True
            return False
        if command in (30, 31):  # GET_CONTENT_DIRECTORY / GET_SAVE_DIRECTORY
            value = self.system_dir if command == 30 else self.save_dir
            C.cast(data, C.POINTER(C.c_char_p))[0] = value
            return True
        if command == 15:  # GET_VARIABLE: defaults are selected by the core
            variable = C.cast(data, C.POINTER(Variable)).contents
            variable.value = None
            return False
        if command == 17:  # GET_VARIABLE_UPDATE
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if command in (1, 6, 8, 11, 16, 18, 21, 22, 24, 32, 35, 36, 37, 44):
            return True
        return False

    def video(self, data, width, height, pitch):
        if data:
            bpp = 4 if self.pixel_format == 1 else 2
            row_size = width * bpp
            raw = C.string_at(data, pitch * height)
            packed = b"".join(raw[y * pitch:y * pitch + row_size] for y in range(height))
            self.last_frame = (packed, width, height)
            self.frames_seen += 1
        if self.frame in self.checkpoints and self.last_frame:
            packed, width, height = self.last_frame
            nonzero = sum(byte != 0 for byte in packed)
            self.results[str(self.frame)] = {
                "sha256": hashlib.sha256(packed).hexdigest(),
                "width": width,
                "height": height,
                "nonzero_bytes": nonzero,
            }

    @staticmethod
    def audio(_left, _right):
        return None

    @staticmethod
    def audio_batch(_data, frames):
        return frames

    @staticmethod
    def input_poll():
        return None

    def input_state(self, port, device, _index, control):
        if not self.enable_input or port != 0 or device != 1:
            return 0
        if control == 3:  # Start
            return int((self.frame % 180) < 6)
        if control == 0:  # B / fire
            return int(self.frame > 300 and (self.frame % 4) < 2)
        phase = (self.frame // 180) % 4
        return int(control in (4, 7, 5, 6) and (4, 7, 5, 6).index(control) == phase)

    def run(self, frames: int):
        env, video, audio, audio_batch, poll, state = self._callbacks
        self.core.retro_set_environment(env)
        self.core.retro_set_video_refresh(video)
        self.core.retro_set_audio_sample(audio)
        self.core.retro_set_audio_sample_batch(audio_batch)
        self.core.retro_set_input_poll(poll)
        self.core.retro_set_input_state(state)
        self.core.retro_init()
        info = SystemInfo()
        self.core.retro_get_system_info(C.byref(info))
        blob = self.rom.read_bytes()
        buffer = C.create_string_buffer(blob)
        game = GameInfo(os.fsencode(str(self.rom)), C.cast(buffer, C.c_void_p), len(blob), None)
        self.core.retro_load_game.argtypes = [C.POINTER(GameInfo)]
        self.core.retro_load_game.restype = C.c_bool
        if not self.core.retro_load_game(C.byref(game)):
            raise RuntimeError(f"core rejected {self.rom.name}")
        try:
            for self.frame in range(1, frames + 1):
                self.core.retro_run()
        finally:
            self.core.retro_unload_game()
            self.core.retro_deinit()
        missing = sorted(self.checkpoints - {int(key) for key in self.results})
        if missing:
            raise RuntimeError(f"no video frame at checkpoints: {missing}")
        if self.frames_seen < frames // 2:
            raise RuntimeError(f"only {self.frames_seen} video frames for {frames} runs")
        hashes = {entry["sha256"] for entry in self.results.values()}
        if len(hashes) < min(3, len(self.checkpoints)):
            raise RuntimeError(f"only {len(hashes)} distinct checkpoint frames")
        for checkpoint, entry in self.results.items():
            pixels = entry["width"] * entry["height"]
            if entry["width"] < 256 or entry["height"] < 224:
                raise RuntimeError(f"invalid video geometry at frame {checkpoint}: {entry}")
            if entry["nonzero_bytes"] < pixels // 20:
                raise RuntimeError(f"nearly empty video frame at checkpoint {checkpoint}")
        return self.results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=6000)
    parser.add_argument("--checkpoints", default="600,1200,2400,3600,4800,6000")
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--different-from", type=Path,
                        help="fail unless input changes at least one common video checkpoint")
    parser.add_argument("--no-input", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checkpoints = [int(value) for value in args.checkpoints.split(",") if value]
    input_mode = "none" if args.no_input else "scripted"
    result = Frontend(args.core, args.rom, checkpoints, not args.no_input).run(args.frames)
    document = {
        "rom_sha1": hashlib.sha1(args.rom.read_bytes()).hexdigest(),
        "input": input_mode,
        "frames": result,
    }
    if args.output:
        args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.expected:
        expected = json.loads(args.expected.read_text(encoding="utf-8"))
        if document != expected:
            print(json.dumps(document, indent=2, sort_keys=True))
            raise SystemExit("video regression mismatch")
    if args.different_from:
        baseline = json.loads(args.different_from.read_text(encoding="utf-8"))
        common = sorted(set(document["frames"]) & set(baseline.get("frames", {})))
        if not common:
            raise SystemExit("input regression has no checkpoint in common with baseline")
        if all(document["frames"][key]["sha256"] == baseline["frames"][key]["sha256"]
               for key in common):
            raise SystemExit("scripted controls did not change any video checkpoint")
    else:
        print(json.dumps(document, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
