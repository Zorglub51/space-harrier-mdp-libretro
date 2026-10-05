#!/usr/bin/env python3
"""Repair the M2 Mega Drive Mini 2 Space Harrier ROMs.

Mechanism (see FINDINGS.md): m2engage replaces hot 68000 blocks with native ARM
handlers, and M2 corrupted the *first opcode word of every hooked block* so the raw
ROM cannot run anywhere else. The rule is exact and verified 12/12:

    hook address  <=>  exactly one corrupted 16-bit word, at that address

`tools/hook.py` lists every hook and disassembles its handler; the handler is the
specification from which the original opcode is reconstructed. Only the opcode word
is corrupted - immediate/displacement extension words are left intact.

Each entry is (offset, corrupt, correct, 68000 mnemonic, how it was confirmed).
"""
import argparse
import hashlib
import struct
from pathlib import Path

# fmt: off
SH1 = [
    (0x0C58EA, 0x9FF8, 0x3482, "move.w d2,(a2)",                                   "handler"),
    (0x0C58FC, 0x1039, 0x508F, "addq.l #8,a7        [pop 2 longs after jsr (a4)]", "handler"),
    (0x0C5906, 0x1BE0, 0x2680, "move.l d0,(a3)",                                   "handler"),
    (0x0C596E, 0x4FEF, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler"),
    (0x00C5D72, 0x0280, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x00C5F1A, 0x4E95, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x00C5F44, 0x2C39, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x00C5F8C, 0x2DB4, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x00C662A, 0x508F, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x00C76CC, 0x2F39, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x0C83E2, 0x4879, 0x22D8, "move.l (a0)+,(a1)+  [memcpy 8x unrolled, slot 0]", "handler+loop"),
    (0x0C83EC, 0x167E, 0x22D8, "move.l (a0)+,(a1)+  [memcpy 8x unrolled, slot 5]", "handler+loop"),
    (0x13A090, 0x3C9A, 0x3091, "move.w (a1),(a0)    [sans post-incrementation]",            "handler+ROM"),
    (0x0142528, 0x0008, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x1427E8, 0x4E90, 0x32BC, "move.w #$1000,(a1)",                               "handler"),
    (0x14282A, 0x00C0, 0x36BC, "move.w #$1000,(a3)",                               "handler"),
    (0x14284C, 0xE808, 0x2209, "move.l a1,d1        [before add.l d0,d1]",         "handler"),
    (0x142854, 0x0000, 0x2881, "move.l d1,(a4)",                                   "handler"),
    (0x142872, 0x4A42, 0x30BC, "move.w #$1000,(a0)",                               "handler"),
    (0x142894, 0x1800, 0x2209, "move.l a1,d1        [before add.l d0,d1]",         "handler"),
    (0x14289C, 0x41F9, 0x2681, "move.l d1,(a3)",                                   "handler"),
    (0x1428B4, 0x3002, 0x3092, "move.w (a2),(a0)",                                  "handler"),
    (0x1428C4, 0x00FF, 0x0281, "andi.l #$FFFF,d1",                                 "handler+ROM"),
    (0x1428E0, 0x6000, 0xD2B9, "add.l $FF21A8.l,d1",                               "handler+ROM"),
    (0x1428EA, 0x7420, 0x2281, "move.l d1,(a1)",                                    "handler"),
    (0x1703C2, 0x217C, 0x102B, "move.b $20(a3),d0",                                "handler"),
    (0x1703CE, 0x0018, 0x4A2B, "tst.b $2B(a3)",                                    "handler"),
    (0x1703D6, 0xFE9E, 0x0240, "andi.w #$FF,d0      [before mulu.w #$16,d0]",      "handler"),
    (0x1703E6, 0x326A, 0xD0AB, "add.l $1C(a3),d0  [base du descripteur + indice LOD]", "handler+runtime"),
    (0x170406, 0x3239, 0x206F, "movea.l $6A(a7),a0",                               "handler"),
    (0x1705B2, 0x0016, 0x526F, "addq.w #1,$4A(a7)  [compteur avant objet suivant]", "handler+SH2"),
    (0x1705BE, 0x0000, 0x670A, "beq.b $1705CA",                                    "handler"),
    (0x1705C0, 0x063E, 0x0C6F, "cmpi.w #$80,$4A(a7)",                              "handler"),
    (0x1705E2, 0x3230, 0xBE6F, "cmp.w $34(a7),d7",                                 "handler"),
    (0x1705EA, 0xD1C8, 0x0C6F, "cmpi.w #$80,$4A(a7)",                              "handler"),
    (0x1705FE, 0x002A, 0x302B, "move.w $2A(a3),d0",                                "handler"),
    (0x17060A, 0x0C2B, 0x342B, "move.w $A(a3),d2",                                 "handler"),
    (0x170610, 0x004A, 0xE840, "asr.w #4,d0",                                      "handler"),
    (0x170628, 0x162F, 0x4840, "swap d0             [high word of muls result]",   "handler"),
    (0x17063E, 0x063E, 0x1639, "move.b $12F9.l,d3",                                 "handler+ROM"),
    (0x17065A, 0x5283, 0x3042, "movea.w d2,a0",                                     "handler+ROM"),
    (0x17066C, 0x3401, 0x7A0B, "moveq #$B,d5",                                     "handler"),
    (0x170670, 0xD26F, 0x0283, "andi.l #$FF,d3",                                    "handler+ROM"),
    (0x170690, 0x6D00, 0x5381, "subq.l #1,d1",                                      "handler+ROM"),
    (0x1706B0, 0x7AFF, 0x700C, "moveq #$C,d0",                                     "handler"),
    (0x1706B4, 0x93C9, 0x3F42, "move.w d2,$36(a7)",                                 "handler+ROM"),
    (0x170732, 0x1580, 0x3028, "move.w $6(a0),d0",                                  "handler+ROM"),
    (0x170760, 0x00FF, 0x5489, "addq.l #2,a1",                                      "handler+ROM"),
    (0x170788, 0x2F79, 0x266B, "movea.l $18(a3),a3  [parcours de liste]",           "handler+ROM"),
    (0x170790, 0x0601, 0x6600, "bne.w $1705E2  [boucle de liste]",                  "handler+ROM"),
    (0x170A5E, 0x003A, 0x246F, "movea.l $3A(a7),a2",                                "handler+ROM"),
    (0x170A72, 0xD281, 0x7A0B, "moveq #$B,d5  [decalage pour lsl.w d5,d2]",         "handler+ROM"),
    (0x170A76, 0xEB6A, 0xD842, "add.w d2,d4",                                       "handler"),
    (0x170A9A, 0x43E9, 0x6700, "beq.w $1705B2",                                     "handler+ROM"),
    (0x170A9E, 0xECA2, 0x342B, "move.w $C(a3),d2",                                  "handler"),
    (0x170ABC, 0x0964, 0x3F45, "move.w d5,$46(a7)",                                 "handler+ROM"),
    (0x170ADA, 0x45EF, 0x3228, "move.w $6(a0),d1",                                  "handler+ROM"),
    (0x170AE2, 0x43E9, 0x3401, "move.w d1,d2",                                      "handler+ROM"),
    (0x170AE6, 0xECA2, 0x4A41, "tst.w d1",                                          "handler+ROM"),
    (0x170B02, 0x0054, 0x3212, "move.w (a2),d1",                                    "handler"),
    (0x170B04, 0x2F41, 0x548A, "addq.l #2,a2",                                      "handler"),
    (0x170B1C, 0x004A, 0x5283, "addq.l #1,d3",                                      "handler+ROM"),
    (0x170B26, 0x2F79, 0x266F, "movea.l $42(a7),a3",                                "handler+ROM"),
    (0x170B36, 0xFCEA, 0x3242, "movea.w d2,a1",                                     "handler+ROM"),
    (0x170E2C, 0x4DEE, 0x7A00, "moveq #0,d5  [zero-extension avant move.w d0,d5]",     "handler+ROM"),
    (0x170E9C, 0x4841, 0xBE6F, "cmp.w $34(a7),d7",                                  "handler+ROM"),
    (0x170F14, 0x0112, 0x4A68, "tst.w $4(a0)",                                      "handler+ROM"),
    (0x170F3A, 0x003E, 0x3A2F, "move.w $32(a7),d5",                                 "handler+ROM"),
    (0x170F44, 0x007C, 0xBE6F, "cmp.w $34(a7),d7",                                  "handler+ROM"),
    (0x1711C4, 0x0034, 0x7400, "moveq #0,d2            [zero-extend before move.w d1,d2]", "handler"),
    (0x171234, 0x003A, 0xD868, "add.w $2(a0),d4",                                   "handler+ROM"),
    (0x171268, 0x0006, 0x266F, "movea.l $42(a7),a3",                                "handler+ROM"),
    (0x17128C, 0x003E, 0xEE81, "asr.l #7,d1",                                       "handler"),
    (0x171578, 0x6400, 0x3428, "move.w $4(a0),d2",                                 "handler"),
    (0x171580, 0x6500, 0x4A42, "tst.w d2",                                         "handler"),
    (0x171592, 0x0641, 0x92AF, "sub.l $3E(a7),d1",                                  "handler+ROM"),
    (0x17159A, 0x92AF, 0x0641, "addi.w #$80,d1",                                    "symetrie ROM"),
    (0x17176C, 0x6446, 0x342F, "move.w $32(a7),d2",                                 "handler+ROM"),
    (0x171778, 0x6500, 0xBE6F, "cmp.w $34(a7),d7",                                  "handler+ROM"),
    (0x171780, 0x342F, 0x266F, "movea.l $42(a7),a3",                                "handler+ROM"),
    (0x1717A4, 0x1941, 0xEE81, "asr.l #7,d1",                                       "handler+ROM"),
    (0x171DC4, 0x0002, 0x5381, "subq.l #1,d1",                                     "handler"),
    (0x171DE4, 0x0006, 0x3400, "move.w d0,d2        [avant ext.l d2 / cmp.l d2,d5]", "handler+ROM"),
    (0x171E48, 0x0642, 0xD2E8, "adda.w $2(a0),a1",                                  "handler+ROM"),
    (0x1723FC, 0x1D40, 0x342F, "move.w $36(a7),d2",                                 "handler+ROM"),
    (0x172534, 0x0C41, 0x242A, "move.l $14(a2),d2",                                "handler"),
    (0x172540, 0x0003, 0x102A, "move.b $47(a2),d0",                                "handler"),
    (0x172558, 0x0004, 0x302A, "move.w $A(a2),d0",                                 "handler"),
    (0x17255E, 0x6702, 0x206A, "movea.l $1C(a2),a0",                               "handler"),
    (0x172570, 0x0014, 0x3200, "move.w d0,d1",                                     "handler"),
    (0x17257C, 0x0000, 0x1E28, "move.b $B(a0),d7",                                 "handler"),
    (0x172586, 0x0018, 0x4285, "clr.l d5",                                         "handler"),
    (0x172592, 0x0018, 0xB289, "cmp.l a1,d1",                                      "handler"),
    (0x1725B0, 0x2F00, 0x4287, "clr.l d7            [zero-extend before add.l]",   "handler"),
    (0x1725C0, 0x4A82, 0x720C, "moveq #$C,d1        [shift count for lsr.l d1,d6]","handler"),
    (0x1725C4, 0x0018, 0x3546, "move.w d6,$40(a2)",                                "handler"),
    (0x1725E0, 0x0014, 0x6712, "beq.b $1725F4       [list walk: exit if a0==0]",   "handler"),
    (0x1725E2, 0x42AA, 0xB068, "cmp.w $A(a0),d0     [list walk: compare key]",     "handler"),
    (0x1725F4, 0x2A6A, 0xB5C9, "cmpa.l a1,a2",                                     "handler"),
    (0x19B91C, 0x0048, 0x246A, "movea.l $18(a2),a2  [parcours de liste]",           "handler+ROM"),
    (0x19B924, 0x205D, 0x6700, "beq.w $19BAA2",                                     "handler+ROM"),
    (0x19B928, 0x00FF, 0x0C2A, "cmpi.b #$FD,$20(a2)",                               "handler+ROM"),
    (0x19B930, 0x45F9, 0x102A, "move.b $23(a2),d0",                                 "handler+ROM"),
    # ARM handler $0D57C4 stores A4+$0A at CPU-state +$2C (D1), then forms
    # A0 = sign_extend(D1.w) - sign_extend(D4.w).  D6 must keep the collision
    # table count: writing the object's depth there overruns the FF408C table.
    (0x19B93E, 0x3C1C, 0x322C, "move.w $A(a4),d1",                                  "handler+ROM+runtime"),
    (0x19B94E, 0x00FF, 0x6D00, "blt.w $19BB2C",                                     "handler+ROM"),
    (0x19B956, 0xBA80, 0x6EC4, "bgt.b $19B91C  [reboucle sur la liste]",            "handler+ROM"),
    (0x01E5F76, 0x13FC, 0x1039, "move.b $FF3D0E.l,d0 [vblank wait-flag spin loop]",  "handler+SH2"),
    (0x1EB908, 0x0201, 0x3039, "move.w $C00004.l,d0 [attente fin VBlank]",          "handler+ROM"),
    (0x1EB914, 0x0007, 0x3039, "move.w $C00004.l,d0 [attente debut VBlank]",       "handler+ROM"),
    (0x1EEA28, 0x5346, 0x3204, "move.w d4,d1        [VDP tilemap blit loop]",      "handler+runtime"),
    (0x1F0E7C, 0x4EB9, 0x4A18, "tst.b (a0)+         [strlen]",                     "SH2+runtime"),
    (0x1F3584, 0x60D6, 0x4240, "clr.w d0            [byte->tile loop]",            "handler+runtime"),
    (0x1F5A7E, 0x4CDF, 0x12DA, "move.b (a2)+,(a1)+  [aPLib copy loop]",            "handler+runtime"),
    (0x1F5A88, 0xD040, 0xD603, "add.b d3,d3         [aPLib getbit]",               "handler+runtime"),
    (0x1FAB70, 0x1601, 0x2F02, "move.l d2,-(a7)     [__udivsi3]",                  "SH2+handler"),
    (0x1FAB8A, 0x01D9, 0x3002, "move.w d2,d0        [__udivsi3]",                  "SH2"),
    (0x1FAB94, 0x2929, 0x3002, "move.w d2,d0        [__udivsi3]",                  "SH2"),
    (0x1FABCC, 0xCB90, 0x2F02, "move.l d2,-(a7)     [__divsi3]",                   "SH2"),
    (0x1FABEE, 0x3D20, 0x508F, "addq.l #8,a7        [__divsi3]",                   "SH2"),
]

# Compatibility guard for the reconstructed standalone ROM.  During the attract-mode
# restart, 0x0FB324 calls the object projection once with only Harrier left in the
# list.  Harrier's update marks itself inactive ($20 = FF), so the accepted-object
# count D3 is zero at 0x17264A.  M2's original environment never exposes the ensuing
# 0/0 to a real 68000; on MAME it raises vector 5 and displays "DIVIDE BY ZERO".
#
# Replace the three argument-setup words with a jump to an unused, zero-filled ROM
# area.  The trampoline bypasses only the division/store when D3 == 0; otherwise it
# reproduces the displaced instructions byte-for-byte and returns at 0x172656.
SH1_DIVZERO_GUARD = [
    (0x17264A, bytes.fromhex("30432F082F00"), bytes.fromhex("4EF9003CBCF2"),
     "jmp $3CBCF2  [guard object-average divisor]"),
    (0x3CBCF2, bytes(28), bytes.fromhex(
        "4A43"          # tst.w d3
        "6712"          # beq.b zero
        "3043"          # movea.w d3,a0
        "2F08"          # move.l a0,-(a7)
        "2F00"          # move.l d0,-(a7)
        "4EB9001FABCC"  # jsr __divsi3
        "4EF900172656"  # jmp normal stack cleanup
        "4EF90017265E"  # zero: jmp epilogue
    ), "skip average when no active object"),
]

SH2_DIVZERO_GUARD = [
    (0x13D35C, bytes.fromhex("30432F082F00"), bytes.fromhex("4EF90037FFC0"),
     "jmp $37FFC0  [guard SH2 object-average divisor]"),
    (0x37FFC0, bytes(28), bytes.fromhex(
        "4A43" "6712" "3043" "2F08" "2F00"
        "4EB9001A9BCC" "4EF90013D368" "4EF90013D370"
    ), "skip SH2 average when no active object"),
]

# The Stage 1 script used by attract variant $81 jumps from distance $0037 to
# $078A.  That deliberately skips the normal vertical-tree stream (request $27),
# while the independent low-bush stream (request $36) keeps running.  On the M2
# host the missing scenery was supplied outside the standalone 68000 path.
#
# Restore it without replacing the bushes: when the vertical-tree descriptor
# finishes loading, create the first tree; while that descriptor remains active,
# each subsequent Stage 1 bush event also creates one randomly-positioned tree.
# Both calls use the ROM's normal creator at $178066, so allocation, projection,
# LOD selection and cleanup remain native game logic.
SH1_TREE_RESTORE = [
    (0x13E41C, bytes.fromhex("13FC000100FF"), bytes.fromhex("4EF9003CBD0E"),
     "jmp $3CBD0E  [restore first Stage 1 vertical tree]"),
    (0x3CBD0E, bytes(38), bytes.fromhex(
        "13FC000100FF2149"  # move.b #1,$FF2149
        "423900FF2148"      # clr.b $FF2148
        "0C39000100FF16CC"  # cmpi.b #1,$FF16CC (Stage 1)
        "66000008"          # bne.w done
        "4EB900178066"      # jsr random vertical-tree creator
        "4CDF1C1C"          # restore original callee-saved registers
        "4E75"              # rts
    ), "seed one tree after its graphics have loaded"),
    (0x140CEA, bytes.fromhex("103900FF2164"), bytes.fromhex("4EF9003CBD34"),
     "jmp $3CBD34  [pair later bushes with vertical trees]"),
    (0x3CBD34, bytes(44), bytes.fromhex(
        "103900FF2164"      # displaced: move.b $FF2164,d0
        "0C050036"          # cmpi.b #$36,d5 (low bush request)
        "6600001A"          # bne.w normal enqueue
        "0CB9000007AC00FF214A"  # cmpi.l #$7AC,$FF214A (tree set active)
        "6600000C"          # bne.w normal enqueue
        "2F00"              # preserve the queue index across the creator
        "4EB900178066"      # jsr random vertical-tree creator
        "201F"              # restore d0
        "4EF900140CF0"      # resume the original request enqueue
    ), "add a tree without consuming the low-bush request"),
]

# Player shots are limited by the byte at $FF40A6.  A few collision paths can
# retire every projectile while leaving this count above four; from then on the
# stock creation routine rejects fire forever, even though no $131A projectile
# object remains.  Keep the original five-shot limit whenever at least one shot
# is still active, but recover a demonstrably stale counter by walking the active
# list once at the refusal point.
SH1_SHOT_COUNTER_GUARD = [
    (0x1E55D6, bytes.fromhex("103900FF40A6"), bytes.fromhex("4EF9003CBD62"),
     "jmp $3CBD62  [recover stale player-shot count]"),
    (0x3CBD62, bytes(64), bytes.fromhex(
        "103900FF40A6"      # move.b $FF40A6,d0
        "0C000004"          # cmpi.b #4,d0
        "6300002E"          # bls.w normal
        "207900FF40B8"      # movea.l active-list head,a0
        "B0FC0000"          # loop: cmpa.w #0,a0
        "660A"              # bne.b inspect
        "423900FF40A6"      # no projectile: clear stale count
        "7000"              # moveq #0,d0
        "6016"              # bra.b normal
        "0CA80000131A001C"  # inspect: cmpi.l #$131A,$1C(a0)
        "6606"              # bne.b next
        "4EF9001E55EA"      # a real shot remains: preserve stock refusal
        "20680018"          # next: movea.l $18(a0),a0
        "60DA"              # bra.b loop
        "4EF9001E55DC"      # normal: resume stock method/limit setup
    ), "repair only a stale shot count after proving the active list has no shots"),
]

# The Stage 1 script waits for $FF3CDE to reach zero before advancing.  A long
# manual fight can retire every Moot object while leaving this byte above zero;
# the screen is then empty forever on Stage 1.  This wait operator is also active
# while Moot is being assembled, and the counter can precede insertion of the
# first controller into the active list by part of a frame.  A list-only guard
# therefore advanced the scenario too early and eventually caused an ADDRESS
# ERROR in the collision list.
#
# FF3CDF is the unused byte adjacent to the byte-only FF3CDE counter.  Arm it only
# after the real Moot controller has actually been observed.  A repair then needs
# all three proofs: Stage 1, this armed encounter, and no controller/segment/
# hand-off/explosion left in the active list.  Clear the latch on a native zero or
# on another stage so an encounter cannot leak into a later scenario.
SH1_BOSS_COMPLETION_GUARD = [
    (0x140A9C, bytes.fromhex("4A3900FF3CDE"), bytes.fromhex(
        "4EF9003CBDA2"  # jmp $3CBDA2
    ), "jmp $3CBDA2  [repair stale Stage 1 boss count]"),
    (0x3CBDA2, bytes(152), bytes.fromhex(
        "48E78080"              # movem.l d0/a0,-(a7)
        "4A3900FF3CDE"          # tst.b $FF3CDE
        "67000076"              # beq.w clear_latch
        "0C39000100FF16CC"      # cmpi.b #1,$FF16CC
        "6600006A"              # bne.w clear_latch
        "207900FF40B8"          # movea.l active-list head,a0
        "B0FC0000"              # loop: cmpa.w #0,a0
        "67000042"              # beq.w no_boss_objects
        "20280010"              # move.l $10(a0),d0
        "0C800013841A"          # boss controller
        "67000028"              # beq.w arm_latch
        "0C80000C8560"          # live body segment
        "6700004A"              # beq.w compare
        "0C80000CBF16"          # segment handing off to explosion
        "67000040"              # beq.w compare
        "0C800012CA16"          # explosion/destruction object
        "67000036"              # beq.w compare
        "20680018"              # movea.l $18(a0),a0
        "6000FFC6"              # bra.w loop
        "13FC000100FF3CDF"      # arm_latch: move.b #1,$FF3CDF
        "60000022"              # bra.w compare
        "4A3900FF3CDF"          # no_boss_objects: tst.b latch
        "67000018"              # beq.w compare
        "423900FF3CDE"          # repair stale count
        "423900FF3CDF"          # consume latch
        "60000008"              # bra.w compare
        "423900FF3CDF"          # clear_latch
        "4A3900FF3CDE"          # compare: restore original CCR
        "4CDF0101"              # movem.l (a7)+,d0/a0
        "4EF900140AA2"          # jmp after displaced test
    ), "complete Stage 1 only after an observed Moot has fully disappeared"),
]

SH2 = [
    (0x178F1A, 0x00C0, 0x1039, "move.b $FF3884.l,d0 [vblank wait-flag spin loop]",  "SH1 idiom"),
    (0x1999EC, 0x2F9A, 0x3039, "move.w <framecnt>.l,d0",                           "SH1"),
    (0x19DA8C, 0x0287, 0x3204, "move.w d4,d1        [VDP tilemap blit loop]",      "handler+runtime"),
    (0x1A2DB6, 0x3400, 0x10C1, "move.b d1,(a0)+     [memset]",                     "SH1"),
    (0x1A4A7E, 0x4CDF, 0x12DA, "move.b (a2)+,(a1)+  [aPLib copy loop]",            "handler+runtime"),
    (0x1A4A88, 0xD040, 0xD603, "add.b d3,d3         [aPLib getbit]",               "handler+runtime"),

    # Transposees depuis SH1 : l'emetteur de sprites et une partie de la bibliotheque
    # runtime de M2 sont communs aux deux jeux, a decalage constant (-0x352EE pour
    # l'emetteur, -0x50F9C pour la bibliotheque). Appariement sur le contexte octet a
    # octet de part et d'autre du mot corrompu, taux de concordance >= 85 %.
    (0x13B0FA, 0x6700, 0xD0AB, "add.l $1C(a3),d0  [base du descripteur + indice LOD]", "handler+SH1 1703E6"),
    (0x13B2D4, 0xD281, 0x0C6F, "cmpi.w #$80,$4A(a7)",                          "SH2<-SH1 1705C0"),
    (0x13B444, 0x2F43, 0x3028, "move.w $6(a0),d0",                             "SH2<-SH1 170732"),
    (0x13B472, 0x41F9, 0x5489, "addq.l #2,a1",                                 "SH2<-SH1 170760"),
    (0x13B7F8, 0x2443, 0x4A41, "tst.w d1",                                     "SH2<-SH1 170AE6"),
    (0x13B816, 0x005A, 0x548A, "addq.l #2,a2",                                 "SH2<-SH1 170B04"),
    (0x13B848, 0x302F, 0x3242, "movea.w d2,a1",                                "SH2<-SH1 170B36"),
    (0x13BBAE, 0x3C01, 0xBE6F, "cmp.w $34(a7),d7",                             "SH2<-SH1 170E9C"),
    (0x13BC26, 0x342F, 0x4A68, "tst.w $4(a0)",                                 "SH2<-SH1 170F14"),
    (0x13BF46, 0x0036, 0xD868, "add.w $2(a0),d4",                              "SH2<-SH1 171234"),
    (0x13BF7A, 0x8028, 0x266F, "movea.l $42(a7),a3",                           "SH2<-SH1 171268"),
    (0x13BF9E, 0x0042, 0xEE81, "asr.l #7,d1",                                  "SH2<-SH1 17128C"),
    (0x13C292, 0x1941, 0x4A42, "tst.w d2",                                     "SH2<-SH1 171580"),
    (0x13C2AC, 0x266F, 0x0641, "addi.w #$80,d1",                               "SH2<-SH1 17159A"),
    (0x13CAF6, 0x0010, 0x3400, "move.w d0,d2        [avant ext.l d2 / cmp.l d2,d5]", "SH2<-SH1 171DE4"),
    (0x13CB5A, 0x000C, 0xD2E8, "adda.w $2(a0),a1",                             "SH2<-SH1 171E48"),
    (0x13D10E, 0x0000, 0x342F, "move.w $36(a7),d2",                            "SH2<-SH1 1723FC"),
    (0x13D252, 0x0019, 0x102A, "move.b $47(a2),d0",                            "SH2<-SH1 172540"),
    (0x13D2A4, 0xB44A, 0xB289, "cmp.l a1,d1",                                  "SH2<-SH1 172592"),
    (0x13D2F4, 0x6000, 0xB068, "cmp.w $A(a0),d0     [list walk: compare key]", "SH2<-SH1 1725E2"),
    (0x18F5A8, 0x00FF, 0x1039, "move.b $00FF3884.l,d0",                        "handler"),
    (0x19A174, 0x0020, 0x3039, "move.w $00FF414E.l,d0",                        "handler"),
    (0x00044E, 0x0807, 0x4CDF, "movem.l (a7)+,d0-d1/a0-a1 [epilogue du 0x442, puis rte]", "handler+symetrie"),
    (0x199D2E, 0x00FF, 0x4CDF, "movem.l (a7)+,d2-d4 [masque 001C, puis rts]",        "handler+masque"),
    (0x1984AE, 0x0C00, 0x2F02, "move.l d2,-(a7)     [puis move.l $8(a7),d0]",       "handler"),
    (0x19911A, 0x40FC, 0x2F02, "move.l d2,-(a7)     [puis move.w $FF39F4.l,d0]",    "handler"),
    (0x199C94, 0xE18A, 0x5280, "addq.l #1,d0        [puis move.l d0,$FF4670]",      "handler"),
    (0x199CA8, 0x4243, 0x2079, "movea.l $FF3ABC.l,a0",                            "handler"),
    (0x199CB2, 0x010A, 0x6702, "beq.b $199CB6       [garde : saute jsr (a0) si a0 nul]", "handler"),
    (0x13D246, 0x4FEF, 0x242A, "move.l $14(a2),d2",                               "SH2<-SH1 172534"),
    (0x13D26A, 0x0004, 0x302A, "move.w $A(a2),d0",                                "SH2<-SH1 172558"),
    (0x13D270, 0x1B40, 0x206A, "movea.l $1C(a2),a0",                              "SH2<-SH1 17255E"),
    (0x13D28E, 0x0080, 0x1E28, "move.b $B(a0),d7",                                "SH2<-SH1 17257C"),
    (0x13D298, 0x3B40, 0x4285, "clr.l d5",                                        "SH2<-SH1 172586"),
    (0x13D2C2, 0xEE80, 0x4287, "clr.l d7",                                        "SH2<-SH1 1725B0"),
    (0x13D2D2, 0x0006, 0x720C, "moveq #$C,d1",                                    "SH2<-SH1 1725C0"),
    (0x13D2D6, 0x0080, 0x3546, "move.w d6,$40(a2)",                               "SH2<-SH1 1725C4"),
    (0x13D2F2, 0xFC18, 0x6712, "beq.b $13D306      [passer par cmpa.l a1,a2 avant tout retrait]", "handler+SH1+runtime"),
    (0x199CFE, 0x0800, 0x0282, "andi.l #$FFFF,d2    [puis move.l d2,$FF40B6]",     "handler"),
    (0x199D14, 0x0004, 0x6702, "beq.b $199D18       [garde : saute jsr (a0)]",      "handler"),
    (0x199D1E, 0x0019, 0x3039, "move.w $FF4138.l,d0 [puis andi.w #$FFFE,d0]",       "handler"),
    (0x199D3C, 0x6402, 0x0C40, "cmpi.w #$E0,d0      [extension 00E0, puis beq.b]",   "handler"),
    (0x199D50, 0x3239, 0x4A40, "tst.w d0            [avant beq.w $199CA8]",          "handler"),
    (0x199D94, 0x0004, 0x4880, "ext.w d0            [puis neg.w d0]",                "handler"),
    (0x198542, 0x4E90, 0x48E7, "movem.l d2-d7/a2-a5,-(a7) [masque 3F3C, 10 reg = 40 o]", "handler+masque"),
    (0x19854C, 0x2F00, 0x41F9, "lea $FF39B8.l,a0    [ou movea.l #, equivalent ; puis cmpi.b #$A,(a0)]", "handler"),
    (0x198954, 0x0008, 0x4EB9, "jsr $199A1E.l       [retour 19895A empile = +6]",   "handler+extension"),
    (0x199CC0, 0x00DC, 0x3803, "move.w d3,d4        [avant andi.l #$FFFF,d4]",       "handler"),
    (0x199D9A, 0x4878, 0x4EB9, "jsr $19911A.l       [retour 199DA0 empile = +6]",    "handler+extension"),
    (0x19857E, 0x0241, 0x2F3C, "move.l #$00A10003,-(a7) [port manette 1, extensions 00A1 0003]", "handler+extension"),
    (0x198588, 0x6054, 0x3200, "move.w d0,d1        [avant lsr.w #6,d1]",            "handler"),
    (0x1985B2, 0x2079, 0x588F, "addq.l #4,a7        [8 cycles, suite en 1985B4]",    "handler"),
    (0x199DA0, 0x001A, 0x6000, "bra.w $199CD0       [retour dans la chaine de btst]", "handler+extension"),
    (0x19A96C, 0x0001, 0x3039, "move.w $C00004.l,d0 [attente sur etat VDP, btst #3 / bne]", "handler+extension"),
    (0x17174A, 0x6E00, 0x246A, "movea.l $18(a2),a2  [maillon suivant, puis cmpa.w #0,a2]", "handler+extension"),
    # Generateur de la table du reechantillonneur de lignes MDP (analogue SH1 0x1427C0).
    (0x18BCD0, 0x7400, 0x30BC, "move.w #$1000,(a0)  [echelle neutre, ligne 1/3]",   "handler+SH1"),
    (0x18BCEA, 0x7001, 0x45E8, "lea $C(a0),a2       [extension 000C]",              "handler+SH1"),
    (0x18BD12, 0x720F, 0x30BC, "move.w #$1000,(a0)  [ligne 2/3]",                   "handler+SH1"),
    (0x18BD34, 0x33C3, 0x220A, "move.l a2,d1        [avant add.l d0,d1]",           "handler+SH1"),
    (0x18BD3C, 0x0DDC, 0x2681, "move.l d1,(a3)",                                    "handler+SH1"),
    (0x18BD56, 0x0DD8, 0x30BC, "move.w #$1000,(a0)  [ligne 3/3]",                   "handler+SH1"),
    (0x18BD78, 0x33C0, 0x760C, "moveq #$C,d3        [decalage, avant lsl.l d3,d1]", "handler+SH1"),
    (0x18BD7C, 0x5282, 0x2681, "move.l d1,(a3)",                                    "handler+SH1"),
    (0x18BD94, 0x00E0, 0x3091, "move.w (a1),(a0)    [a1 = pointeur source]",        "handler+SH1"),
    (0x18BDA4, 0x00BE, 0x0281, "andi.l #$FFFF,d1    [extension 0000FFFF]",          "handler+SH1"),
    (0x18BDC0, 0x9480, 0xD2B9, "add.l $FF3538.l,d1  [extension 00FF3538]",          "handler+SH1"),
    (0x18BDD4, 0x2279, 0x2481, "move.l d1,(a2)      [puis addq.l #4,a1]",           "handler+SH1"),
    (0x13CA6C, 0x2A39, 0x7800, "moveq #$0,d4",                                    "SH1 171D5A"),
    (0x13CA7C, 0x000A, 0x760B, "moveq #$B,d3",                                    "SH1 171D6A"),
    (0x13CA80, 0x7200, 0x3241, "movea.w d1,a1",                                   "SH1 171D6E"),
    (0x13CAA6, 0x0022, 0x362B, "move.w $C(a3),d3    [extension 000C]",            "SH1 171D94"),
    (0x13CACC, 0x6600, 0x0C42, "cmpi.w #$15F,d2     [extension 015F]",            "SH1 171DBA"),
    (0x13CAD6, 0x6600, 0x5381, "subq.l #1,d1",                                    "SH1 171DC4"),
    (0x13CAE0, 0x50AF, 0x3003, "move.w d3,d0",                                    "SH1 171DCE"),
    (0x13B0D6, 0x263C, 0x102B, "move.b $20(a3),d0   [ext 0020]",                  "SH1 1703C2"),
    (0x13B0E2, 0x342B, 0x4A2B, "tst.b $2B(a3)       [ext 002B]",                  "SH1 1703CE"),
    (0x13B0EA, 0x0002, 0x0240, "andi.w #$FF,d0      [ext 00FF]",                  "SH1 1703D6"),
    (0x13B11A, 0x3F42, 0x206F, "movea.l $6A(a7),a0  [ext 006A]",                  "SH1 170406"),
    (0x13B2D2, 0x323B, 0x670A, "beq.b $13B2DE       [cible recalculee sur SH2]",     "SH1 1705BE"),
    (0x13B2F6, 0x004B, 0xBE6F, "cmp.w $34(a7),d7    [ext 0034]",                  "SH1 1705E2"),
    (0x13B312, 0x00FF, 0x082B, "btst #$2,$2B(a3)    [ext 0002 puis 002B]",         "handler+extension"),
    (0x13B49A, 0x0080, 0x266B, "movea.l $18(a3),a3  [ext 0018]",                  "SH1 170788"),
    (0x13B7EC, 0x000C, 0x3228, "move.w $6(a0),d1    [ext 0006]",                  "SH1 170ADA"),
    (0x13B7F4, 0x0000, 0x3401, "move.w d1,d2        [puis mulu.w d0,d2]",         "SH1 170AE2"),
    (0x13B814, 0xDCC1, 0x3212, "move.w (a2),d1",                                  "SH1 170B02"),
    (0x13B82E, 0x41E8, 0x5283, "addq.l #1,d3",                                    "SH1 170B1C"),
    (0x13B4A2, 0x7C0C, 0x6600, "bne.w $13B2F6       [ext FE52]",                  "SH1 170790"),
    (0x13BC4C, 0x0032, 0x3A2F, "move.w $32(a7),d5   [ext 0032]",                  "SH1 170F3A"),
    (0x13C28A, 0x526F, 0x3428, "move.w $4(a0),d2    [ext 0004]",                  "SH1 171578"),
    (0x13C2A4, 0x3542, 0x92AF, "sub.l $3E(a7),d1    [ext 003E]",                  "SH1 171592"),
    (0x13C47E, 0x4230, 0x342F, "move.w $32(a7),d2   [ext 0032]",                  "SH1 17176C"),
    (0x13C6E0, 0x6000, 0x246B, "movea.l $1C(a3),a2  [ext 001C]",                  "SH1 1719CE"),
    (0x13C82E, 0x182A, 0x3F4A, "move.w a2,$32(a7)   [ext 0032]",                  "SH1 171B1C"),
    (0x13CDC6, 0x48C3, 0x3940, "move.w d0,$6(a4)    [ext 0006]",                  "SH1 1720B4"),
    (0x13CDE6, 0x3036, 0x0200, "andi.b #$10,d0      [drapeau MDP, ext 0010]",     "SH1 1720D4"),
    (0x171756, 0x3540, 0x0C2A, "cmpi.b #$FD,$20(a2) [ext FFFD 0020, cf SH1 171730]", "handler+SH1"),
    (0x171752, 0x4A44, 0x6700, "beq.w $1718C4       [garde a2 nul, ext 0170]",       "handler+extension"),
    (0x17175E, 0x3039, 0x102A, "move.b $23(a2),d0   [ext 0023, puis move.b d0,d1]", "handler+extension"),
    (0x190A80, 0x2F3C, 0x30C1, "move.w d1,(a0)+",                                 "handler"),
    (0x1985B8, 0x00FF, 0x6700, "beq.w $1986CC       [garde a0 nul, ext 0112]",      "handler+extension"),
    (0x1986CC, 0x41F9, 0x0C39, "cmpi.b #$A,$FF39B9.l [ext 000A 00FF 39B9]",         "handler+extension"),
    (0x199142, 0x5240, 0x207C, "movea.l #$A11100,a0 [busreq Z80, ext 00A1 1100]",  "handler+extension"),
    (0x1972D6, 0x0100, 0x206F, "movea.l $4(a7),a0  [ext 0004]",                  "SH2<-SH1 1E8272"),
    (0x19895A, 0x48E7, 0x4CDF, "movem.l (a7)+,d2-d7/a2-a5 [masque 3CFC = miroir de 3F3C, epilogue du 198542]", "handler+symetrie"),
    (0x199184, 0x2030, 0x1010, "move.b (a0),d0      [a0 = $A00113, RAM Z80]",       "handler"),
    (0x19D4A6, 0x0010, 0x33C2, "move.w d2,$C00000.l [port de donnees VDP, boucle dbf]", "handler+extension"),
    # Native SH2 handler $0BF174 copies all of D4 to D1 at $0BF206. D4 is -32
    # here: restore the signed 32-line phase when ADDQ makes D1 non-negative.
    # NOP loses this reset. See the original-ARM oracle and SH2_NATIVE_REFERENCE.
    (0x18BCF4, 0x4E75, 0x2204, "move.l d4,d1        [reset signed MDP line phase to -32]", "handler+original-ARM oracle"),
    (0x199C74, 0x4243, 0x48E7, "movem.l d2-d4,-(a7) [masque 3800 ; prologue du 199D2E]", "handler+symetrie"),
    (0x199CA2, 0x0012, 0x4A00, "tst.b d0            [avant beq.w $199D34]",       "handler"),
    (0x19A3D0, 0x4EBA, 0x1039, "move.b $FF3AC0.l,d0 [puis andi.b #2,d0]",       "handler"),
    (0x000442, 0x8DBF, 0x48E7, "movem.l d0-d1/a0-a1,-(a7)  [masque C0C0 en +2]", "handler"),
    (0x199A1E, 0x42A7, 0x3039, "move.w $FF4138.l,d0",                              "handler"),
    (0x19A978, 0x4EB9, 0x3039, "move.w $C00004.l,d0 [attente debut VBlank]",   "SH2<-SH1 1EB914"),
]

# fmt: on

ROMS = {
    "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72": ("Space Harrier",    SH1),
    "80f576af01d6413c0b92073e2f947b0431f12a74": ("Space Harrier II", SH2),
}

EXTRA_PATCHES = {
    "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72": (
        SH1_DIVZERO_GUARD + SH1_TREE_RESTORE + SH1_SHOT_COUNTER_GUARD +
        SH1_BOSS_COMPLETION_GUARD
    ),
    "80f576af01d6413c0b92073e2f947b0431f12a74": SH2_DIVZERO_GUARD,
}


def patch(src, dst):
    d = bytearray(open(src, 'rb').read())
    sha = hashlib.sha1(d).hexdigest()
    rom_key = sha
    if rom_key not in ROMS:
        # Permit an already repaired ROM as input.  This keeps the patcher
        # idempotent even when a later compatibility fix is added and the
        # pristine extracted image is no longer available locally.
        for candidate, (candidate_name, candidate_table) in ROMS.items():
            if len(d) > max(off for off, *_ in candidate_table) + 1 and all(
                struct.unpack_from('>H', d, off)[0] in (bad, good)
                for off, bad, good, *_ in candidate_table
            ):
                rom_key = candidate
                break
        else:
            print(f"  !! unrecognised ROM (sha1 {sha})")
            return -1
    name, table = ROMS[rom_key]
    print(f"  {name}  ({len(d):,} bytes)")
    n = 0
    for off, bad, good, mnem, truth in table:
        cur = struct.unpack_from('>H', d, off)[0]
        if cur == bad:
            struct.pack_into('>H', d, off, good)
            print(f"    {off:07X}  {bad:04X} -> {good:04X}  {mnem:50s} ({truth})")
            n += 1
        elif cur == good:
            print(f"    {off:07X}  already {good:04X}")
        else:
            print(f"    {off:07X}  UNEXPECTED {cur:04X} (want {bad:04X}) - SKIPPED")
    for off, bad, good, mnem in EXTRA_PATCHES.get(rom_key, []):
        cur = bytes(d[off:off + len(bad)])
        if cur == bad:
            d[off:off + len(good)] = good
            print(f"    {off:07X}  {mnem} (compatibility guard)")
            n += 1
        elif cur == good:
            print(f"    {off:07X}  guard already applied")
        else:
            print(f"    {off:07X}  UNEXPECTED bytes for guard - SKIPPED")
    open(dst, 'wb').write(d)
    total = len(table) + len(EXTRA_PATCHES.get(rom_key, []))
    print(f"  -> {dst}: {n}/{total} repaired")
    return n


def main():
    parser = argparse.ArgumentParser(
        description="Repair an original Mega Drive Mini 2 Space Harrier ROM."
    )
    parser.add_argument("input", type=Path, help="original .smp file")
    parser.add_argument("output", type=Path, nargs="?", help="patched output file")
    args = parser.parse_args()

    output = args.output or args.input.with_name(
        f"{args.input.stem}_patched{args.input.suffix}"
    )
    if args.input.resolve() == output.resolve():
        parser.error("input and output must be different files")
    return 0 if patch(args.input, output) >= 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
