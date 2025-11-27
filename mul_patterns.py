import re
from typing import Callable
from optimize_lst import (
    find_free_after_use_data_register,
    find_unused_data_register,
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

@export_func
def muls_high_word_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    # TODO: for all muls instructions if source is negative then is the same than
    # non negative optimization followed by a neg.l dN at the end. Additional penalty of 6 cycles.

    # muls.w  #0,dN     ->   moveq  #0,dN     ; Saves 38 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(0|0x0|$0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}moveq{match.group(3)}#0,{dN}'
        return ([optimized_line], True)

    # muls.w  #1,dN     ->   ext.l  dN        ; Saves 42 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(1|0x1|$1),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}ext.l{match.group(3)}{dN}'
        return ([optimized_line], True)

    # muls.w  #2,dN     ->   ext.l  dN        ; Saves 34 cycles
    #                        add.l  dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(2|0x2|$2),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}add.l{match.group(3)}{dN},{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #3,dN     ->   ext.l   dN       ; Saves 24 cycles
    #                        move.l  dN,dM
    #                        add.l   dN,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(3|0x3|$3),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #4,dN     ->   ext.l  dN        ; Saves 30 cycles
    #                        asl.l  #2,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(4|0x4|$4),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}asl.l{match.group(3)}#2,{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #7,dN     ->   ext.l   dN       ; Saves 20 cycles
    #                        move.l  dN,dM
    #                        asl.l   #3,dN
    #                        sub.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(7|0x7|$7),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #8,dN     ->   ext.l  dN        ; Saves 28 cycles
    #                        asl.l  #3,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(8|0x8|$8),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}asl.l{match.group(3)}#3,{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #9,dN     ->   ext.l   dN       ; Saves 20 cycles
    #                        move.l  dN,dM
    #                        asl.l   #3,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(9|0x9|$9),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #10,dN    ->   ext.l   dN       ; Saves 14 cycles
    #                        move.l  dN,dM
    #                        asl.l   #2,dN
    #                        add.l   dM,dN
    #                        add.l   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(10|0x[aS]|$[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #11,dN    ->   ext.l   dN       ; Saves 16 cycles
    #                        move.l  dN,dM
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    #                        asl.l   #2,dN
    #                        sub.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(11|0x[bB]|$[bB]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #12,dN    ->   ext.l   dN       ; Saves 4 cycles
    #                        move.l  dN,dM
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    #                        asl.l   #2,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(12|0x[cC]|$[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #13,dN    ->   ext.l   dN       ; Saves 8 cycles
    #                        move.l  dN,dM
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    #                        asl.l   #2,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(13|0x[dD]|$[dD]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #14,dN    ->   ext.l   dN       ; Saves 12 cycles
    #                        move.l  dN,dM
    #                        asl.l   #3,dN
    #                        sub.l   dM,dN
    #                        add.l   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(14|0x[eE]|$[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #15,dN    ->   ext.l   dN       ; Saves 20 cycles
    #                        move.l  dN,dM
    #                        asl.l   #4,dN
    #                        sub.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(15|0x[fF]|$[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #16,dN    ->   ext.l  dN        ; Saves 26 cycles
    #                        asl.l  #4,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(16|0x10|$10),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}asl.l{match.group(3)}#4,{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #17,dN    ->   ext.l   dN       ; Saves 18 cycles
    #                        move.l  dN,dM
    #                        asl.l   #4,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(17|0x11|$11),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #18,dN    ->   ext.l   dN       ; Saves 12 cycles
    #                        add.l   dN,dN
    #                        move.l  dN,dM
    #                        asl.l   #3,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(18|0x12|$12),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #19,dN    ->   ext.l   dN       ; Saves 6 cycles
    #                        move.l  dN,dM
    #                        asl.l   #3,dN
    #                        add.l   dM,dN
    #                        add.l   dN,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(19|0x13|$13),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #20,dN    ->   ext.l   dN       ; Saves 10 cycles
    #                        move.l  dN,dM
    #                        asl.l   #2,dN
    #                        add.l   dM,dN
    #                        asl.l   #2,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(20|0x14|$14),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l #2,{match.group(3)}{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #21,dN    ->   ext.l   dN       ; Saves 6 cycles
    #                        move.l  dN,dM
    #                        asl.l   #2,dN
    #                        add.l   dM,dN
    #                        asl.l   #2,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(21|0x15|$15),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
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
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(22|0x16|$16),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#2,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #23,dN    ->   ext.l   dN       ; Saves 6 cycles
    #                        move.l  dN,dM
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    #                        asl.l   #3,dN
    #                        sub.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(23|0x17|$17),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #24,dN    ->   ext.l   dN       ; Saves 8 cycles
    #                        move.l  dN,dM
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    #                        asl.l   #3,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(24|0x18|$18),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #25,dN    ->   ext.l   dN       ; Saves 4 cycles
    #                        move.l  dN,dM
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    #                        asl.l   #3,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(25|0x19|$19),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #26,dN    ->   ext.l   dN       ; Saves 4 cycles
    #                        move.l  dN,dM
    #                        add.l   dM,dM
    #                        add.l   dM,dN
    #                        asl.l   #3,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(26|0x1[aA]|$1[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.l {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #29,dN    ->   ext.l   dN       ; Saves 4 cycles
    #                        move.l  dN,dM
    #                        asl.l   #5,dN
    #                        sub.l   dM,dN
    #                        sub.l   dM,dN
    #                        sub.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(29|0x1[dD]|$1[dD]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #30,dN    ->   ext.l   dN       ; Saves 10 cycles
    #                        move.l  dN,dM
    #                        asl.l   #5,dN
    #                        sub.l   dM,dN
    #                        sub.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(30|0x1[eE]|$1[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #31,dN    ->   ext.l   dN       ; Saves 20 cycles
    #                        move.l  dN,dM
    #                        asl.l   #5,dN
    #                        sub.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(31|0x1[fF]|$1[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #32,dN    ->   ext.l  dN        ; Saves 24 cycles
    #                        asl.l  #5,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(32|0x20|$20),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}asl.l{match.group(3)}#5,{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #33,dN    ->   ext.l   dN       ; Saves 16 cycles
    #                        move.l  dN,dM
    #                        asl.l   #5,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(33|0x21|$21),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #34,dN    ->   ext.l   dN       ; Saves 8 cycles
    #                        move.l  dN,dM
    #                        asl.l   #5,dN
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(34|0x22|$22),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #35,dN    ->   ext.l   dN       ; Saves 2 cycles
    #                        move.l  dN,dM
    #                        asl.l   #5,dN
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    #                        add.l   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(35|0x23|$23),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}ext.l {match.group(3)}{dN}',
                f'{match.group(1)}move.l{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.l {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #64,dN    ->   ext.l  dN        ; Saves 22 cycles
    #                        asl.l  #6,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(64|0x40|$40),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}asl.l{match.group(3)}#6,{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #128,dN    ->  ext.l  dN        ; Saves 20 cycles
    #                        asl.l  #7,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(128|0x80|$80),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}asl.l{match.group(3)}#7,{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #256,dN    ->  ext.l  dN        ; Saves 18 cycles
    #                        asl.l  #8,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(256|0x100|$100),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}ext.l{match.group(3)}{dN}',
            f'{match.group(1)}asl.l{match.group(3)}#8,{dN}'
        ]
        return (optimized_lines, True)

    return ([], False)

@export_func
def mulu_high_word_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    # mulu.w  #0,dN     ->   moveq   #0,dN    ; Saves 38 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(0|0x0|$0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}moveq{match.group(3)}#0,{dN}'
        return ([optimized_line], True)

    # mulu.w  #1,dN     ->   moveq   #0,dM    ; Saves 36 cycles
    #                        move.w  dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(1|0x1|$1),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #2,dN     ->   moveq   #0,dM    ; Saves 28 cycles
    #                        move.w  dN,dM
    #                        add.l   dM,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(2|0x2|$2),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #3,dN     ->   moveq   #0,dM    ; Saves 18 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        add.l   dM,dM
    #                        add.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(3|0x3|$3),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #4,dN     ->   moveq   #0,dM    ; Saves 24 cycles
    #                        move.w  dN,dM
    #                        lsl.l   #2,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(4|0x4|$4),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#2,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #5,dN     ->   moveq   #0,dM    ; Saves 14 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #2,dM
    #                        add.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(5|0x5|$5),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#2,{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #6,dN     ->   moveq   #0,dM    ; Saves 10 cycles
    #                        move.w  dN,dM
    #                        add.l   dM,dM
    #                        move.l  dM,dN
    #                        add.l   dM,dM
    #                        add.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(6|0x6|$6),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #7,dN     ->   moveq   #0,dM    ; Saves 14 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #3,dM
    #                        sub.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(7|0x7|$7),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#3,{dM}',
                f'{match.group(1)}sub.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #8,dN     ->   moveq   #0,dM     ; Saves 22 cycles
    #                        move.w  dN,dM
    #                        lsl.l   #3,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(8|0x8|$8),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#3,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #9,dN     ->   moveq   #0,dM    ; Saves 12 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #3,dM
    #                        add.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(9|0x9|$9),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#3,{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #10,dN    ->   moveq   #0,dM    ; Saves 6 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #2,dM
    #                        add.l   dN,dM
    #                        add.l   dM,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(10|0x[aA]|$[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#2,{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}'
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
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(11|0x[bB]|$[bB]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#2,{dM}',
                f'{match.group(1)}sub.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #14,dN    ->   moveq   #0,dM    ; Saves 6 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #3,dM
    #                        sub.l   dN,dM
    #                        add.l   dM,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(14|0x[eE]|$[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#3,{dM}',
                f'{match.group(1)}sub.l {match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #15,dN    ->   moveq   #0,dM    ; Saves 14 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #4,dM
    #                        sub.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(15|0x[fF]|$[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#4,{dM}',
                f'{match.group(1)}sub.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #16,dN    ->   moveq   #0,dM    ; Saves 20 cycles
    #                        move.w  dN,dM
    #                        lsl.l   #4,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(16|0x10|$10),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#4,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #17,dN    ->   moveq   #0,dM    ; Saves 10 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #4,dM
    #                        add.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(17|0x11|$11),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#4,{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #18,dN    ->   moveq   #0,dM    ; Saves 4 cycles
    #                        move.w  dN,dM
    #                        add.l   dM,dM
    #                        move.l  dM,dN
    #                        lsl.l   #3,dM
    #                        add.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(18|0x12|$12),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#3,{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #20,dN    ->   moveq   #0,dM    ; Saves 2 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #2,dM
    #                        add.l   dN,dM
    #                        lsl.l   #2,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(20|0x14|$14),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#2,{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#2,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #24,dN    ->   moveq   #0,dM    ; Saves 4 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        add.l   dM,dM
    #                        add.l   dN,dM
    #                        lsl.l   #3,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(24|0x18|$18),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.l {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#3,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #30,dN    ->   moveq   #0,dM    ; Saves 4 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #5,dM
    #                        sub.l   dN,dM
    #                        sub.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(30|0x1[eE]|$1[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#5,{dM}',
                f'{match.group(1)}sub.l {match.group(3)}{dN},{dM}',
                f'{match.group(1)}sub.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #31,dN    ->   moveq   #0,dM    ; Saves 14 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #5,dM
    #                        sub.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(31|0x1[fF]|$1[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#5,{dM}',
                f'{match.group(1)}sub.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #32,dN    ->   moveq   #0,dM    ; Saves 18 cycles
    #                        move.w  dN,dM
    #                        lsl.l   #5,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(32|0x20|$20),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#5,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #33,dN    ->   moveq   #0,dM    ; Saves 8 cycles
    #                        move.w  dN,dM
    #                        move.l  dM,dN
    #                        lsl.l   #5,dM
    #                        add.l   dN,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(33|0x21|$21),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.l{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.l {match.group(3)}#5,{dM}',
                f'{match.group(1)}add.l {match.group(3)}{dN},{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #64,dN    ->   moveq   #0,dM    ; Saves 16 cycles
    #                        move.w  dN,dM
    #                        lsl.l   #6,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(64|0x40|$40),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#6,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #128,dN   ->   moveq   #0,dM    ; Saves 14 cycles
    #                        move.w  dN,dM
    #                        lsl.l   #7,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(128|0x80|$80),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#7,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #256,dN   ->   moveq   #0,dM    ; Saves 12 cycles
    #                        move.w  dN,dM
    #                        lsl.l   #8,dM
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(256|0x100|$100),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None:
            replace_xN_by_xM_in_next_lines(dN, dM, i_line, lines, modified_lines)
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(3)}#0,{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.l {match.group(3)}#8,{dM}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization
    
    return ([], False)

@export_func
def muls_high_word_not_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    # TODO: for all muls instructions if source is negative then is the same than
    # non negative optimization followed by a neg.l dN at the end. Additional penalty of 4 cycles.

    # muls.w  #0,dN   ->    moveq  #0,dN     ; Saves 38 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(0|0x0|$0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}moveq{match.group(3)}#0,{dN}'
        return ([optimized_line], True)

    # muls.w  #1,dN   ->   remove line       ; Saves 38 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(1|0x1|$1),(\s*)(%d[0-7])', line)
    if match:
        return ([], True)

    # muls.w  #2,dN   ->   add.w   dN,dN     ; Saves 42 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(2|0x2|$2),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}add.w{match.group(3)}{dN},{dN}'
        return ([optimized_line], True)

    # muls.w  #3,dN   ->   move.w  dN,dM     ; Saves 36 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(3|0x3|$3),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #4,dN   ->   add.w   dN,dN     ; Saves 38 cycles
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(4|0x4|$4),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}add.w{match.group(3)}{dN},{dN}',
            f'{match.group(1)}add.w{match.group(3)}{dN},{dN}'
        ]
        return (optimized_lines, True)

    # muls.w  #5,dN   ->   move.w  dN,dM     ; Saves 34 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(5|0x5|$5),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #6,dN   ->   add.w   dN,dN     ; Saves 32 cycles
    #                      move.w  dN,dM
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(6|0x6|$6),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #7,dN   ->   move.w  dN,dM     ; Saves 30 cycles
    #                      asl.w   #3,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(7|0x7|$7),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #8,dN   ->    asl.w  #3,dN     ; Saves 34 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(8|0x8|$8),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}asl.w{match.group(3)}#3,{dN}'
        return ([optimized_line], True)

    # muls.w  #9,dN   ->   move.w  dN,dM     ; Saves 30 cycles
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(9|0x9|$9),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #10,dN  ->   move.w  dN,dM     ; Saves 30 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(10|0x[aA]|$[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #11,dN  ->   move.w  dN,dM     ; Saves 28 cycles
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(11|0x[bB]|$[bB]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #12,dN  ->   move.w  dN,dM     ; Saves 28 cycles
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(12|0x[cC]|$[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #13,dN  ->   move.w  dN,dM     ; Saves 28 cycles
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(13|0x[dD]|$[dD]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #14,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      asl.w   #3,dN
    #                      sub.w   dM,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(14|0x[eE]|$[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #15,dN  ->   move.w  dN,dM     ; Saves 30 cycles
    #                      asl.w   #4,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(15|0x[fF]|$[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #16,dN  ->   asl.w  #4,dN      ; Saves 32 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(16|0x10|$10),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}asl.w{match.group(3)}#4,{dN}'
        return ([optimized_line], True)

    # muls.w  #17,dN  ->   move.w  dN,dM     ; Saves 28 cycles
    #                      asl.w   #4,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(17|0x11|$11),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #18,dN  ->   add.w   dN,dN     ; Saves 26 cycles
    #                      move.w  dN,dM
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(18|0x12|$12),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #19,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(19|0x13|$13),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #20,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(20|0x14|$14),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
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
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(21|0x15|$15),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
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
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(22|0x16|$16),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #23,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(23|0x17|$17),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #24,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(24|0x18|$18),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #25,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(25|0x19|$19),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #26,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      add.w   dM,dM
    #                      add.w   dM,dN
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(26|0x1[aA]|$1[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #27,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      asl.w   #3,dN
    #                      sub.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(27|0x1[bB]|$1[bB]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #28,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      asl.w   #3,dN
    #                      sub.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(28|0x1[cC]|$1[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #29,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      asl.w   #5,dN
    #                      sub.w   dM,dN
    #                      sub.w   dM,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(29|0x1[dD]|$1[dD]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #30,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      asl.w   #5,dN
    #                      sub.w   dM,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(30|0x1[eE]|$1[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #31,dN  ->   move.w  dN,dM     ; Saves 30 cycles
    #                      asl.w   #5,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(31|0x1[fF]|$1[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #32,dN   ->    asl.w  #5,dN    ; Saves 30 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(32|0x20|$20),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}asl.w{match.group(3)}#5,{dN}'
        return ([optimized_line], True)

    # muls.w  #33,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      asl.w   #5,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(33|0x21|$21),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #34,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      asl.w   #5,dN
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(34|0x22|$22),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #35,dN  ->   move.w  dN,dM     ; Saves 20 cycles
    #                      asl.w   #5,dN
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(35|0x23|$23),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #36,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(36|0x24|$24),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #37,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(37|0x25|$25),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #38,dN  ->   add.w   dN,dN     ; Saves 20 cycles
    #                      move.w  dN,dM
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(38|0x26|$26),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #39,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      asl.w   #3,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(39|0x27|$27),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #40,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      asl.w   #3,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(40|0x28|$28),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #41,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(41|0x29|$29),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #42,dN  ->   move.w  dN,dM     ; Saves 20 cycles
    #                      add.w   dM,dM
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      asl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(42|0x2[aA]|$2[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}asl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # muls.w  #64,dN   ->    asl.w  #6,dN    ; Saves 28 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(64|0x40|$40),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}asl.w{match.group(3)}#6,{dN}'
        return ([optimized_line], True)

    # muls.w  #128,dN  ->    asl.w  #7,dN    ; Saves 26 cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(128|0x80),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}asl.w{match.group(3)}#7,{dN}'
        return ([optimized_line], True)

    # muls.w  #256,dN  ->    asl.w  #8,dN    ; Saves 24+2 cycles
    #                                        ; It can be optimized like lsl.w #8, there 2 more saved cycles
    match = re.match(r'^(\s*)(muls\.w)(\s+)#(256|0x100|$100),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            #f'{match.group(1)}asl.w{match.group(3)}#8,{dN}' replaced by next:
            f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
            f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
            f'{match.group(1)}clr.b {match.group(3)}{dN}'
        ]
        return (optimized_lines, True)

    return ([], False)

def mulu_high_word_not_important(line, i_line, lines, modified_lines) -> tuple[list[str], bool]:

    # mulu.w  #0,dN   ->    moveq  #0,dN     ; Saves 38 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(0|0x0|$0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}moveq{match.group(3)}#0,{dN}'
        return ([optimized_line], True)

    # mulu.w  #1,dN   ->   remove line       ; Saves 44 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(1|0x1|$1),(\s*)(%d[0-7])', line)
    if match:
        return ([], True)

    # mulu.w  #2,dN   ->   add.w   dN,dN     ; Saves 40 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(2|0x2|$2),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}add.w{match.group(3)}{dN},{dN}'
        return ([optimized_line], True)

    # mulu.w  #3,dN   ->   move.w  dN,dM     ; Saves 34 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(3|0x3|$3),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #4,dN   ->   add.w   dN,dN     ; Saves 36 cycles
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(4|0x4|$4),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            f'{match.group(1)}add.w{match.group(3)}{dN},{dN}',
            f'{match.group(1)}add.w{match.group(3)}{dN},{dN}'
        ]
        return (optimized_lines, True)

    # mulu.w  #5,dN   ->   move.w  dN,dM     ; Saves 30 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(5|0x5|$5),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #6,dN   ->   add.w   dN,dN     ; Saves 30 cycles
    #                      move.w  dN,dM
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(6|0x6|$6),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #7,dN   ->   move.w  dN,dM     ; Saves 28 cycles
    #                      lsl.w   #3,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(7|0x7|$7),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #8,dN   ->    lsl.w  #3,dN     ; Saves 32 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(8|0x8|$8),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}lsl.w{match.group(3)}#3,{dN}'
        return ([optimized_line], True)

    # mulu.w  #9,dN   ->   move.w  dN,dM     ; Saves 26 cycles
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(9|0x9|$9),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #10,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(10|0x[aA]|$[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #11,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(11|0x[bB]|$[bB]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #12,dN  ->   move.w  dN,dM     ; Saves 26 cycles
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(12|0x[cC]|$[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #13,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(13|0x[dD]|$[dD]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #14,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      lsl.w   #3,dN
    #                      sub.w   dM,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(14|0x[eE]|$[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #15,dN  ->   move.w  dN,dM     ; Saves 28 cycles
    #                      lsl.w   #4,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(15|0x[fF]|$[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #16,dN  ->   lsl.w  #4,dN      ; Saves 30 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(16|0x10|$10),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}lsl.w{match.group(3)}#4,{dN}'
        return ([optimized_line], True)

    # mulu.w  #17,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      lsl.w   #4,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(17|0x11|$11),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #18,dN  ->   add.w   dN,dN     ; Saves 22 cycles
    #                      move.w  dN,dM
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(18|0x12|$12),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #19,dN  ->   move.w  dN,dM     ; Saves 20 cycles
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(19|0x13|$13),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #20,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(20|0x14|$14),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
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
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(21|0x15|$15),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
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
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(22|0x16|$16),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #23,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(23|0x17|$17),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #24,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(24|0x18|$18),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #25,dN  ->   move.w  dN,dM     ; Saves 20 cycles
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(25|0x19|$19),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #26,dN  ->   move.w  dN,dM     ; Saves 20 cycles
    #                      add.w   dM,dM
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(26|0x1[aA]|$1[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #27,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      lsl.w   #3,dN
    #                      sub.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(27|0x1[bB]|$1[bB]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #28,dN  ->   move.w  dN,dM     ; Saves 24 cycles
    #                      lsl.w   #3,dN
    #                      sub.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(28|0x1[cC]|$1[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #29,dN  ->   move.w  dN,dM     ; Saves 18 cycles
    #                      lsl.w   #5,dN
    #                      sub.w   dM,dN
    #                      sub.w   dM,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(29|0x1[dD]|$1[dD]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #30,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      lsl.w   #5,dN
    #                      sub.w   dM,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(30|0x1[eE]|$1[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #31,dN  ->   move.w  dN,dM     ; Saves 28 cycles
    #                      lsl.w   #5,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(31|0x1[fF]|$1[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #32,dN   ->    lsl.w  #5,dN    ; Saves 28 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(32|0x20|$20),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}lsl.w{match.group(3)}#5,{dN}'
        return ([optimized_line], True)

    # mulu.w  #33,dN  ->   move.w  dN,dM     ; Saves 22 cycles
    #                      lsl.w   #5,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(33|0x21|$21),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #34,dN  ->   move.w  dN,dM     ; Saves 18 cycles
    #                      lsl.w   #5,dN
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(34|0x22|$22),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #35,dN  ->   move.w  dN,dM     ; Saves 16 cycles
    #                      lsl.w   #5,dN
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(35|0x23|$23),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #36,dN  ->   move.w  dN,dM     ; Saves 18 cycles
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(36|0x24|$24),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #37,dN  ->   move.w  dN,dM     ; Saves 16 cycles
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(37|0x25|$25),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #38,dN  ->   add.w   dN,dN     ; Saves 16 cycles
    #                      move.w  dN,dM
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(38|0x26|$26),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #39,dN  ->   move.w  dN,dM     ; Saves 18 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      sub.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(39|0x27|$27),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #40,dN  ->   move.w  dN,dM     ; Saves 18 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(40|0x28|$28),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #41,dN  ->   move.w  dN,dM     ; Saves 16 cycles
    #                      add.w   dN,dN
    #                      add.w   dN,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(41|0x29|$29),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # mulu.w  #42,dN  ->   move.w  dN,dM     ; Saves 16 cycles
    #                      add.w   dM,dM
    #                      add.w   dM,dN
    #                      add.w   dM,dN
    #                      lsl.w   #3,dN
    #                      add.w   dM,dN
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(42|0x2[aA]|$2[aA]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)  # no free register -> not available optimization

    # *44
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(44|0x2[cC]|$2[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *45
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(45|0x2[dD]|$2[dD]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dM}',
                f'{match.group(1)}move.w{match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *46
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(46|0x2[eE]|$2[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *48
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(48|0x30|$30),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *49
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(49|0x31|$31),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *56
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(56|0x38|$38),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *60
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(60|0x3[cC]|$3[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *62
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(62|0x3[eE]|$3[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *63
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(63|0x3[fF]|$3[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # mulu.w  #64,dN   ->    lsl.w  #6,dN    ; Saves 26 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(64|0x40|$40),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}lsl.w{match.group(3)}#6,{dN}'
        return ([optimized_line], True)

    # *65
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(65|0x41|$41),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *66
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(66|0x42|$42),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *68
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(68|0x44|$44),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *72
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(72|0x48|$48),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *80
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(80|0x50|$50),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *84
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(84|0x54|$54),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *92
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(92|0x5[cC]|$5[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *96
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(96|0x60|$60),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *112
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(112|0x70|$70),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *120
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(120|0x78|$78),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *124
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(124|0x7[cC]|$7[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *126
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(126|0x7[eE]|$7[eE]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *127
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(127|0x7[fF]|$7[fF]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # mulu.w  #128,dN  ->    lsl.w  #7,dN    ; Saves 24 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(128|0x80|$80),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_line = f'{match.group(1)}lsl.w{match.group(3)}#7,{dN}'
        return ([optimized_line], True)

    # *129
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(129|0x81),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *130
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(130|0x82|$82),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *132
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(132|0x84|$84),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *136
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(136|0x88|$88),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *144
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(144|0x90|$90),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *156
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(156|0x9[cC]|$9[cC]),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *160
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(160|0xA0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *184
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(184|0xB8),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *192
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(192|0xC0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *196
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(196|0xC4),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *200
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(200|0xC8),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *208
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(208|0xD0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *224
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(224|0xE0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *240
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(240|0xF0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *248
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(248|0xF8),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *252
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(252|0xFC),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *254
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(254|0xFE),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *255
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(255|0xFF),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}',
                f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
                f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
                f'{match.group(1)}clr.b {match.group(3)}{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # mulu.w  #256,dN  ->    lsl.w  #8,dN    ; Saves 22+2 cycles
    #                                        ; lsl.w #8 is optimized, there 2 more saved cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(256|0x100),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            #f'{match.group(1)}lsl.w{match.group(3)}#8,{dN}'
            f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
            f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
            f'{match.group(1)}clr.b {match.group(3)}{dN}'
        ]
        return (optimized_lines, True)

    # *257
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(257|0x101),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}',
                f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
                f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
                f'{match.group(1)}clr.b {match.group(3)}{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *258
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(258|0x102),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *260
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(260|0x104),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *264
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(264|0x108),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *272
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(272|0x110),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *288
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(288|0x120),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *304
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(304|0x130),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *320
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(320|0x140),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *384
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(384|0x180),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *400
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(400|0x190),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *416
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(416|0x1A0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *480
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(480|0x1E0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *512
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(512|0x200),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}',
            f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
            f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
            f'{match.group(1)}clr.b {match.group(3)}{dN}',
            f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
        ]
        return (optimized_lines, True)

    # *576
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(576|0x240),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *608
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(608|0x260),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#5,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *624
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(624|0x270),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *625
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(625|0x271),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *640
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(640|0x280),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *768
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(768|0x300),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}'
                f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
                f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
                f'{match.group(1)}clr.b {match.group(3)}{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *896
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(896|0x380),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *960
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(960|0x3C0),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#6,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *1024
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(1024|0x400),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}',
            f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
            f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
            f'{match.group(1)}clr.b {match.group(3)}{dN}',
            f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
            f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
        ]
        return (optimized_lines, True)

    # *1280
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(1280|0x500),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}' replaced by next:
                f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
                f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
                f'{match.group(1)}clr.b {match.group(3)}{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *1920    ; Saves 8 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(1920|0x780),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}lsl.w {match.group(3)}#4,{dN}',
                f'{match.group(1)}sub.w {match.group(3)}{dM},{dN}',
                f'{match.group(1)}lsl.w {match.group(3)}#7,{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *2048    ; Saves 12 cycles
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(2048|0x800),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        optimized_lines = [
            #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}', replaced by next:
            f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
            f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
            f'{match.group(1)}clr.b {match.group(3)}{dN}',
            f'{match.group(1)}lsl.w {match.group(3)}#3,{dN}'
        ]
        return (optimized_lines, True)

    # *2560
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(2560|0xA00),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}', replaced by next:
                f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
                f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
                f'{match.group(1)}clr.b {match.group(3)}{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)

    # *3072
    match = re.match(r'^(\s*)(mulu\.w)(\s+)#(3072|0xC00),(\s*)(%d[0-7])', line)
    if match:
        dN = match.group(6)
        dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                #f'{match.group(1)}lsl.w {match.group(3)}#8,{dN}', replaced by next:
                f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
                f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
                f'{match.group(1)}clr.b {match.group(3)}{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w {match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)
        return ([], False)
    
    return ([], False)

# Export decorated functions and classes
__all__ = _PUBLIC_FUNCS_AND_CLASSES