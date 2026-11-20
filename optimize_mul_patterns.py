# --------------------------------------------------------------------
# Copyright (c) 2025-2026 fabri1983
# Author: Pablo L (fabri1983)
# fabri1983@gmail.com
#
# This script is part of the Gcc's gas assembly optimizer for cpu m68000.
# See disclaimer at main script.
# --------------------------------------------------------------------

import re
from typing import Callable
from optimize_lst import (
    find_free_after_use_DATA_regs,
    find_unused_DATA_regs,
    add_regs_into_push_pop_if_not_scratch_or_in_interrupt,
    replace_xN_by_xM_in_next_lines
)

# Registry for public functions
_PUBLIC_FUNCS_AND_CLASSES = []

def export_func(func: Callable) -> Callable:
    """Decorator to automatically add functions to __all__"""
    _PUBLIC_FUNCS_AND_CLASSES.append(func.__name__)
    return func

def export_class(cls: type) -> type:
    """Decorator to automatically add classes to __all__"""
    _PUBLIC_FUNCS_AND_CLASSES.append(cls.__name__)
    return cls

MULS_IMM_REGEX = re.compile(r'^(\s*)muls(?:\.w)?(\s+)#([^,]+),\s*(%d[0-7])')
MULU_IMM_REGEX = re.compile(r'^(\s*)mulu(?:\.w)?(\s+)#([^,]+),\s*(%d[0-7])')

def imm_to_int(literal: str) -> int:
    """
    Converts a decimal, 0x-prefixed or $-prefixed hexadecimal literal into an int.
    """
    if literal[0] == '$':
        return int(literal[1:], 16)
    if literal[:2] in ('0x', '0X'):
        return int(literal, 16)
    return int(literal)

@export_func
def muls_high_word_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    # TODO: for all muls instructions if source is negative then is the same than
    # non negative optimization followed by a neg.l dN at the end. Additional penalty of 6 cycles.

    m = MULS_IMM_REGEX.match(line)
    if not m:
        return ([], False)

    multiplier = imm_to_int(m.group(3))
    dN = m.group(4)

    match multiplier:

        # muls.w  #0,dN     ->   moveq  #0,dN     ; Saves 38 cycles
        case 0:
            optimized_line = f'{m.group(1)}moveq{m.group(2)}#0,{dN}'
            return ([optimized_line], True)

        # muls.w  #1,dN     ->   ext.l  dN        ; Saves 42 cycles
        case 1:
            optimized_line = f'{m.group(1)}ext.l{m.group(2)}{dN}'
            return ([optimized_line], True)

        # muls.w  #2,dN     ->   ext.l  dN        ; Saves 34 cycles
        #                        add.l  dN,dN
        case 2:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}add.l{m.group(2)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #3,dN     ->   ext.l   dN       ; Saves 24 cycles
        #                        move.l  dN,dM
        #                        add.l   dN,dN
        #                        add.l   dM,dN
        case 3:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #4,dN     ->   ext.l  dN        ; Saves 30 cycles
        #                        asl.l  #2,dN
        case 4:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}asl.l{m.group(2)}#2,{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #7,dN     ->   ext.l   dN       ; Saves 20 cycles
        #                        move.l  dN,dM
        #                        asl.l   #3,dN
        #                        sub.l   dM,dN
        case 7:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #8,dN     ->   ext.l  dN        ; Saves 28 cycles
        #                        asl.l  #3,dN
        case 8:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}asl.l{m.group(2)}#3,{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #9,dN     ->   ext.l   dN       ; Saves 20 cycles
        #                        move.l  dN,dM
        #                        asl.l   #3,dN
        #                        add.l   dM,dN
        case 9:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #10,dN    ->   ext.l   dN       ; Saves 14 cycles
        #                        move.l  dN,dM
        #                        asl.l   #2,dN
        #                        add.l   dM,dN
        #                        add.l   dN,dN
        case 10:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #11,dN    ->   ext.l   dN       ; Saves 16 cycles
        #                        move.l  dN,dM
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        asl.l   #2,dN
        #                        sub.l   dM,dN
        case 11:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #12,dN    ->   ext.l   dN       ; Saves 4 cycles
        #                        move.l  dN,dM
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        asl.l   #2,dN
        case 12:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #13,dN    ->   ext.l   dN       ; Saves 8 cycles
        #                        move.l  dN,dM
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        asl.l   #2,dN
        #                        add.l   dM,dN
        case 13:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #14,dN    ->   ext.l   dN       ; Saves 12 cycles
        #                        move.l  dN,dM
        #                        asl.l   #3,dN
        #                        sub.l   dM,dN
        #                        add.l   dN,dN
        case 14:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #15,dN    ->   ext.l   dN       ; Saves 20 cycles
        #                        move.l  dN,dM
        #                        asl.l   #4,dN
        #                        sub.l   dM,dN
        case 15:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #16,dN    ->   ext.l  dN        ; Saves 26 cycles
        #                        asl.l  #4,dN
        case 16:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}asl.l{m.group(2)}#4,{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #17,dN    ->   ext.l   dN       ; Saves 18 cycles
        #                        move.l  dN,dM
        #                        asl.l   #4,dN
        #                        add.l   dM,dN
        case 17:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #18,dN    ->   ext.l   dN       ; Saves 12 cycles
        #                        add.l   dN,dN
        #                        move.l  dN,dM
        #                        asl.l   #3,dN
        #                        add.l   dM,dN
        case 18:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #19,dN    ->   ext.l   dN       ; Saves 6 cycles
        #                        move.l  dN,dM
        #                        asl.l   #3,dN
        #                        add.l   dM,dN
        #                        add.l   dN,dN
        #                        add.l   dM,dN
        case 19:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #20,dN    ->   ext.l   dN       ; Saves 10 cycles
        #                        move.l  dN,dM
        #                        asl.l   #2,dN
        #                        add.l   dM,dN
        #                        asl.l   #2,dN
        case 20:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #21,dN    ->   ext.l   dN       ; Saves 6 cycles
        #                        move.l  dN,dM
        #                        asl.l   #2,dN
        #                        add.l   dM,dN
        #                        asl.l   #2,dN
        #                        add.l   dM,dN
        case 21:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #22,dN    ->   ext.l   dN       ; Saves 8 cycles
        #                        add.l   dN,dN
        #                        move.l  dN,dM
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        asl.l   #2,dN
        #                        sub.l   dM,dN
        case 22:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#2,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #23,dN    ->   ext.l   dN       ; Saves 6 cycles
        #                        move.l  dN,dM
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        asl.l   #3,dN
        #                        sub.l   dM,dN
        case 23:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #24,dN    ->   ext.l   dN       ; Saves 8 cycles
        #                        move.l  dN,dM
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        asl.l   #3,dN
        case 24:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #25,dN    ->   ext.l   dN       ; Saves 4 cycles
        #                        move.l  dN,dM
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        asl.l   #3,dN
        #                        add.l   dM,dN
        case 25:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #26,dN    ->   ext.l   dN       ; Saves 4 cycles
        #                        move.l  dN,dM
        #                        add.l   dM,dM
        #                        add.l   dM,dN
        #                        asl.l   #3,dN
        #                        add.l   dM,dN
        case 26:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.l{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #29,dN    ->   ext.l   dN       ; Saves 4 cycles
        #                        move.l  dN,dM
        #                        asl.l   #5,dN
        #                        sub.l   dM,dN
        #                        sub.l   dM,dN
        #                        sub.l   dM,dN
        case 29:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #30,dN    ->   ext.l   dN       ; Saves 10 cycles
        #                        move.l  dN,dM
        #                        asl.l   #5,dN
        #                        sub.l   dM,dN
        #                        sub.l   dM,dN
        case 30:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #31,dN    ->   ext.l   dN       ; Saves 20 cycles
        #                        move.l  dN,dM
        #                        asl.l   #5,dN
        #                        sub.l   dM,dN
        case 31:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #32,dN    ->   ext.l  dN        ; Saves 24 cycles
        #                        asl.l  #5,dN
        case 32:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}asl.l{m.group(2)}#5,{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #33,dN    ->   ext.l   dN       ; Saves 16 cycles
        #                        move.l  dN,dM
        #                        asl.l   #5,dN
        #                        add.l   dM,dN
        case 33:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #34,dN    ->   ext.l   dN       ; Saves 8 cycles
        #                        move.l  dN,dM
        #                        asl.l   #5,dN
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        case 34:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #35,dN    ->   ext.l   dN       ; Saves 2 cycles
        #                        move.l  dN,dM
        #                        asl.l   #5,dN
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        #                        add.l   dM,dN
        case 35:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}ext.l{m.group(2)}{dN}',
                    f'{m.group(1)}move.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.l{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #64,dN    ->   ext.l  dN        ; Saves 22 cycles
        #                        asl.l  #6,dN
        case 64:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}asl.l{m.group(2)}#6,{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #128,dN    ->  ext.l  dN        ; Saves 20 cycles
        #                        asl.l  #7,dN
        case 128:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}asl.l{m.group(2)}#7,{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #256,dN    ->  ext.l  dN        ; Saves 18 cycles
        #                        asl.l  #8,dN
        case 256:
            optimized_lines = [
                f'{m.group(1)}ext.l{m.group(2)}{dN}',
                f'{m.group(1)}asl.l{m.group(2)}#8,{dN}'
            ]
            return (optimized_lines, True)

        case _:
            return ([], False)

@export_func
def mulu_high_word_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    m = MULU_IMM_REGEX.match(line)
    if not m:
        return ([], False)

    multiplier = imm_to_int(m.group(3))
    dN = m.group(4)

    match multiplier:

        # mulu.w  #0,dN     ->   moveq   #0,dN    ; Saves 38 cycles
        case 0:
            optimized_line = f'{m.group(1)}moveq{m.group(2)}#0,{dN}'
            return ([optimized_line], True)

        # mulu.w  #1,dN     ->   moveq   #0,dM    ; Saves 36 cycles
        #                        move.w  dN,dM
        case 1:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #2,dN     ->   moveq   #0,dM    ; Saves 28 cycles
        #                        move.w  dN,dM
        #                        add.l   dM,dM
        case 2:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #3,dN     ->   moveq   #0,dM    ; Saves 18 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        add.l   dM,dM
        #                        add.l   dN,dM
        case 3:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #4,dN     ->   moveq   #0,dM    ; Saves 24 cycles
        #                        move.w  dN,dM
        #                        lsl.l   #2,dM
        case 4:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#2,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #5,dN     ->   moveq   #0,dM    ; Saves 14 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #2,dM
        #                        add.l   dN,dM
        case 5:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#2,{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #6,dN     ->   moveq   #0,dM    ; Saves 10 cycles
        #                        move.w  dN,dM
        #                        add.l   dM,dM
        #                        move.l  dM,dN
        #                        add.l   dM,dM
        #                        add.l   dN,dM
        case 6:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #7,dN     ->   moveq   #0,dM    ; Saves 14 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #3,dM
        #                        sub.l   dN,dM
        case 7:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#3,{dM}',
                    f'{m.group(1)}sub.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #8,dN     ->   moveq   #0,dM     ; Saves 22 cycles
        #                        move.w  dN,dM
        #                        lsl.l   #3,dM
        case 8:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#3,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #9,dN     ->   moveq   #0,dM    ; Saves 12 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #3,dM
        #                        add.l   dN,dM
        case 9:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#3,{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #10,dN    ->   moveq   #0,dM    ; Saves 6 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #2,dM
        #                        add.l   dN,dM
        #                        add.l   dM,dM
        case 10:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#2,{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #11,dN    ->   moveq   #0,dM    ; Saves 8 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        add.l   dN,dM
        #                        add.l   dN,dM
        #                        lsl.l   #2,dM
        #                        sub.l   dN,dM
        case 11:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#2,{dM}',
                    f'{m.group(1)}sub.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #14,dN    ->   moveq   #0,dM    ; Saves 6 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #3,dM
        #                        sub.l   dN,dM
        #                        add.l   dM,dM
        case 14:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#3,{dM}',
                    f'{m.group(1)}sub.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #15,dN    ->   moveq   #0,dM    ; Saves 14 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #4,dM
        #                        sub.l   dN,dM
        case 15:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#4,{dM}',
                    f'{m.group(1)}sub.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #16,dN    ->   moveq   #0,dM    ; Saves 20 cycles
        #                        move.w  dN,dM
        #                        lsl.l   #4,dM
        case 16:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#4,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #17,dN    ->   moveq   #0,dM    ; Saves 10 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #4,dM
        #                        add.l   dN,dM
        case 17:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#4,{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #18,dN    ->   moveq   #0,dM    ; Saves 4 cycles
        #                        move.w  dN,dM
        #                        add.l   dM,dM
        #                        move.l  dM,dN
        #                        lsl.l   #3,dM
        #                        add.l   dN,dM
        case 18:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#3,{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #20,dN    ->   moveq   #0,dM    ; Saves 2 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #2,dM
        #                        add.l   dN,dM
        #                        lsl.l   #2,dM
        case 20:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#2,{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#2,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #24,dN    ->   moveq   #0,dM    ; Saves 4 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        add.l   dM,dM
        #                        add.l   dN,dM
        #                        lsl.l   #3,dM
        case 24:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.l{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#3,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #30,dN    ->   moveq   #0,dM    ; Saves 4 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #5,dM
        #                        sub.l   dN,dM
        #                        sub.l   dN,dM
        case 30:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#5,{dM}',
                    f'{m.group(1)}sub.l{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}sub.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #31,dN    ->   moveq   #0,dM    ; Saves 14 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #5,dM
        #                        sub.l   dN,dM
        case 31:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#5,{dM}',
                    f'{m.group(1)}sub.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #32,dN    ->   moveq   #0,dM    ; Saves 18 cycles
        #                        move.w  dN,dM
        #                        lsl.l   #5,dM
        case 32:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#5,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #33,dN    ->   moveq   #0,dM    ; Saves 8 cycles
        #                        move.w  dN,dM
        #                        move.l  dM,dN
        #                        lsl.l   #5,dM
        #                        add.l   dN,dM
        case 33:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.l{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.l{m.group(2)}#5,{dM}',
                    f'{m.group(1)}add.l{m.group(2)}{dN},{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #64,dN    ->   moveq   #0,dM    ; Saves 16 cycles
        #                        move.w  dN,dM
        #                        lsl.l   #6,dM
        case 64:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#6,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #128,dN   ->   moveq   #0,dM    ; Saves 14 cycles
        #                        move.w  dN,dM
        #                        lsl.l   #7,dM
        case 128:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#7,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #256,dN   ->   moveq   #0,dM    ; Saves 12 cycles
        #                        move.w  dN,dM
        #                        lsl.l   #8,dM
        case 256:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None:
                replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
                optimized_lines = [
                    f'{m.group(1)}moveq{m.group(2)}#0,{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.l{m.group(2)}#8,{dM}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        case _:
            return ([], False)

@export_func
def muls_high_word_not_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    # TODO: for all muls instructions if source is negative then is the same than
    # non negative optimization followed by a neg.l dN at the end. Additional penalty of 4 cycles.

    m = MULS_IMM_REGEX.match(line)
    if not m:
        return ([], False)

    multiplier = imm_to_int(m.group(3))
    dN = m.group(4)

    match multiplier:

        # muls.w  #0,dN   ->    moveq  #0,dN     ; Saves 38 cycles
        case 0:
            optimized_line = f'{m.group(1)}moveq{m.group(2)}#0,{dN}'
            return ([optimized_line], True)

        # muls.w  #1,dN   ->   remove line       ; Saves 38 cycles
        case 1:
            return ([], True)

        # muls.w  #2,dN   ->   add.w   dN,dN     ; Saves 42 cycles
        case 2:
            optimized_line = f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
            return ([optimized_line], True)

        # muls.w  #3,dN   ->   move.w  dN,dM     ; Saves 36 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 3:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #4,dN   ->   add.w   dN,dN     ; Saves 38 cycles
        #                      add.w   dN,dN
        case 4:
            optimized_lines = [
                f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # muls.w  #5,dN   ->   move.w  dN,dM     ; Saves 34 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 5:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #6,dN   ->   add.w   dN,dN     ; Saves 32 cycles
        #                      move.w  dN,dM
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 6:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #7,dN   ->   move.w  dN,dM     ; Saves 30 cycles
        #                      asl.w   #3,dN
        #                      sub.w   dM,dN
        case 7:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #8,dN   ->    asl.w  #3,dN     ; Saves 34 cycles
        case 8:
            optimized_line = f'{m.group(1)}asl.w{m.group(2)}#3,{dN}'
            return ([optimized_line], True)

        # muls.w  #9,dN   ->   move.w  dN,dM     ; Saves 30 cycles
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        case 9:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #10,dN  ->   move.w  dN,dM     ; Saves 30 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        case 10:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #11,dN  ->   move.w  dN,dM     ; Saves 28 cycles
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      sub.w   dM,dN
        case 11:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #12,dN  ->   move.w  dN,dM     ; Saves 28 cycles
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 12:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #13,dN  ->   move.w  dN,dM     ; Saves 28 cycles
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 13:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #14,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      asl.w   #3,dN
        #                      sub.w   dM,dN
        #                      add.w   dN,dN
        case 14:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #15,dN  ->   move.w  dN,dM     ; Saves 30 cycles
        #                      asl.w   #4,dN
        #                      sub.w   dM,dN
        case 15:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #16,dN  ->   asl.w  #4,dN      ; Saves 32 cycles
        case 16:
            optimized_line = f'{m.group(1)}asl.w{m.group(2)}#4,{dN}'
            return ([optimized_line], True)

        # muls.w  #17,dN  ->   move.w  dN,dM     ; Saves 28 cycles
        #                      asl.w   #4,dN
        #                      add.w   dM,dN
        case 17:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #18,dN  ->   add.w   dN,dN     ; Saves 26 cycles
        #                      move.w  dN,dM
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        case 18:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #19,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 19:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #20,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 20:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #21,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 21:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #22,dN  ->   add.w   dN,dN     ; Saves 24 cycles
        #                      move.w  dN,dM
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      sub.w   dM,dN
        case 22:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #23,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      sub.w   dM,dN
        case 23:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #24,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        case 24:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #25,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        case 25:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #26,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      add.w   dM,dM
        #                      add.w   dM,dN
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        case 26:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #27,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      asl.w   #3,dN
        #                      sub.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      sub.w   dM,dN
        case 27:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #28,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      asl.w   #3,dN
        #                      sub.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 28:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #29,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      asl.w   #5,dN
        #                      sub.w   dM,dN
        #                      sub.w   dM,dN
        #                      sub.w   dM,dN
        case 29:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #30,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      asl.w   #5,dN
        #                      sub.w   dM,dN
        #                      sub.w   dM,dN
        case 30:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #31,dN  ->   move.w  dN,dM     ; Saves 30 cycles
        #                      asl.w   #5,dN
        #                      sub.w   dM,dN
        case 31:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #32,dN   ->    asl.w  #5,dN    ; Saves 30 cycles
        case 32:
            optimized_line = f'{m.group(1)}asl.w{m.group(2)}#5,{dN}'
            return ([optimized_line], True)

        # muls.w  #33,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      asl.w   #5,dN
        #                      add.w   dM,dN
        case 33:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #34,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      asl.w   #5,dN
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        case 34:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #35,dN  ->   move.w  dN,dM     ; Saves 20 cycles
        #                      asl.w   #5,dN
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        case 35:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #36,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 36:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #37,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 37:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #38,dN  ->   add.w   dN,dN     ; Saves 20 cycles
        #                      move.w  dN,dM
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 38:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #39,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      asl.w   #3,dN
        #                      sub.w   dM,dN
        case 39:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #40,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      asl.w   #3,dN
        case 40:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #41,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        case 41:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #42,dN  ->   move.w  dN,dM     ; Saves 20 cycles
        #                      add.w   dM,dM
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      asl.w   #3,dN
        #                      add.w   dM,dN
        case 42:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}asl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # muls.w  #64,dN   ->    asl.w  #6,dN    ; Saves 28 cycles
        case 64:
            optimized_line = f'{m.group(1)}asl.w{m.group(2)}#6,{dN}'
            return ([optimized_line], True)

        # muls.w  #128,dN  ->    asl.w  #7,dN    ; Saves 26 cycles
        case 128:
            optimized_line = f'{m.group(1)}asl.w{m.group(2)}#7,{dN}'
            return ([optimized_line], True)

        # muls.w  #256,dN  ->    asl.w  #8,dN    ; Saves 24+2 cycles
        #                                        ; It can be optimized like lsl.w #8, there 2 more saved cycles
        case 256:
            optimized_lines = [
                #f'{m.group(1)}asl.w{m.group(2)}#8,{dN}' replaced by next:
                f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                f'{m.group(1)}clr.b{m.group(2)}{dN}'
            ]
            return (optimized_lines, True)

        case _:
            return ([], False)

@export_func
def mulu_high_word_not_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    m = MULU_IMM_REGEX.match(line)
    if not m:
        return ([], False)

    multiplier = imm_to_int(m.group(3))
    dN = m.group(4)

    match multiplier:

        # mulu.w  #0,dN   ->    moveq  #0,dN     ; Saves 38 cycles
        case 0:
            optimized_line = f'{m.group(1)}moveq{m.group(2)}#0,{dN}'
            return ([optimized_line], True)

        # mulu.w  #1,dN   ->   remove line       ; Saves 44 cycles
        case 1:
            return ([], True)

        # mulu.w  #2,dN   ->   add.w   dN,dN     ; Saves 40 cycles
        case 2:
            optimized_line = f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
            return ([optimized_line], True)

        # mulu.w  #3,dN   ->   move.w  dN,dM     ; Saves 34 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 3:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #4,dN   ->   add.w   dN,dN     ; Saves 36 cycles
        #                      add.w   dN,dN
        case 4:
            optimized_lines = [
                f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # mulu.w  #5,dN   ->   move.w  dN,dM     ; Saves 30 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 5:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #6,dN   ->   add.w   dN,dN     ; Saves 30 cycles
        #                      move.w  dN,dM
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 6:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #7,dN   ->   move.w  dN,dM     ; Saves 28 cycles
        #                      lsl.w   #3,dN
        #                      sub.w   dM,dN
        case 7:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #8,dN   ->    lsl.w  #3,dN     ; Saves 32 cycles
        case 8:
            optimized_line = f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
            return ([optimized_line], True)

        # mulu.w  #9,dN   ->   move.w  dN,dM     ; Saves 26 cycles
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        case 9:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #10,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        case 10:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #11,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      sub.w   dM,dN
        case 11:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #12,dN  ->   move.w  dN,dM     ; Saves 26 cycles
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 12:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #13,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 13:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #14,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      lsl.w   #3,dN
        #                      sub.w   dM,dN
        #                      add.w   dN,dN
        case 14:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #15,dN  ->   move.w  dN,dM     ; Saves 28 cycles
        #                      lsl.w   #4,dN
        #                      sub.w   dM,dN
        case 15:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #16,dN  ->   lsl.w  #4,dN      ; Saves 30 cycles
        case 16:
            optimized_line = f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
            return ([optimized_line], True)

        # mulu.w  #17,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      lsl.w   #4,dN
        #                      add.w   dM,dN
        case 17:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #18,dN  ->   add.w   dN,dN     ; Saves 22 cycles
        #                      move.w  dN,dM
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        case 18:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #19,dN  ->   move.w  dN,dM     ; Saves 20 cycles
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 19:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #20,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 20:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #21,dN  ->   move.w  dN,dM     ; Saves 20 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 21:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #22,dN  ->   add.w   dN,dN     ; Saves 20 cycles
        #                      move.w  dN,dM
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      sub.w   dM,dN
        case 22:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #23,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      sub.w   dM,dN
        case 23:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #24,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        case 24:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #25,dN  ->   move.w  dN,dM     ; Saves 20 cycles
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        case 25:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #26,dN  ->   move.w  dN,dM     ; Saves 20 cycles
        #                      add.w   dM,dM
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        case 26:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #27,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      lsl.w   #3,dN
        #                      sub.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      sub.w   dM,dN
        case 27:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #28,dN  ->   move.w  dN,dM     ; Saves 24 cycles
        #                      lsl.w   #3,dN
        #                      sub.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 28:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #29,dN  ->   move.w  dN,dM     ; Saves 18 cycles
        #                      lsl.w   #5,dN
        #                      sub.w   dM,dN
        #                      sub.w   dM,dN
        #                      sub.w   dM,dN
        case 29:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #30,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      lsl.w   #5,dN
        #                      sub.w   dM,dN
        #                      sub.w   dM,dN
        case 30:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #31,dN  ->   move.w  dN,dM     ; Saves 28 cycles
        #                      lsl.w   #5,dN
        #                      sub.w   dM,dN
        case 31:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #32,dN   ->    lsl.w  #5,dN    ; Saves 28 cycles
        case 32:
            optimized_line = f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
            return ([optimized_line], True)

        # mulu.w  #33,dN  ->   move.w  dN,dM     ; Saves 22 cycles
        #                      lsl.w   #5,dN
        #                      add.w   dM,dN
        case 33:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #34,dN  ->   move.w  dN,dM     ; Saves 18 cycles
        #                      lsl.w   #5,dN
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        case 34:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #35,dN  ->   move.w  dN,dM     ; Saves 16 cycles
        #                      lsl.w   #5,dN
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        case 35:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #36,dN  ->   move.w  dN,dM     ; Saves 18 cycles
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        case 36:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #37,dN  ->   move.w  dN,dM     ; Saves 16 cycles
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 37:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #38,dN  ->   add.w   dN,dN     ; Saves 16 cycles
        #                      move.w  dN,dM
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        case 38:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #39,dN  ->   move.w  dN,dM     ; Saves 18 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      sub.w   dM,dN
        case 39:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #40,dN  ->   move.w  dN,dM     ; Saves 18 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        case 40:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #41,dN  ->   move.w  dN,dM     ; Saves 16 cycles
        #                      add.w   dN,dN
        #                      add.w   dN,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        case 41:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # mulu.w  #42,dN  ->   move.w  dN,dM     ; Saves 16 cycles
        #                      add.w   dM,dM
        #                      add.w   dM,dN
        #                      add.w   dM,dN
        #                      lsl.w   #3,dN
        #                      add.w   dM,dN
        case 42:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # *44
        case 44:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *45
        case 45:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}move.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *46
        case 46:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *48
        case 48:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *49
        case 49:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *56
        case 56:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *60
        case 60:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *62
        case 62:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *63
        case 63:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # mulu.w  #64,dN   ->    lsl.w  #6,dN    ; Saves 26 cycles
        case 64:
            optimized_line = f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}'
            return ([optimized_line], True)

        # *65
        case 65:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *66
        case 66:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *68
        case 68:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *72
        case 72:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *80
        case 80:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *84
        case 84:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *92
        case 92:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *96
        case 96:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *112
        case 112:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *120
        case 120:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *124
        case 124:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *126
        case 126:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *127
        case 127:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # mulu.w  #128,dN  ->    lsl.w  #7,dN    ; Saves 24 cycles
        case 128:
            optimized_line = f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}'
            return ([optimized_line], True)

        # *129
        case 129:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *130
        case 130:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *132
        case 132:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *136
        case 136:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *144
        case 144:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *156
        case 156:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *160
        case 160:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *184
        case 184:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *192
        case 192:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *196
        case 196:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *200
        case 200:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *208
        case 208:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *224
        case 224:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *240
        case 240:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *248
        case 248:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *252
        case 252:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *254
        case 254:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *255
        case 255:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}',
                    f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                    f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                    f'{m.group(1)}clr.b{m.group(2)}{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # mulu.w  #256,dN  ->    lsl.w  #8,dN    ; Saves 22+2 cycles
        #                                        ; lsl.w #8 is optimized, there 2 more saved cycles
        case 256:
            optimized_lines = [
                #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}'
                f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                f'{m.group(1)}clr.b{m.group(2)}{dN}'
            ]
            return (optimized_lines, True)

        # *257
        case 257:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}',
                    f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                    f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                    f'{m.group(1)}clr.b{m.group(2)}{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *258
        case 258:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *260
        case 260:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *264
        case 264:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *272
        case 272:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *288
        case 288:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *304
        case 304:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *320
        case 320:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *384
        case 384:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *400
        case 400:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *416
        case 416:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *480
        case 480:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *512
        case 512:
            optimized_lines = [
                #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}',
                f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                f'{m.group(1)}clr.b{m.group(2)}{dN}',
                f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # *576
        case 576:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *608
        case 608:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#5,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *624
        case 624:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *625
        case 625:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *640
        case 640:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *768
        case 768:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}'
                    f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                    f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                    f'{m.group(1)}clr.b{m.group(2)}{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *896
        case 896:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *960
        case 960:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#6,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *1024
        case 1024:
            optimized_lines = [
                #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}',
                f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                f'{m.group(1)}clr.b{m.group(2)}{dN}',
                f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # *1280
        case 1280:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}' replaced by next:
                    f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                    f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                    f'{m.group(1)}clr.b{m.group(2)}{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *1920    ; Saves 8 cycles
        case 1920:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}lsl.w{m.group(2)}#4,{dN}',
                    f'{m.group(1)}sub.w{m.group(2)}{dM},{dN}',
                    f'{m.group(1)}lsl.w{m.group(2)}#7,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *2048    ; Saves 12 cycles
        case 2048:
            optimized_lines = [
                #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}', replaced by next:
                f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                f'{m.group(1)}clr.b{m.group(2)}{dN}',
                f'{m.group(1)}lsl.w{m.group(2)}#3,{dN}'
            ]
            return (optimized_lines, True)

        # *2560
        case 2560:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}', replaced by next:
                    f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                    f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                    f'{m.group(1)}clr.b{m.group(2)}{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        # *3072
        case 3072:
            dM = find_free_after_use_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_DATA_regs([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{m.group(1)}move.w{m.group(2)}{dN},{dM}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dM},{dN}',
                    #f'{m.group(1)}lsl.w{m.group(2)}#8,{dN}', replaced by next:
                    f'{m.group(1)}move.b{m.group(2)}{dN},-(%sp)',
                    f'{m.group(1)}move.w{m.group(2)}(%sp)+,{dN}',
                    f'{m.group(1)}clr.b{m.group(2)}{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}',
                    f'{m.group(1)}add.w{m.group(2)}{dN},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)

        case _:
            return ([], False)

# Export decorated functions and classes
__all__ = _PUBLIC_FUNCS_AND_CLASSES