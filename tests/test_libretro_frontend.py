import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_frontend():
    path = ROOT / "tests" / "libretro_regression.py"
    spec = importlib.util.spec_from_file_location("libretro_regression_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAKE_CORE = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef bool (*env_cb)(unsigned, void *);
typedef void (*video_cb)(const void *, unsigned, unsigned, size_t);
typedef void (*void_cb)(void);
typedef int16_t (*input_cb)(unsigned, unsigned, unsigned, unsigned);
struct game_info { const char *path; const void *data; size_t size; const char *meta; };
struct system_info { const char *name, *version, *extensions; bool fullpath, block_extract; };
static env_cb env; static video_cb video; static unsigned frame;
void retro_set_environment(env_cb cb) { env = cb; }
void retro_set_video_refresh(video_cb cb) { video = cb; }
void retro_set_audio_sample(void *cb) { (void)cb; }
void retro_set_audio_sample_batch(void *cb) { (void)cb; }
void retro_set_input_poll(void_cb cb) { (void)cb; }
void retro_set_input_state(input_cb cb) { (void)cb; }
void retro_init(void) { int format = 1; env(10, &format); }
void retro_deinit(void) {}
void retro_get_system_info(struct system_info *i) { i->name="fake"; i->version="1"; i->extensions="smp"; i->fullpath=false; i->block_extract=false; }
bool retro_load_game(const struct game_info *g) { return g && g->data && g->size; }
void retro_unload_game(void) {}
void retro_run(void) { static uint32_t pixels[320*224]; frame++; for (unsigned i=0;i<320*224;i++) pixels[i]=0xff000000u | (frame*0x010101u) | i; video(pixels,320,224,320*4); }
'''


class FrontendContractTests(unittest.TestCase):
    def test_frontend_captures_distinct_frames(self):
        module = load_frontend()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / "fake.c"
            core = tmp / "fake.so"
            rom = tmp / "fake.smp"
            source.write_text(FAKE_CORE, encoding="utf-8")
            rom.write_bytes(b"fake-rom")
            subprocess.run(["cc", "-shared", "-fPIC", str(source), "-o", str(core)], check=True)
            result = module.Frontend(core, rom, [1, 2, 3]).run(3)
        self.assertEqual(set(result), {"1", "2", "3"})
        self.assertEqual(len({item["sha256"] for item in result.values()}), 3)
        self.assertTrue(all(item["width"] == 320 and item["height"] == 224 for item in result.values()))


if __name__ == "__main__":
    unittest.main()
