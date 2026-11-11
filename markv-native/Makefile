CXX ?= c++
BUILD ?= build
CPPFLAGS += -Isrc
CXXFLAGS += -std=c++20 -O3 -Wall -Wextra -Werror
SHARED_FLAGS ?= -shared
SHARED_SUFFIX ?= so
DESKTOP_120 ?= 1
CORE = src/video.cpp src/bus.cpp src/m68k.cpp src/machine.cpp src/rom_profile.cpp src/z80.cpp src/ym2612.cpp src/psg.cpp src/scene_sprites.cpp src/interpolation.cpp
HEADERS = $(wildcard src/*.hpp)

.PHONY: all test test-attract libretro
all: $(BUILD)/markv-replay $(BUILD)/markv-run
libretro: $(BUILD)/markv_libretro.$(SHARED_SUFFIX)

$(BUILD):
	mkdir -p "$@"

$(BUILD)/markv-replay: src/video.cpp tools/replay.cpp $(HEADERS) | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) src/video.cpp tools/replay.cpp -o "$@"

$(BUILD)/markv-run: $(CORE) tools/run.cpp $(HEADERS) | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) $(CORE) tools/run.cpp -o "$@"

$(BUILD)/markv_libretro.$(SHARED_SUFFIX): $(CORE) src/libretro.cpp $(HEADERS) Makefile | $(BUILD)
	$(CXX) $(CPPFLAGS) -DMARKV_DESKTOP_120=$(DESKTOP_120) $(CXXFLAGS) $(LDFLAGS) $(SHARED_FLAGS) $(if $(filter dll,$(SHARED_SUFFIX)),,-fPIC) -fvisibility=hidden $(CORE) src/libretro.cpp -o "$@"

$(BUILD)/selftest: $(CORE) tests/selftest.cpp $(HEADERS) | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) $(CORE) tests/selftest.cpp -o "$@"

test: $(BUILD)/selftest
	"$(BUILD)/selftest"

$(BUILD)/sh1-attract: $(CORE) tests/sh1_attract.cpp $(HEADERS) | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(LDFLAGS) $(CORE) tests/sh1_attract.cpp -o "$@"

test-attract: $(BUILD)/sh1-attract
	"$(BUILD)/sh1-attract" "$(ROM)"
