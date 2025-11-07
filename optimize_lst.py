# --------------------------------------------------------------------
# Copyright (c) 2025 fabri1983
# Author: fabri1983
# fabri1983@gmail.com
#
# Gcc's gas assembly optimizer for cpu m68000.
#
# This script processes assembly output in gas syntax generated at the PLUGIN_FINISH phase.
# It searches for known single and multi line patterns that can be turned on into peephole 
# optimizations, and for multi line patterns produced by gcc that are not precisely optimized.
#
# The functions provided here in search for a free register can't see the entirity of the 
# context as they follow branches/jumps in a constrained way, hence might incur in new bugs 
# if the candidate free register turns out to be not free in a more complex code flow. 
# In addition, attempts to push/pop the register into the stack are considered to keep 
# trashed regs saved before returning from the routine.
#
# Some optimizations may leave the CCR flags in a different state than the original immediate 
# instruction was expecting, therefor may incur in new bugs.
# 
# Test your game thoroughly not only in emulators but also in real hardware.
#
# DISCLAIMER.
# This script is provided "as is" without warranty of any kind.
# You are free to use and modify this code, but please notify the author of any 
# modification, improvement, and bug you found.
# USE AT YOUR OWN RISK.
# --------------------------------------------------------------------

# Sources:
# (IMPLEMENTED) https://gist.github.com/flamewing/ad17bf22875be36ad4ae26f159a94f8b
# (IMPLEMENTED) http://www.easy68k.com/paulrsm/doc/asp68k6.txt
# (IMPLEMENTED) http://preserve.mactech.com/articles/mactech/Vol.08/08.02/Efficient68000/index.html
# (IMPLEMENTED) http://www.easy68k.com/paulrsm/doc/trick68k.htm
# (IMPLEMENTED) https://wiki.neogeodev.org/index.php?title=Optimization
# (IMPLEMENTED) http://www.ibaug.de/vasm/doc/vasm.pdf
# (IMPLEMENTED) http://www.csua.berkeley.edu/~muchandr/m68k
# Custom patterns found from gcc -S outputs

# Mnemocis equivalence
# ------------------
# gcc -S   |   M68k
# ------------------
# dbra     |   dbf
# jeq      |   beq
# jne      |   bne
# jgt      |   bgt
# jge      |   bge
# jlt      |   blt
# jle      |   ble
# jhi      |   bhi
# jhs/jcc  |   bhs/bcc
# jlo/jcs  |   blo/bcs
# jls      |   bls
# jmi      |   bmi
# jpl      |   bpl
# jvs      |   bvs
# jvc      |   bvc
# jra      |   bra
# -----------------

import sys
import operator
import re
from dataclasses import dataclass, field
from typing import List
try:
    from colorama import Fore, Back, Style, init
    # Initialize colorama (auto-detects Windows and enables ANSI).
    init()
except ImportError:
    print("ERROR: Please install Colorama module with 'pip install colorama'")
    exit(1)

# NOT_WORKING
# Those lines in this script marked with NOT_WORKING keyword are mean to be skipped from optimization.
# They produce errors in Blastem emulator.

# Set to False if you don't want to persist the optimizations into output file. 
# Use in conjunction with PRINT_OPTIMIZATION_LOG to print the findings as candidates.
SAVE_OPTIMIZATIONS = True

# Set to False to turn off printing of every pattern applied.
PRINT_OPTIMIZATION_LOG = True

# Which format do you like the most to print the logs? Columns or single line?
PRINT_LOG_IN_TWO_COLUMNS_FASHION = True

# If False then inlined asm blocks won't be optimized, which is good because they're probably already optimized by the user.
OPTIMIZE_INLINE_ASM_BLOCKS = False
# In case you want to optimize inline asm blocks but certain instructions must be ommited from optimization,
# then put this text at the end of the instruction:
SKIP_OPTIMIZATION_FLAG = ";# DO_NOT_OPTIMIZE"
# There is also the possibility to manually mark any inline asm block to be always optimized:
# surround the block with "\n#NO_APP\n\t" and "\n#APP"

# WARNING: As I don't use a proper graph structure for corrrect flow analysis, some optimizations might incurr in errors.
# If this flag is set to False then it skips the weak flow analysis, but lot of optimizations will be skipped too.
# This acts as a master switch to all methods that perform any kind of flow analysis.
USE_WEAK_FLOW_ANALYSIS = True

# Analyzes the context of the routine to detect free regs that were actually used but are free to use at 
# the line the analyzer is looking at.
# Depends also on USE_WEAK_FLOW_ANALYSIS flag.
USE_FIND_FREE_AFTER_USE_REG_FUNCTION = True

# This refers to the function that search for a new free reg not used at all in the context of a routine and 
# tye current program flow in that routine.
# WARNING: This may add overhead on push/pop from stack instructions that kills any gain given by the optimized line/s.
# Depends also on USE_WEAK_FLOW_ANALYSIS flag.
USE_FIND_FREE_REG_FUNCTION = True

# By default if current routine is not and interrupt routine AND regs are scratch pad THEN naturally there is
# no need to add them into push/pop in/from stack.
# In any other case we must add them, and that's where this flag enables/disables this functionality.
# Depends also on USE_WEAK_FLOW_ANALYSIS flag.
USE_ADD_REGS_INTO_PUSH_POP_FUNCTION = False  # TODO: glitches appear in Blastem

# Custom optimizations found from the analyzis of gcc -S listings.
USE_FABRI1983_MOVEM_OPTIMIZATIONS = True
USE_FABRI1983_OPTIMIZATIONS = True

# Set to True if you want to allow the use of TAS instruction with mapped I/O memory.
# This is risky if the mapped memory points to read-only memory (ie: a device).
# I assume SGDK does not generate instructions that write into read-only mapped I/O memory, so is safe to use TAS.
USE_TAS_ON_MAPPED_IO_MEMORY_OPTIMIZATION = True

# Set to True if the high word of result is important. Otherwise False.
OPTIMIZE_MULTIPLICATION_HIGH_WORD_IMPORTANT = True
OPTIMIZE_MULTIPLICATION_HIGH_WORD_NOT_IMPORTANT = not OPTIMIZE_MULTIPLICATION_HIGH_WORD_IMPORTANT

# Set to True if the reminder (located at high word) is not needed.
# Set to False if OPTIMIZE_INLINE_ASM_BLOCKS=True AND you use at least one of SGDK maths.c functions: 
#   modu(), mods(), divmodu(), divmods().
OPTIMIZE_DIVISION_HIGH_WORD_NOT_IMPORTANT = False

# Set to True if you want to replace tst+bcc by dbcc.
# Used in conjunction with a method that checks if the affected data register is not needed aftwewards.
USE_TST_BCC_BY_DBCC_OPTIMIZATION = True

# Set to True only if you know before hand the upper word won't be affected, 
# which is true for loops (TODO: but I don't check if inside a loop, yet).
# Note: VASM compiler seems to do this optimization by default (as per documentation).
USE_ADDQL_SUBQL_BY_ADDQW_SUBQW_OPTIMIZATION = True

# This optimizaton removes the clearing of a register before it is loaded with a word value.
# WARNING: Enabling this flag may cause unexpected side effects. Test thoroughly.
USE_AGGRESSIVE_AVOID_CLEAR_BEFORE_MOVE_WORD_INTO_DN = True

# This optimization modifies the way gcc pushes word registers into stack.
# WARNING: Enabling this flag may cause unexpected side effects. Test thoroughly.
USE_AGGRESSIVE_COMPACT_TWO_WORDS_PUSH_INTO_STACK = True

# This optimization modifies the way gcc clears the stack.
# WARNING: Enabling this flag may cause unexpected side effects. Test thoroughly.
USE_AGGRESSIVE_CLR_SP_OPTIMIZATION = False

# This is not an optimization per sé. It replaces dN.l by dN.w on indirect addressing.
# It might help some optimizations (currently not implemented) to change instruction size .l by .w, thus saving 4 cycles.
# WARNING: in certain code scenarios this produce glitches. Test thoroughly.
USE_AGGRESSIVE_REPLACE_LONG_INDIRECT_ADDRESSING_BY_WORD = False

MULTIPLE_LINES_OPTIMIZATION_LIMIT = 6

def print_optimized_diff(original_lines, i_line, optimized_lines):
    """
    Prints the original and optimized lines in two columns fashion or in one single line.
    """
    if not original_lines or not optimized_lines:
        return

    # After the 1st line is printed with the log info, we need to compensate all the space at left needed for upcoming lines
    left_padding_from_log = ''

    # Logging line info
    log = ''
    if not SAVE_OPTIMIZATIONS:
        log = f'{Fore.GREEN}[CANDIDATE at {(i_line+1):5d}]{Style.RESET_ALL}'
        left_padding_from_log = " " * (20 + 1)
    else:
        log = f'{Style.BRIGHT}{Fore.GREEN}[OPTIMIZED at {(i_line+1):5d}]{Style.RESET_ALL}'
        left_padding_from_log = " " * (20 + 1)

    if not PRINT_LOG_IN_TWO_COLUMNS_FASHION:
        original_joined = " / ".join(lineOrig.lstrip() for lineOrig in original_lines)
        optimized_joined = " / ".join(lineOpt.lstrip() for lineOpt in optimized_lines)
        print(f'{log} {original_joined}  ->  {optimized_joined}')
        return;

    # Calculate the maximum width for the first column
    max_width_1st_column = max(len(line.lstrip()) for line in original_lines)
    # Then calculate max with the min column width. 
    # This will print consistent column width accross all the optimizations, except in some extreme long lines (not likely)
    max_width_1st_column = max(max_width_1st_column, 26)

    # Create the formatted output
    output_lines = []
    max_lines = max(len(original_lines), len(optimized_lines))

    for i in range(max_lines):
        orig_line = original_lines[i].lstrip() if i < len(original_lines) else ""
        opt_line = optimized_lines[i].lstrip() if i < len(optimized_lines) else ""

        if i == 0:
            # First line with arrow
            output_lines.append(f"{orig_line:<{max_width_1st_column}}  ->   {opt_line}")
        else:
            # Subsequent lines without arrow, just aligned
            output_lines.append(f"{left_padding_from_log}{orig_line:<{max_width_1st_column+1}}      {opt_line}")

    # Join all lines with newlines
    formatted_output = "\n".join(output_lines)

    print(f'{log} {formatted_output}')

scratch_pad = ('%d0', '%d1', '%a0', '%a1')

# Set of comment prefixes commonly used at the start of a line
COMMENT_PREFIX_CHAR = {';', '*', '#', '|', '/'}

# Set of compiler info strings
compilerInfoEntries = {
    ".align", ".ascii", ".asciz", ".balign", ".balignw", ".balignl", 
    ".bss", ".comm", ".data", ".even", ".extern", ".file", ".globl", 
    ".hidden", ".ident", ".lcomm", ".lflags", ".local", ".section", ".size", 
    ".string", ".swbeg", ".text", ".type", ".weak", ".zero", ".zerofill"
}

def containsCompilerInfo(line):
    """
    Check if the line starts with any compiler info entry.
    """
    first_word = line.lstrip().split(None, 1)[0] if line.lstrip() else ""
    return first_word in compilerInfoEntries

# Set of compiler info strings
compilerDirectiveEntries = {
    ".byte", ".word", ".long", "dc.b", "dc.w", "dc.l", "ds.b", "ds.w", "ds.l", 
    ".if", ".endif", ".macro", ".endm", ".rept", ".irept", ".endr", ".set"
}

def containsCompilerDirective(line):
    """
    Check if the line starts with any compiler info entry.
    """
    first_word = line.lstrip().split(None, 1)[0] if line.lstrip() else ""
    return first_word in compilerDirectiveEntries

def isValue(s):
    """
    Check if a string is a valid number: integer, hexadecimal, binary.
    """
    s = s.strip()
    if not s:
        return False

    try:
        int(s)
        return True
    except ValueError:
        pass

    if s.startswith(('0x','0X','$')):
        return True

    if s.startswith(('0b','0B','%')):
        return True

    return False

def parseConstantUnsigned(value):
    """
    Convert a string constant to an integer.
    Handles decimal, hexadecimal (0x, $), and binary (0b, %).

    Parameters:
        value (str): The constant as a string.

    Returns:
        int: Unsigned integer interpretation.
             Otherwise Signed integer for decimal representation
    """
    if value.startswith(('0x','0X','$')):
        return int(value[2:], 16)
    elif value.startswith(('0b','0B','%')):
        return int(value[2:], 2)
    else:
        return int(value)

def parseConstantSigned(value, bit_depth=32):
    """
    Convert a string constant to a signed integer of the specified bit depth.
    Handles decimal, hexadecimal (0x, $), and binary (0b, %).

    Parameters:
        value (str): The constant as a string.
        bit_depth (int): Number of bits (8, 16, 32). Default is 32.

    Returns:
        int: Signed integer interpretation within the given bit depth.
    """
    if value.startswith(('0x','0X','$')):
        result = int(value[2:], 16)
    elif value.startswith(('0b','0B','%')):
        result = int(value[2:], 2)
    else:
        # Just return the integer conversion of the decimal
        return int(value)

    # Two's complement interpretation for signed values
    signed_threshold = 1 << (bit_depth - 1)
    max_unsigned = (1 << bit_depth) - 1

    #if result > max_unsigned:
    #    raise ValueError(f"Value {result} does not fit in {bit_depth} bits")

    if result >= signed_threshold:
        result -= (1 << bit_depth)

    return result

def find_bset_bit(n):
    """
    Finds the only bit position 'b' at which is 1.
    Returns None if 'n' is not a valid single-bit mask.
    """
    if n == 0:
        return None  # No bits set
    
    # Check if 'n' has exactly one 1 bit
    if (n & (n - 1)) != 0:
        return None  # More than one bit is set
    
    # Find the position of the single 1 bit
    b = 0
    temp = n
    while temp != 1:
        temp >>= 1
        b += 1
    return b

def find_bclr_bit(n):
    return find_bset_bit(~n)  # NOT n

# Set of mapings valid only for move.l #n optimizations
n_to_m = {
    -32881: -113,
    -32849: -81,
    -32817: -49,
    -32785: -17,
    -16498: -114,
    -16466: -82,
    -16434: -50,
    -16402: -18,
    -8307: -115,
    -8275: -83,
    -8243: -51,
    -8211: -19,
    -4212: -116,
    -4180: -84,
    -4148: -52,
    -4116: -20,
    -2165: -117,
    -2133: -85,
    -2101: -53,
    -2069: -21,
    -1142: -118,
    -1110: -86,
    -1078: -54,
    -1046: -22,
    -631: -119,
    -599: -87,
    -567: -55,
    -535: -23,
    -376: -120,
    -344: -88,
    -312: -56,
    -280: -24,
    264: 8,
    296: 40,
    328: 72,
    360: 104,
    521: 9,
    553: 41,
    585: 73,
    617: 105,
    1034: 10,
    1066: 42,
    1098: 74,
    1130: 106,
    2059: 11,
    2091: 43,
    2123: 75,
    2155: 107,
    4108: 12,
    4140: 44,
    4172: 76,
    4204: 108,
    8205: 13,
    8237: 45,
    8269: 77,
    8301: 109,
    16398: 14,
    16430: 46,
    16462: 78,
    16494: 110,
    32783: 15,
    32815: 47,
    32847: 79,
    32879: 111
}

def getMForMovelOptimization(n):
    return n_to_m.get(n, None)  # Returns None if n is not found

PUSH_REGS_INTO_STACK_REGEX = re.compile(r'^\s*(movem|move)\.([wl])\s+([^,]+),\s*-\(%sp\)')

POP_REGS_FROM_STACK_REGEX = re.compile(r'^\s*(movem|move)\.([wl])\s+\(%sp\)\+,\s*(.*)')

RANGE_REGS_REGEX = re.compile(r'(%[ad])([0-7])-(%[ad])([0-7])')
SINGLE_REG_REGEX = re.compile(r'(%[ad])([0-7])')

PUSH_OP = 1
POP_OP = 2

def sort_regs(regs):
    # First, separate the registers into data and address lists and sort them numerically
    data_regs = sorted([r for r in regs if r.startswith('%d')], key=lambda r: int(r[2:]))
    addr_regs = sorted([r for r in regs if r.startswith('%a')], key=lambda r: int(r[2:]))
    # Now merge them
    ordered_list = data_regs + addr_regs
    return ordered_list

def extract_registers(regs_encoded, operation_type):
    """
    Analyzes regs_encoded and returns the registers in the order they are transferred.
    Args:
        regs_encoded: The string containing the register list (eg: "d0-d7/a0-a6", "#49404")
        operation_type: PUSH_OP or POP_OP
    Returns:
        A list of ordered registers from smaller to higher, starting with data regs and then address regs.
    """
    if not regs_encoded:
        return []

    regs_set = set()

    # Check for immediate constant
    const_match = re.match(r'#(-?\d+)', regs_encoded)
    if const_match:
        value = parseConstantUnsigned(const_match.group(1))
        # Remember that regs are read from x7 to x0 when pushing into stack.
        # That's why GCC reverses the bits of the encoded value.
        if operation_type == PUSH_OP:
            # Extract the i-th bit and place it at the (15-i)-th position
            value = sum(((value >> i) & 1) << (15 - i) for i in range(16))
        # d0–d7 are bits 0–7
        for i in range(8):
            if value & (1 << i):
                regs_set.add(f'%d{i}')
        # a0–a7 are bits 8–15
        for i in range(8):
            if value & (1 << (8 + i)):
                regs_set.add(f'%a{i}')
    else:
        # Split into register groups (separated by /)
        for group in regs_encoded.split('/'):
            # Check for range (eg: d0-d3)
            range_match = RANGE_REGS_REGEX.fullmatch(group)
            if range_match:
                reg_type_start, start, reg_type_end, end = range_match.groups()
                start, end = int(start), int(end)
                if reg_type_start == reg_type_end:
                    regs_set.update(f"{reg_type_start}{n}" for n in range(start, end + 1))
            # Single register
            elif reg_match := SINGLE_REG_REGEX.fullmatch(group):
                reg_type, num = reg_match.groups()
                num = int(num)
                regs_set.add(f'{reg_type}{num}')

    ordered_list = sort_regs(regs_set)
    return ordered_list

FUNCTION_DECLARATION_REGEX = re.compile(
    r'^\s*'                # Optional leading whitespace
    r'\.type\s+'           # .type followed by at least one whitespace
    r'('                   # Start capturing group for function name
    r'[a-zA-Z_]'           # First character must be a letter or underscore
    r'[^,]*'               # Any word before a comma
    r')'                   # End capturing group for function name
    r',\s*@function'       # @function keyword
    # Eg:    .type    game_loop, @function
)
FUNCTION_SIZE_CALCULATION_REGEX = re.compile(
    r'^\s*'                # Optional leading whitespace
    r'\.size\s+'           # .size followed by at least one whitespace
    r'[a-zA-Z_]'           # First character must be a letter or underscore
    r'[^,]*'               # Any word before a comma
    r',\s*'                # Comma followed by optional whitespace
    r'\.-[a-zA-Z_]\w*'     # Size calculation
    # Eg:    .size    game_loop, .-game_loop
)
FUNCTION_EXIT_REGEX = re.compile(
    r'^\s*(rts|rte)\b'
)
INSTRUCTION_WITH_SIZE_REGEX = re.compile(
    r'^\s*(\w+)\.?([bwl])?\s+(?:.+);?$'  # Only capture instruction mnemonic and size .s
)
REG_AS_TARGET_REGEX = re.compile(
    r'^\s*'                          # Optional leading whitespace
    r'(?:'                           # Non-capturing group for target-writing instructions
    r'(?:abcd|add|and|asl|asr|bchg|bclr|bset|btst|cmp|div|eor|exg|lea|lsl|lsr|move|mul|nbcd|or|rol|ror|roxl|roxr|sbcd|sub)\S*'
    r')\b'                           # Word boundary
    r'[^,]*'                         # Everything up to a comma (source operands)
    r',\s*'                          # Comma and optional whitespace before destination
    r'(%[ad][0-7])\b'                # Target register
)
REG_AS_TARGET_ALONE_REGEX = re.compile(
    r'^\s*'                          # Optional leading whitespace
    r'(?:'                           # Non-capturing group for target-writing instructions
    r'(?:clr|ext|neg|negx|not|scc|scs|seq|sf|sge|sgt|shi|sle|sls|slt|smi|sne|spl|st|svc|svs|swap|tas|tst|unlk)\S*'
    r')\b'                           # Word boundary
    r'\s+'                           # Whitespace before destination
    r'(%[ad][0-7]);?$'               # Target register
)
# Conditional instructions except those dbcc
CONDITIONAL_CONTROL_FLOW_REGEX = re.compile(
    r'^\s*(bcc|bcs|beq|bge|bgt|bhi|bhs|ble|blo|bls|blt|bmi|bne|bpl|bvc|bvs|jcc|jcs|jeq|jge|jgt|jhi|jhs|jle|jlo|jls|jlt|jmi|jne|jpl|jvc|jvs)\s+([0-9a-zA-Z_\.]+)(\.[bwl])?;?$'
)
# Unconditional instructions. Considers cases like: label, symbolName, mem, (%aN). With optional .s
UNCONDITIONAL_CONTROL_FLOW_REGEX = re.compile(
    r'^\s*(jmp|bra|jra|bsr|jsr)\s+'
    r'(\()?'   # Optional '('
    r'(%?[0-9a-zA-Z_\.]+)(\.[bwl])?'
    r'(\))?'   # Optional ')'
    r';?$'
)
REG_AS_SOURCE_OR_INDIRECT_USE_REGEX = re.compile(
    r'\s+(%[ad][0-7]),'              # Source operand as " %xN,"
    r'|'  
    r'(%[ad][0-7])\.[bwl]\)'         # Indirect addressing register as "%xN.s)"
    r'|'  
    r'(%[ad][0-7])\)'                # Indirect addressing register as "%xN)"
    # Note that gcc might put the displacement like next: (d,aN/pc)   (d,aN/pc,xN.s)
)
REG_OVERWRITEN_OR_CLEARED_REGEX = re.compile(
    r'^\s*'                           # Optional leading whitespace
    r'(?:'                            # Non-capturing group for alternatives
        r'(move\S*|sub\S*|eor\S*)\b'  # Capture overwrite instructions
        r'([^,]*)'                    # Capture everything before comma
        r',\s*'                       # Comma and whitespace
        r'|'                          # OR
        r'(clr\S*)\b'                 # Clear instructions
        r'[^%]*'                      # Everything before register starting with %
    r')'                              # End alternatives
    r'(%[ad][0-7])\b'                 # Register being overwritten
)

# pea <value|symbolName>[.wl][+-*N][.bwl]
PEA_REGEX = re.compile(
    r'^\s*pea\s+(-?\d+|0[xX][0-9a-fA-F]+|[0-9a-zA-Z_\.]+)(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?'
)

# move.[wl] <#value|symbolName>[.wl][+-*N][.bwl],-(sp)
PUSH_OTHER_INTO_STACK_REGEX = re.compile(
    r'^\s*move\.([wl])\s+#?(-?\d+|0[xX][0-9a-fA-F]+|[0-9a-zA-Z_\.]+)(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?,\s*-\(%sp\)'
)

# Labels: 1:, .L37:, _loc1:, abcABC:, xlt_all.0:
LABEL_REGEX = re.compile(r'^\s*([0-9a-zA-Z_\.]+):$')

backward_number_labels = {'0b','1b','2b','3b','4b','5b','6b','7b','8b','9b'}
forward_number_labels = {'0f','1f','2f','3f','4f','5f','6f','7f','8f','9f'}
number_labels = {'0','1','2','3','4','5','6','7','8','9'}
                    
@dataclass
class ControlFlowPosInArray:
    """ Position in lines where the label is defined"""
    pos_in_lines: int = -1
    """ Position in modified_lines where the label is defined"""
    pos_in_modified_lines: int = -1
    """ Ordered list of lines positions where a label is called from"""
    inverted_for_lines: List[int] = field(default_factory=list)
    """ Ordered list of modified_lines positions where a label is called from"""
    inverted_for_modified_lines: List[int] = field(default_factory=list)

    def add_inverted_for_lines(self, value: int):
        if value not in self.inverted_for_lines:
            self.inverted_for_lines.append(value)
            self.inverted_for_lines.sort()
    
    def add_inverted_for_modified_lines(self, value: int):
        if value not in self.inverted_for_modified_lines:
            self.inverted_for_modified_lines.append(value)
            self.inverted_for_modified_lines.sort()

def build_control_flow_map(i_line, lines, modified_lines):
    """
    Builds a dictionary:
        {
            key: label,
            value: {
                pos_in_lines: int,
                pos_in_modified_lines: int,
                inverted_for_lines: List[int],
                inverted_for_modified_lines: List[int]
            }
        }
    to allow tracking of code flow from any jum/branh instruction.
    Returns: control_flow_dict to be accessed as:
        control_obj = control_flow_dict[label]
        control_obj.pos_in_lines
        control_obj.pos_in_modified_lines
        control_obj.inverted_for_lines
        control_obj.inverted_for_modified_lines
    """

    control_flow_dict = {}

    # Phase 1: collect all the labels and their line position

    # Scan backwards
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break condition
        if FUNCTION_DECLARATION_REGEX.match(line):
            break

        # Is a label definition?
        if match := LABEL_REGEX.match(line):
            label = match.group(1)
            # If it's a special label then treat it differently
            if label in number_labels:
                # This type of labels are not processed here but better in the method that needs flow control
                pass
            else:
                control_obj = ControlFlowPosInArray(pos_in_lines=-1, pos_in_modified_lines=i)
                control_flow_dict[label] = control_obj

    # Scan forwards
    rem_start = i_line + 1
    rem_end = len(lines)
    for i in range(rem_start, rem_end):
        line = lines[i]
        if line[0] == '#':
            continue

        # Break condition
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            break

        # Is a label definition?
        if match := LABEL_REGEX.match(line):
            label = match.group(1)
            # If it's a special label then treat it differently
            if label in ('0','1','2','3','4','5','6','7','8','9'):
                # This type of labels are not processed here but better in the method that needs flow control
                pass
            else:
                control_obj = ControlFlowPosInArray(pos_in_lines=i, pos_in_modified_lines=-1)
                control_flow_dict[label] = control_obj

    # Phase 2: create inverted indexes for every label used in bra/jra/jmp/bcc/jcc

    # Scan backwards
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break condition
        if FUNCTION_DECLARATION_REGEX.match(line):
            break

        # Any branch instruction (except dbcc)
        if match := CONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            label = match.group(2)
            if label in control_flow_dict:
                control_obj = control_flow_dict[label]
                control_obj.add_inverted_for_modified_lines(i)
        elif match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            label = match.group(3)
            if label in control_flow_dict:
                control_obj = control_flow_dict[label]
                control_obj.add_inverted_for_modified_lines(i)

    # Scan forwards
    rem_start = i_line + 1
    rem_end = len(lines)
    for i in range(rem_start, rem_end):
        line = lines[i]
        if line[0] == '#':
            continue

        # Break condition
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            break

        # Any branch instruction (except dbcc)
        if match := CONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            label = match.group(2)
            if label in control_flow_dict:
                control_obj = control_flow_dict[label]
                control_obj.add_inverted_for_modified_lines(i)
        elif match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            label = match.group(3)
            if label in control_flow_dict:
                control_obj = control_flow_dict[label]
                control_obj.add_inverted_for_modified_lines(i)

    return control_flow_dict

def in_an_interrupt_routine(i_line, lines, modified_lines):
    """
    Search over the lines in modified_lines array for a rte instruction, before the declaration of current function.
    Search over remaining lines in lines array for a rte instruction, before exiting the current function.
    """
    # Scan backwards
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue
        # Find function declaration
        if FUNCTION_DECLARATION_REGEX.match(line):
            return False
        # Found a rts/rte?
        if match := FUNCTION_EXIT_REGEX.match(line):
            # If instruciton is rte then we are inside an interrupt routine, otherwise is a simple routine
            return match.group(1) == 'rte'

    # Scan forwards
    rem_start = i_line + 1
    rem_end = len(lines)
    for i in range(rem_start, rem_end):
        line = lines[i]
        if line[0] == '#':
            continue
        # Exiting the routine declaration
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            return False
        # Found a rts/rte?
        if match := FUNCTION_EXIT_REGEX.match(line):
            # If instruciton is rte then we are inside an interrupt routine, otherwise is a simple routine
            return match.group(1) == 'rte'

    return False

def find_free_after_use_register(excludes, i_line, lines, modified_lines, reg_type):
    """
    Search for a free after use register xM:
    1. Search backwards over the lines in modified_lines array for a register xM, different 
       than any reg in excludes (might be empty or None), that is used as source or indirect 
       or target operand.
    2. Search forwards over the lines in lines array starting at i_line:
       - if xM is overwritten/cleared by a move, sub or eor itself, or clr, before is actually used in 
         remaining lines, then xM is free to use immediately.
       - If xM is not used as source operand nor in any indirection (in both source and target) 
         operand until a bra/jmp or new a function is reached, before xM is overwritten/cleared, 
         then xM is free to use immediately.
    Returns:
        ["%xM","%xP",...] or [None]
        Excluding %a7
    """

    # As I don't use a proper graph structure for corrrect flow analysis, it might incurr in errors.
    if not USE_WEAK_FLOW_ANALYSIS or not USE_FIND_FREE_AFTER_USE_REG_FUNCTION:
        return [None]

    # Bitmask tracking (7-0 = x7-x0)
    candidate_mask = 0
    exclude_indexes = (
        {} if not excludes  # Handle empty list
        else {int(xN[2]) for xN in excludes if xN.startswith(reg_type)}  # Extract digits from regs
    )

    # Phase 1: Scan recently instruction lines for all candidate registers (backwards scan)
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break conditions
        if FUNCTION_DECLARATION_REGEX.match(line):
            break

        # It's a source or indirect operand?
        if match := REG_AS_SOURCE_OR_INDIRECT_USE_REGEX.search(line):
            reg_str = next((g for g in (match.group(1), match.group(2), match.group(3)) if g), None)
            if reg_str is not None and reg_str.startswith(reg_type):
                reg_index = int(reg_str[2])  # Extract digit after '%x'
                if reg_index not in exclude_indexes:
                    candidate_mask |= 1 << reg_index  # Mark candidate as available
        # It's a target operand?
        elif match := REG_AS_TARGET_REGEX.match(line) or REG_AS_TARGET_ALONE_REGEX.match(line):
            if match.group(1).startswith(reg_type):
                reg_index = int(match.group(1)[2])  # Extract digit after '%x'
                if reg_index not in exclude_indexes:
                    candidate_mask |= 1 << reg_index  # Mark candidate as available

        # All registers available? Then no need to keep scanning
        if candidate_mask == 0xFF:
            break

    # No candidates? Then exit
    if candidate_mask == 0:
        return [None]

    control_flow_dict = build_control_flow_map(i_line, lines, modified_lines)
    control_visited = set()  # Helps to avoid looping infinitely 

    # Phase 2: Scan remaining lines and keep those candidate registers satisfying the rules (forwards scan)
    overwritten_or_cleared_mask = 0;
    used_before_overwritten_or_cleared_mask = 0;
    rem_start = i_line + 1
    rem_end = len(lines)
    i = rem_start
    while i < rem_end:  # forwards
        line = lines[i]
        i += 1

        if line[0] == '#':
            continue

        # Break condition
        # If exiting the routine declaration
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            break

        # If is an unconditional branch jmp/bra/bsr/jsr
        if match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            # Jumping into a routine?
            if match.group(1) in ('jsr', 'bsr'):
                # When jumping into a subroutine we must stop the analysis since we don't know 
                # whether the candidates will be effectively used in that routine
                candidate_mask = 0  # Mark all candidates as unavailable
                break
            elif match.group(1) in ('bra', 'jra', 'jmp'):
                # Get the target label (might be a function name which won't be in control_flow_dict)
                label = match.group(3)
                # Is tatget label a special one?
                if label in backward_number_labels or label in forward_number_labels:
                    if label[1] == 'b':
                        # As we are going forwards in lines array it means we have already analyzed the code in previous lines
                        continue
                    elif label[1] == 'f':
                        # Move forwards until we find where the label has been defined
                        while i < rem_end:
                            if match_label := LABEL_REGEX.match(lines[i]):
                                if match_label.group(1) == label:
                                    break
                            i += 1
                # Sometimes the label is a function name and the code comes with a jmp/bra.
                # Or could be (symbol_name) or (%aN) which are not considered labels.
                # Hence this element is not in the dictionary.
                elif label not in control_flow_dict:
                    # When jumping into a subroutine we must stop the analysis since we don't know 
                    # whether the candidates will be effectively used in that routine
                    candidate_mask = 0  # Mark all candidates as unavailable
                    break
                # Target label is in the dictionary AND was not yet visited
                elif label in control_flow_dict and label not in control_visited:
                    control_obj = control_flow_dict[label];
                    # Which array the destination line points to?
                    if control_obj.pos_in_lines != -1:
                        control_visited.add(label)  # Mark this label as visited
                        i = control_obj.pos_in_lines
                        continue
                    else:
                        # TODO
                        # We can only iterate over the current array we are iterating at (lines in this case),
                        # so we must stop here since we don't support iterating over modified_lines array starting
                        # at control_obj.pos_in_modified_lines
                        candidate_mask = 0  # Mark all candidates as unavailable
                        break

        # If is a conditional branch jcc/bcc (except dbcc)
        elif match := CONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            # TODO: follow the many paths the code could take
            pass

        # First check for overwrites/clears (if not used already)
        elif match := REG_OVERWRITEN_OR_CLEARED_REGEX.match(line):
            instr_move_or_sub_or_eor = match.group(1)  # move or sub or eor, or empty if matched with the clr
            src = match.group(2)  # source operand for move or sub or eor
            instr_clr = match.group(3)
            dest = match.group(4)  # reg being overwritten or cleared
            if dest and dest.startswith(reg_type):
                reg_index = int(dest[2])  # Extract digit after '%x'
                # Check reg is not one of the excluded and not used earlier
                if (reg_index not in exclude_indexes) and not (used_before_overwritten_or_cleared_mask & (1 << reg_index)):
                    # if matching sub or eor
                    if instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith(("sub","eor")):
                        # sub or eor itslef?
                        if src == dest:
                            overwritten_or_cleared_mask |= 1 << reg_index  # mark candidate as overwritten/cleared
                    # if matching move
                    elif instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith("move"):
                        overwritten_or_cleared_mask |= 1 << reg_index  # mark candidate as overwritten/cleared
                    # just matching the clr instruction
                    elif instr_clr is not None:
                        overwritten_or_cleared_mask |= 1 << reg_index  # mark candidate as overwritten/cleared
                    else:
                        # Instruction not considered?
                        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Instruction not considered: {line}")
        # Then check for register usage (if not overwritten/cleared already)
        elif match := REG_AS_SOURCE_OR_INDIRECT_USE_REGEX.match(line):
            reg_str = next((g for g in (match.group(1), match.group(2), match.group(3)) if g), None)
            if reg_str is not None and reg_str.startswith(reg_type):
                reg_index = int(reg_str[2])  # Extract digit after '%x'
                # Check reg is not one of the excluded and if not already overwritten/cleared
                if (reg_index not in exclude_indexes) and not (overwritten_or_cleared_mask & (1 << reg_index)):
                    used_before_overwritten_or_cleared_mask |= 1 << reg_index  # mark candidate as used before overwritten/cleared
                    candidate_mask &= ~(1 << reg_index)  # Mark candidate as unavailable

        # All candidates exhausted? Then exit loop
        if candidate_mask == 0:
            break

    # Return array of all available registers
    if candidate_mask:
        candidates = []
        while candidate_mask:
            first_set_bit = (candidate_mask & -candidate_mask).bit_length() - 1
            candidates.append(f'{reg_type}{first_set_bit}')
            candidate_mask &= candidate_mask - 1  # Clear the least significant set bit
        #print(f"{Fore.CYAN}[FREE AFTER USE REG FOUND]{Style.RESET_ALL} {candidates}")
        return candidates

    # No candidates? Then exit
    return [None]

def find_free_after_use_data_register(excludes, i_line, lines, modified_lines):
    return find_free_after_use_register(excludes, i_line, lines, modified_lines, "%d")

def find_free_after_use_address_register(excludes, i_line, lines, modified_lines):
    excludes.append("%a7")
    return find_free_after_use_register(excludes, i_line, lines, modified_lines, "%a")

def find_unused_register(excludes, i_line, lines, modified_lines, reg_type):
    """
    Search for a free register:
    1. Search backwards over the lines in modified_lines array for a register xM, different than 
       any reg in excludes, that is not used as source operand nor in any indirection (in both 
       source and target) operand nor as a target operand, until a declaration or ending of a function is reached.
       If reaching to a push into stack then ensure xM is being saved in the stack.
    Returns:
        "%xM" or None
        Excludes %a7 by default
    """

    # As I don't use a proper graph structure for corrrect flow analysis, it might incurr in errors.
    if not USE_WEAK_FLOW_ANALYSIS or not USE_FIND_FREE_REG_FUNCTION:
        return [None]

    # TODO: It lacks of flow control over lines array.
    # We need to know if there is code in lines array that jumps back into modified_lines array

    # Bitmask tracking (7-0 = x7-x0)
    # Initially we set all them as available
    candidate_mask = 0xFF
    exclude_indexes = (
        {} if not excludes  # Handle empty list
        else {int(xN[2]) for xN in excludes if xN.startswith(reg_type)}  # Extract digits from regs
    )

    # Set excluded indexes as not available candidates
    for reg_index in exclude_indexes:
        candidate_mask &= ~(1 << reg_index)  # Set reg_index as unavailable

    # Scan recently instruction lines for all candidate registers (backwards scan)
    used_as_source_or_indirect_or_target_mask = 0;
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):  # backwards
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break condition
        if FUNCTION_DECLARATION_REGEX.match(line):
            break

        # If reaching to a movem/move pushing into stack then continue with the loop.
        # THIS BEHAVIOR SEEMS USEFUL IN CASES WHERE THERE ARE ORPHAN REGISTERS and only remains its push into stack instruction
        if push_match := PUSH_REGS_INTO_STACK_REGEX.match(line):
            continue
            '''pushed_list = extract_registers(push_match.group(3), PUSH_OP)
            for item in pushed_list:
                if item.startswith(reg_type):
                    N = int(item[2])  # Extract the digit after '%x'
                    reg_index = int(N)
                    if reg_index not in exclude_indexes:
                        if not (used_as_source_or_indirect_or_target_mask & (1 << reg_index)):
                            candidate_mask |= (1 << reg_index)  # Mark candidate as available'''
        # It's a source or indirect operand?
        elif match := REG_AS_SOURCE_OR_INDIRECT_USE_REGEX.match(line):
            reg_str = next((g for g in (match.group(1), match.group(2), match.group(3)) if g), None)
            if reg_str is not None and reg_str.startswith(reg_type):
                reg_index = int(reg_str[2])  # Extract digit after '%x'
                if reg_index not in exclude_indexes:
                    used_as_source_or_indirect_or_target_mask |= 1 << reg_index  # Mark candidate as used
                    candidate_mask &= ~(1 << reg_index)  # Mark candidate as unavailable
        # It's a target operand?
        elif match := REG_AS_TARGET_REGEX.match(line) or REG_AS_TARGET_ALONE_REGEX.match(line):
            if match.group(1).startswith(reg_type):
                reg_index = int(match.group(1)[2])  # Extract digit after '%x'
                if reg_index not in exclude_indexes:
                    used_as_source_or_indirect_or_target_mask |= 1 << reg_index  # Mark candidate as used
                    candidate_mask &= ~(1 << reg_index)  # Mark candidate as unavailable

    # Return array of all available registers
    if candidate_mask:
        candidates = []
        while candidate_mask:
            first_set_bit = (candidate_mask & -candidate_mask).bit_length() - 1
            candidates.append(f'{reg_type}{first_set_bit}')
            candidate_mask &= candidate_mask - 1  # Clear the least significant set bit
        #print(f"{Fore.CYAN}[FREE REG FOUND]{Style.RESET_ALL} {candidates}")
        return candidates

    # No candidates? Then exit
    #print(f"{Fore.YELLOW}[NO FREE REG FOUND]{Style.RESET_ALL} for:  {lines[i_line].lstrip()}")
    return [None]

def find_unused_data_register(excludes, i_line, lines, modified_lines):
    return find_unused_register(excludes, i_line, lines, modified_lines, "%d")

def find_unused_address_register(excludes, i_line, lines, modified_lines):
    excludes.append("%a7")
    return find_unused_register(excludes, i_line, lines, modified_lines, "%a")

def in_a_SGDK_sound_related_routine(modified_lines):
    """
    Search backwards up to the function declaration to see if we are in any of next type of routines:
        Z80_xxx, XGM_xxx, XGM2_xxx, SND_xxx
    """
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue
        # Found a function declaration?
        if match := FUNCTION_DECLARATION_REGEX.match(line):
            return match.group(1).startswith(('Z80_','XGM_','XGM2_','SND_','PSG_','YM2612_'))

    return False

def get_routine_first_instruction_pos(modified_lines):
    """
    Search for the first instruction in the routine. The one next to the label with same routine name.
    """
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break conditions
        if match_func := FUNCTION_DECLARATION_REGEX.match(line):
            label = match_func.group(1)
            # Move forwards until we find where the label is defined
            k = i + 1
            k_end = len(modified_lines)
            while k < k_end:
                if match_label := LABEL_REGEX.match(modified_lines[k]):
                    if match_label.group(1) == label:
                        # First instruction is at next position
                        return k + 1
                k += 1

    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Couldn't find first instruction in routine")
    return (2**31) - 1

def add_line_with_push_regs_into_stack(regs, modified_lines, inAnInterruptRoutine, routine_first_instruction_pos):
    """
    Starting at routine_first_instruction_pos, keep track of the last line where sp is used, 
    but not a modififcation of where it points to.
    Stop searching at one of next patterns:
       -(sp) or (sp)+
       add*/sub* #disp,sp
       lea disp(sp),sp
    """

    last_sp_usage_line = routine_first_instruction_pos
    # Forwards scan in modified_lines
    for k in range(routine_first_instruction_pos, len(modified_lines)):
        line = modified_lines[k]
        if line[0] == '#':
            continue

        # Break conditions
        if FUNCTION_DECLARATION_REGEX.match(line) or FUNCTION_EXIT_REGEX.match():
            break

        # Check for next sp usage patterns:
        #   -(sp) or (sp)+
        #   add*/sub* #disp,sp
        #   lea disp(sp),sp
        if re.search(r'-\(%sp\)', line) or re.search(r'\(%sp\)\+', line) or re.search(r'#.*%sp', line) or re.match(r'^\s*lea\+(?:-?\d+\(%sp\)|\(-?\d+,%sp\)),\s*%sp', line):
            break

        # Check for any other sp usage like: move.l reg,(sp) or move.w 4(sp),reg
        if re.search(r'%sp', line):
            # sp is used in a way that interferes with the push, so next line should be fine
            last_sp_usage_line = k+1

    # If sp wasn't used we can add the new line/s just at i+2.
    # If sp was used, then add the new line/s after that last line it was used.
    # If len(regs) < 3 then use move instructions. Otherwise movem.
    new_lines = []
    sortedRegs = sort_regs(regs_list)
    if len(regs) < 3:
        new_lines.extend(f'\tmove.l {reg},-(%sp)' for reg in sortedRegs)
    else:
        # Rebuild register list using '/' as separator
        newRegs_str = '/'.join(sortedRegs)
        new_lines.append(f'\tmovem.l {newRegs_str},-(%sp)')

    # Insert elements in reverse order to maintain correct order
    for elem in reversed(new_lines):
        modified_lines.insert(last_sp_usage_line, elem)

def replace_xN_by_xM_in_next_lines(xN, xM, i_line, lines, modified_lines):
    """
    Replace any usage of xN register by xM register.
    Special handling is considered in movem/move push/pop instructions if xM is not covered.
    1. Search over the remaining lines in lines array starting at i_line+1 and save those
       indices of lines who satisfy next:
       - xN is used as source operand or in any indirection (in both source and target) operand.
       - xN is in the list (or range) of a pop stack registers operation.
       Break condition is met when a rts/rte/bra/jbra/jmp is reached, or xN is overwritten/cleared 
       by a move, sub or eor itself, or clr.
    2. Visit lines pointed by the indices collected before, and replace xN by xM.
       If the visited line pops registers from the stack then ensure xM is in the list or range, 
       otherwise update the movem/move to include it.
    3. Search over recently added lines in modified_lines, for the movem/move push/pop instruction and 
       add xM reg if not already in push list, and replace xN by xM in pop list.
    """

    # Detect if we are in an interrupt routine
    inAnInterruptRoutine = in_an_interrupt_routine(i_line, lines, modified_lines)

    # Phase 1: Collect lines that use xN in relevant contexts (forwards scan)
    collected_indices = []
    xN_overwritten_or_cleared = False
    rem_start = i_line + 1
    rem_end = len(lines)
    for i in range(rem_start, rem_end):
        line = lines[i]
        if line[0] == '#':
            continue

        # End this routine body?
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            break
        # If only specific unconditional flow is met then stop
        if match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            if match.group(1) in ('bra','jra','jmp'):
                break

        # If xN was overwritten or cleared then process only lines that movem/move pops xN (if any)
        if xN_overwritten_or_cleared:
            pop_match = POP_REGS_FROM_STACK_REGEX.match(line)
            if pop_match and xN in extract_registers(pop_match.group(3), POP_OP):
                collected_indices.append(i)
            continue
        else:
            # Check for overwrites/clears (if not used already)
            if match := REG_OVERWRITEN_OR_CLEARED_REGEX.match(line):
                instr_move_or_sub_or_eor = match.group(1)  # move or sub or eor, or empty if matched with the clr
                src = match.group(2)  # source operand for move or sub or eor
                instr_clr = match.group(3)
                dest = match.group(4)  # reg being overwritten or cleared
                if dest:
                    # if matching sub or eor
                    if instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith(("sub","eor")):
                        # sub or eor itslef?
                        if src == dest and xN == dest:
                            xN_overwritten_or_cleared = True
                            # We have to continue visiting lines until a movem/move pops the xN register
                            continue
                    # if matching move
                    elif instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith("move"):
                        if xN == dest:
                            xN_overwritten_or_cleared = True
                            # We have to continue visiting lines until a movem/move pops the xN register
                            continue
                    # just matching the clr instruction
                    elif instr_clr is not None and xN == dest:
                        xN_overwritten_or_cleared = True
                        # We have to continue visiting lines until a movem/move pops the xN register
                        continue

            # Check for register usage and collect the line index
            if match := REG_AS_SOURCE_OR_INDIRECT_USE_REGEX.match(line):
                reg_str = next((g for g in (match.group(1), match.group(2), match.group(3)) if g), None)
                if reg_str is not None and xN == reg_str:
                    collected_indices.append(i)
            # Is it a movem/move pop for xN?
            elif pop_match := POP_REGS_FROM_STACK_REGEX.match(line):
                if xN in extract_registers(pop_match.group(3), POP_OP):
                    collected_indices.append(i)

    # Phase 2: Apply replacements
    was_xM_added_into_movem_or_move_pop = False
    for i in collected_indices:
        line = lines[i]

        # Is a movem/move pop instruction?
        if pop_match := POP_REGS_FROM_STACK_REGEX.match(line):
            # move
            if pop_match.group(1) == 'move':
                # If xM is not scratch pad, unless in an interrupt routine: then add it
                if inAnInterruptRoutine or (xM not in scratch_pad):
                    was_xM_added_into_movem_or_move_pop = True
                    # Simple text replacement of register name
                    lines[i] = re.sub(rf'\b{re.escape(xN)}\b', xM, line)
            # movem
            else:
                regs_str = pop_match.group(3)
                regs_list = extract_registers(regs_str, POP_OP)
                # If xM is not in the list already and is not scratch pad, unless in an interrupt routine: then add it
                if xM not in regs_list and (inAnInterruptRoutine or (xM not in scratch_pad)):
                    was_xM_added_into_movem_or_move_pop = True
                    # Replace xN by xM
                    index_xN = regs_list.index(xN)
                    regs_list[index_xN] = xM
                    sortedRegs = sort_regs(regs_list)
                    # Rebuild register list using '/' as separator
                    newRegs_str = '/'.join(sortedRegs)
                    lines[i] = line.replace(regs_str, newRegs_str)
        # General case
        else:
            # Simple text replacement of register name
            lines[i] = re.sub(rf'\b{re.escape(xN)}\b', xM, line)

    # Phase 3: Search for the movem/move push/pop instruction and add xM reg if not already there and replace xN by xM

    # Search for the first instruction in the routine
    routine_first_instruction_pos = get_routine_first_instruction_pos(modified_lines)

    # Visit recently added lines in modified_lines (backwards scan)
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break conditions
        if FUNCTION_DECLARATION_REGEX.match(line):
            # Reaching here means xM was not added in an existing movem push, so we have to manually add it.
            if was_xM_added_into_movem_or_move_pop:
                add_line_with_push_regs_into_stack([xM], modified_lines, inAnInterruptRoutine, routine_first_instruction_pos)
                # IMPORTANT: once we've added the new line into modified_lines we can't continue iterating over it
            break

        # Is a movem/move push instruction?
        if push_match := PUSH_REGS_INTO_STACK_REGEX.match(line):
            if was_xM_added_into_movem_or_move_pop:
                # movem
                if push_match.group(1) == 'movem':
                    regs_str = push_match.group(3)
                    regs_list = extract_registers(regs_str, PUSH_OP)
                    # If xM is not in the list already and is not scratch pad, unless in an interrupt routine: then add it
                    if xM not in regs_list and (inAnInterruptRoutine or (xM not in scratch_pad)):
                        regs_list.append(xM)
                        sortedRegs = sort_regs(regs_list)
                        # Rebuild register list using '/' as separator
                        newRegs_str = '/'.join(sortedRegs[::-1])  # reverse the list of regs
                        modified_lines[i] = line.replace(regs_str, newRegs_str)
                    # There is only one movem push which is at the beginning of the routine
                    break

        # Is it a movem/move pop for xN?
        if pop_match := POP_REGS_FROM_STACK_REGEX.match(line):
            if xN in extract_registers(pop_match.group(3), POP_OP):
                # move
                if pop_match.group(1) == 'move':
                    # If xM is not scratch pad, unless in an interrupt routine: then add it
                    if inAnInterruptRoutine or (xM not in scratch_pad):
                        was_xM_added_into_movem_or_move_pop = True
                        # Simple text replacement of register name
                        modified_lines[i] = re.sub(rf'\b{re.escape(xN)}\b', xM, line)
                # movem
                else:
                    regs_str = pop_match.group(3)
                    regs_list = extract_registers(regs_str, POP_OP)
                    # If xM is not in the list already and is not scratch pad, unless in an interrupt routine: then add it
                    if xM not in regs_list and (inAnInterruptRoutine or (xM not in scratch_pad)):
                        was_xM_added_into_movem_or_move_pop = True
                        # Replace xN by xM
                        index_xN = regs_list.index(xN)
                        regs_list[index_xN] = xM
                        sortedRegs = sort_regs(regs_list)
                        # Rebuild register list using '/' as separator
                        newRegs_str = '/'.join(sortedRegs)
                        modified_lines[i] = line.replace(regs_str, newRegs_str)

def get_line_where_reg_is_used_before_being_overwritten_or_cleared_afterwards(xN, i_line, lines, modified_lines, checkTargetOperand):
    """
    Search over the remaining lines in lines array starting at i_line+1 for one of next conditions:
    - xN is used as source operand or in any indirection (in both source and target) operand:
      Returns the line content.
    - if checkTargetOperand==True: if xN is used as a target (but not being actually overwritten/cleared):
      Returns the line content.
    - xN is overwritten/cleared by a move, sub or eor itself, or clr, before is being used:
      Returns None.
    - Control flow jmp/bra/jsr is reached or exiting current routine declaration:
      Returns None.
    """

    control_flow_dict = build_control_flow_map(i_line, lines, modified_lines)
    control_visited = set()  # Helps to avoid looping infinitely 

    rem_start = i_line + 1
    rem_end = len(lines)
    i = rem_start
    while i < rem_end:  # forwards
        line = lines[i]
        i += 1
        if line[0] == '#':
            continue

        # Exiting the routine declaration?
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            return None

        if match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            # Jumping into a routine?
            if match.group(1) in ('jsr', 'bsr'):
                # When jumping into a subroutine we must stop the analysis since we don't know 
                # whether the register xN will be effectively used in that routine
                return None
            elif match.group(1) in ('bra', 'jra', 'jmp'):
                # Get the target label (might be a function name which won't be in control_flow_dict)
                label = match.group(3)
                # Is tatget label a special one?
                if label in backward_number_labels or label in forward_number_labels:
                    if label[1] == 'b':
                        # As we are going forwards in lines array it means we have already analyzed the code in previous lines
                        continue
                    elif label[1] == 'f':
                        # Move forwards until we find where the label has been defined
                        while i < rem_end:
                            if match_label := LABEL_REGEX.match(lines[i]):
                                if match_label.group(1) == label:
                                    break
                            i += 1
                # Sometimes the label is a function name and the code comes with a jmp/bra.
                # Or could be (symbol_name) or (%aN) which are not considered labels.
                # Hence this element is not in the dictionary.
                elif label not in control_flow_dict:
                    # When jumping into a subroutine we must stop the analysis since we don't know 
                    # whether the register xN will be effectively used in that routine
                    return None
                # Target label is in the dictionary AND was not yet visited
                elif label in control_flow_dict and label not in control_visited:
                    control_obj = control_flow_dict[label];
                    # Which array the destination line points to?
                    if control_obj.pos_in_lines != -1:
                        control_visited.add(label)  # Mark this label as visited
                        i = control_obj.pos_in_lines
                        continue
                    else:
                        # TODO
                        # We can only iterate over the current array we are iterating at (lines in this case),
                        # so we must stop here since we don't support iterating over modified_lines array starting
                        # at control_obj.pos_in_modified_lines
                        return None

        # If is a conditional branch jcc/bcc (except dbcc)
        elif match := CONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            # TODO: follow the many paths the code could take
            pass

        # xN is overwritten/cleared by a move, sub or eor itself, or clr
        elif match := REG_OVERWRITEN_OR_CLEARED_REGEX.match(line):
            instr_move_or_sub_or_eor = match.group(1)  # move or sub or eor, or empty if matched with the clr
            src = match.group(2)  # source operand for move or sub or eor
            instr_clr = match.group(3)
            dest = match.group(4)  # reg being overwritten or cleared
            if dest:
                # if matching sub or eor
                if instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith(("sub","eor")):
                    # sub or eor itslef?
                    if src == dest and xN == dest:
                        return None
                # if matching move
                elif instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith("move"):
                    if xN == dest:
                        return None
                # just matching the clr instruction
                elif instr_clr is not None and xN == dest:
                    return None

        # xN is used as source operand or in any indirection (in both source and target) operand
        elif match := REG_AS_SOURCE_OR_INDIRECT_USE_REGEX.match(line):
            reg_str = next((g for g in (match.group(1), match.group(2), match.group(3)) if g), None)
            if reg_str is not None and xN == reg_str:
                return line
        # xN it's a target operand?
        elif checkTargetOperand:
            if match := REG_AS_TARGET_REGEX.match(line) or REG_AS_TARGET_ALONE_REGEX.match(line):
                if xN == match.group(1):
                    return line

    return None

def is_reg_used_before_being_overwritten_or_cleared_afterwards(xN, i_line, lines, modified_lines):

    # As I don't use a proper graph structure for corrrect flow analysis, it might incurr in errors.
    if not USE_WEAK_FLOW_ANALYSIS:
        return True

    checkTargetOperand = False
    matching_line = get_line_where_reg_is_used_before_being_overwritten_or_cleared_afterwards(xN, i_line, lines, modified_lines, checkTargetOperand)
    return matching_line is not None

def is_reg_used_as_word_or_byte_afterwards(xN, i_line, lines, modified_lines):

    # As I don't use a proper graph structure for corrrect flow analysis, it might incurr in errors.
    if not USE_WEAK_FLOW_ANALYSIS:
        return False

    checkTargetOperand = True
    matching_line = get_line_where_reg_is_used_before_being_overwritten_or_cleared_afterwards(xN, i_line, lines, modified_lines, checkTargetOperand)
    if matching_line is None:
        return False

    # Let's check if the register is used in any indirection: 'xN.s)'
    if f'{xN}.b)' in matching_line or f'{xN}.w)' in matching_line:
        return True

    # Let's check for the instruction size
    match_instr_size = INSTRUCTION_WITH_SIZE_REGEX.match(matching_line)
    s = match_instr_size.group(2)
    if s is not None:
        return s in ('b','w')
    return False

def add_regs_into_push_pop_if_not_scratch_or_in_interrupt(regs, i_line, lines, modified_lines):
    """
    Add regs into movem/move push/pop. Ignore scratch regs if not in an interrupt routine.
    """
    if len(regs) == 0:
        return False

    # Detect if we are in an interrupt routine
    inAnInterruptRoutine = in_an_interrupt_routine(i_line, lines, modified_lines)

    # If we are not in an interrupt routine AND all the regs are scratch pad, 
    # then no need to add them into push/pop in/from stack
    if not inAnInterruptRoutine and all(reg in scratch_pad for reg in regs):
        return True

    # As I don't use a proper graph structure for corrrect flow analysis, it might incurr in errors.
    if not USE_WEAK_FLOW_ANALYSIS or not USE_ADD_REGS_INTO_PUSH_POP_FUNCTION:
        return False

    # Forwards scan
    regs_were_added_into_movem_pop = False
    rem_start = i_line + 1
    rem_end = len(lines)
    for i in range(rem_start, rem_end):
        line = lines[i]
        if line[0] == '#':
            continue

        # If reaching the end of the routine
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            if not regs_were_added_into_movem_pop:
                # Reaching here means regs were not added in an existing movem pop, so we have to manually add it.
                # TODO: add a new line in lines[i-1] with the movem pop of regs. BUT WE CAN'T EXPAND lines ARRAY.
                # THIS CONDITION IS ONLY USEFUL FOR PRINTING THE WARNING MESSAGE
                if inAnInterruptRoutine or not any(reg in scratch_pad for reg in regs):
                    print(f"{Fore.YELLOW}[WARNING at {(i_line+1):5d}]{Style.RESET_ALL} Can't add movem/move pop regs in lines array yet")
            break

        # Is a movem/move pop instruction?
        pop_match = POP_REGS_FROM_STACK_REGEX.match(line)
        if pop_match and 'movem' == pop_match.group(1):
            regs_str = pop_match.group(3)
            regs_list = extract_registers(regs_str, POP_OP)
            # Add only missing regs
            # Also, if the reg is scratch pad then discard it, unless we are in an interrupt routine
            regs_list.extend([reg for reg in regs if reg not in regs_list and (inAnInterruptRoutine or (reg not in scratch_pad))])
            sortedRegs = sort_regs(regs_list)
            # Rebuild register list using '/' as separator
            newRegs_str = '/'.join(sortedRegs)
            lines[i] = line.replace(regs_str, newRegs_str)
            regs_were_added_into_movem_pop = True
            # Continue searching for another movem pop since there could be more than one
            continue

    # Search for the first instruction in the routine
    routine_first_instruction_pos = get_routine_first_instruction_pos(modified_lines)

    # Backwards scan
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break conditions
        if FUNCTION_DECLARATION_REGEX.match(line):
            # Reaching here means regs were not added in an existing movem push, so we have to manually add it.
            if regs_were_added_into_movem_pop:
                add_line_with_push_regs_into_stack(regs, modified_lines, inAnInterruptRoutine, routine_first_instruction_pos)
                # IMPORTANT: once we've added the new line into modified_lines we can't continue iterating over it
            break

        # If it's a movem push near the function declaration then add the missing regs into the list
        push_match = PUSH_REGS_INTO_STACK_REGEX.match(line)
        if push_match and 'movem' == push_match.group(1) and abs(i - routine_first_instruction_pos) < 2:
            if regs_were_added_into_movem_pop:
                regs_str = push_match.group(3)
                regs_list = extract_registers(regs_str, PUSH_OP)
                # Add only missing regs
                # Also, if the reg is scratch pad then discard it, unless we are in an interrupt routine
                regs_list.extend([reg for reg in regs if reg not in regs_list and (inAnInterruptRoutine or (reg not in scratch_pad))])
                sortedRegs = sort_regs(regs_list)
                # Rebuild register list using '/' as separator
                newRegs_str = '/'.join(sortedRegs[::-1])  # reverse the list of regs
                modified_lines[i] = line.replace(regs_str, newRegs_str)
            # There is only one movem push at the beginning of the routine
            break

        # Is a movem/move pop instruction?
        pop_match = POP_REGS_FROM_STACK_REGEX.match(line)
        if pop_match and 'movem' == pop_match.group(1):
            regs_str = pop_match.group(3)
            regs_list = extract_registers(regs_str, POP_OP)
            # Add only missing regs
            # Also, if the reg is scratch pad then discard it, unless we are in an interrupt routine
            regs_list.extend([reg for reg in regs if reg not in regs_list and (inAnInterruptRoutine or (reg not in scratch_pad))])
            sortedRegs = sort_regs(regs_list)
            # Rebuild register list using '/' as separator
            newRegs_str = '/'.join(sortedRegs)
            modified_lines[i] = line.replace(regs_str, newRegs_str)
            regs_were_added_into_movem_pop = True
            # Continue searching for another movem pop since there could be more than one
            continue

    return True

def if_reg_not_used_anymore_then_remove_from_push_pop(xN, i_line, lines, modified_lines, ignore_N_previous_lines):
    """
    Search backwards and forwards for any usage of xN.
    Backwards scan:
        Iterate over modified_lines array starting at ignore_N_previous_lines lines from the end.
        If xN is used as target or as source operand or indirection operand, then xN is tagged as used.
    Forwards scan:
        Iterate over lines array starting at i_line + 1.
        If xN is used as target or as source operand or indirection operand, then xN is tagged as used.
    Conclusion:
        If no usage was found (without counting the push/pop into sp), then when reaching the 
        movem/move that pushes or pops xN we can safely remove xN from there.
        In case the movem/move ends empty:
            For lines array: replace the movem/move line by adding a # at the beginning of the 
            line so it is parsed as a comment, given that we can not alter the size of the array.
            For modified_lines: idem.
    """

    # As I don't use a proper graph structure for corrrect flow analysis, it might incurr in errors.
    if not USE_WEAK_FLOW_ANALYSIS:
        return

    # Backwards scan
    xN_used_backwards = False
    start_idx = (len(modified_lines) - 1) - (ignore_N_previous_lines - 1)
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        if line[0] == '#':
            continue

        # Break conditions
        if FUNCTION_DECLARATION_REGEX.match(line):
            break

        # If it's a movem/move push xN then exit the loop, it means we are at the begining of the routine
        push_match = PUSH_REGS_INTO_STACK_REGEX.match(line)
        if push_match and xN in extract_registers(push_match.group(3), PUSH_OP):
            # There is only one movem/move push xN which is at the beginning of the routine
            break

        # If it's a movem/move pop xN then we skip it since it means an exit block (likely) is 
        # set at this location of the routine instead of at the very end
        pop_match = POP_REGS_FROM_STACK_REGEX.match(line)
        if pop_match and xN in extract_registers(pop_match.group(3), POP_OP):
            # Continue searching. It might exist more than one movem/move pop xN
            continue

        # xN is used as source operand or in any indirection (in both source and target) operand
        if match := REG_AS_SOURCE_OR_INDIRECT_USE_REGEX.match(line):
            reg_str = next((g for g in (match.group(1), match.group(2), match.group(3)) if g), None)
            if reg_str is not None and xN == reg_str:
                xN_used_backwards = True
                break
        # It's a target operand?
        elif match := REG_AS_TARGET_REGEX.match(line) or REG_AS_TARGET_ALONE_REGEX.match(line):
            if xN == match.group(1):
                xN_used_backwards = True
                break

    # Forwards scan
    xN_used_forwards = False
    rem_start = i_line + 1
    rem_end = len(lines)
    for i in range(rem_start, rem_end):
        line = lines[i]
        if line[0] == '#':
            continue

        # End of this routine body?
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            break

        # If it's a movem/move pop xN then we skip it
        pop_match = POP_REGS_FROM_STACK_REGEX.match(line)
        if pop_match and xN in extract_registers(pop_match.group(3), POP_OP):
            # Continue searching. It might exist more than one movem/move pop xN
            continue

        # xN is used as source operand or in any indirection (in both source and target) operand
        if match := REG_AS_SOURCE_OR_INDIRECT_USE_REGEX.match(line):
            reg_str = next((g for g in (match.group(1), match.group(2), match.group(3)) if g), None)
            if reg_str is not None and xN == reg_str:
                xN_used_forwards = True
                break
        # It's a target operand?
        elif match := REG_AS_TARGET_REGEX.match(line) or REG_AS_TARGET_ALONE_REGEX.match(line):
            if xN == match.group(1):
                xN_used_forwards = True
                break

    # xN not used at all? Then remove it from movem/move push/pop
    if not xN_used_backwards and not xN_used_forwards:

        # Backwards scan
        start_idx = len(modified_lines) - 1
        end_idx = 0
        for i in range(start_idx, end_idx - 1, -1):
            line = modified_lines[i]
            if line[0] == '#':
                continue

            # End of this routine body?
            if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
                break

            push_match = PUSH_REGS_INTO_STACK_REGEX.match(line)
            if push_match and xN in extract_registers(push_match.group(3), PUSH_OP):
                # move
                if push_match.group(1) == 'move':
                    # Remove the move push by commenting the line (we can't modify the size of the array)
                    modified_lines[i] = '#' + line
                # movem
                else:
                    regs_str = push_match.group(3)
                    regs_list = extract_registers(regs_str, PUSH_OP)
                    # Remove xN
                    regs_list.remove(xN)
                    # If no regs to pop then comment the line
                    if len(regs_list) == 0:
                        modified_lines[i] = '#' + line
                    else:
                        sortedRegs = sort_regs(regs_list)
                        # Rebuild register list using '/' as separator
                        newRegs_str = '/'.join(sortedRegs[::-1])  # reverse the list of regs
                        modified_lines[i] = line.replace(regs_str, newRegs_str)
                # There is only one movem/move push xN which is at the beginning of the routine
                break

            pop_match = POP_REGS_FROM_STACK_REGEX.match(line)
            if pop_match and xN in extract_registers(pop_match.group(3), POP_OP):
                # move
                if pop_match.group(1) == 'move':
                    # Remove the move pop by commenting the line (we can't modify the size of the array)
                    modified_lines[i] = '#' + line
                # movem
                else:
                    regs_str = pop_match.group(3)
                    regs_list = extract_registers(regs_str, POP_OP)
                    # Remove xN
                    regs_list.remove(xN)
                    # If no regs to pop then comment the line
                    if len(regs_list) == 0:
                        modified_lines[i] = '#' + line
                    else:
                        sortedRegs = sort_regs(regs_list)
                        # Rebuild register list using '/' as separator
                        newRegs_str = '/'.join(sortedRegs)
                        modified_lines[i] = line.replace(regs_str, newRegs_str)
                # Continue searching. It might exist more than one movem/move pop xN
                continue

        # Forwards scan
        rem_start = i_line + 1
        rem_end = len(lines)
        for i in range(rem_start, rem_end):
            line = lines[i]
            if line[0] == '#':
                continue

            # End of this routine body?
            if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
                break

            pop_match = POP_REGS_FROM_STACK_REGEX.match(line)
            if pop_match and xN in extract_registers(pop_match.group(3), POP_OP):
                # move
                if pop_match.group(1) == 'move':
                    # Remove the move pop by commenting the line (we can't modify the size of the array)
                    lines[i] = '#' + line
                # movem
                else:
                    regs_str = pop_match.group(3)
                    regs_list = extract_registers(regs_str, POP_OP)
                    # Remove xN
                    regs_list.remove(xN)
                    # If no regs to pop then comment the line
                    if len(regs_list) == 0:
                        lines[i] = '#' + line
                    else:
                        sortedRegs = sort_regs(regs_list)
                        # Rebuild register list using '/' as separator
                        newRegs_str = '/'.join(sortedRegs)
                        lines[i] = line.replace(regs_str, newRegs_str)
                # Continue searching. It might exist more than one movem/move pop xN
                continue

def replace_remaining_jsr_aN_calls(aN, i_line, lines, modified_lines, new_line):
    """
    Search in remaining lines for every "jsr (aN)" and replace by new_line.
    Break condition is: aN is overwritten/cleared or reaching rts/rte.
    """
    control_flow_dict = build_control_flow_map(i_line, lines, modified_lines)
    control_visited = set()  # Helps to avoid looping infinitely 

    rem_start = i_line + 1
    rem_end = len(lines)
    i = rem_start
    while i < rem_end:  # forwards
        line = lines[i]
        i += 1
        if line[0] == '#':
            continue

        # If matching the "jsr (aN)" then replace it by new_line
        if match := re.match(r'^\s*jsr\s+\((%a[0-7])\)', line):
            if match.group(1) == aN:
                lines[i-1] = new_line
                continue

        # End of this routine body?
        if FUNCTION_SIZE_CALCULATION_REGEX.match(line):
            break

        if match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            # Jumping into a routine?
            if match.group(1) in ('jsr', 'bsr'):
                continue
            elif match.group(1) in ('bra', 'jra', 'jmp'):
                # Get the target label (might be a function name which won't be in control_flow_dict)
                label = match.group(3)
                # Is tatget label a special one?
                if label in backward_number_labels or label in forward_number_labels:
                    if label[1] == 'b':
                        # As we are going forwards in lines array it means we have already analyzed the code in previous lines
                        continue
                    elif label[1] == 'f':
                        # Move forwards until we find where the label has been defined
                        while i < rem_end:
                            if match_label := LABEL_REGEX.match(lines[i]):
                                if match_label.group(1) == label:
                                    break
                            i += 1
                # Sometimes the label is a function name and the code comes with a jmp/bra.
                # Or could be (symbol_name) or (%aN) which are not considered labels.
                # Hence this element is not in the dictionary.
                elif label not in control_flow_dict:
                    # When jumping into a subroutine we must stop the analysis since we don't know 
                    # whether the register xN will be effectively used in that routine
                    return None
                # Target label is in the dictionary AND was not yet visited
                elif label in control_flow_dict and label not in control_visited:
                    control_obj = control_flow_dict[label];
                    # Which array the destination line points to?
                    if control_obj.pos_in_lines != -1:
                        control_visited.add(label)  # Mark this label as visited
                        i = control_obj.pos_in_lines
                        continue
                    else:
                        # TODO
                        # We can only iterate over the current array we are iterating at (lines in this case),
                        # so we must stop here since we don't support iterating over modified_lines array starting
                        # at control_obj.pos_in_modified_lines
                        continue

        # If is a conditional branch jcc/bcc (except dbcc)
        elif match := CONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            # TODO: follow the many paths the code could take
            pass

        # aN is overwritten/cleared by a move, sub or eor itself, or clr
        elif match := REG_OVERWRITEN_OR_CLEARED_REGEX.match(line):
            instr_move_or_sub_or_eor = match.group(1)  # move or sub or eor, or empty if matched with the clr
            src = match.group(2)  # source operand for move or sub or eor
            instr_clr = match.group(3)
            dest = match.group(4)  # reg being overwritten or cleared
            if dest and dest.startswith("%a"):
                # if matching sub or eor
                if instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith(("sub","eor")):
                    # sub or eor itslef?
                    if src == dest and aN == dest:
                        break
                # if matching move
                elif instr_move_or_sub_or_eor is not None and instr_move_or_sub_or_eor.startswith("move"):
                    if aN == dest:
                        break
                # just matching the clr instruction
                elif instr_clr is not None and aN == dest:
                    break

def evaluate_instr_math_expression(expr):
    """
    Evaluate a simple math expression in the form "value [+-* value]".
    Returns None if the expression is invalid.
    """
    if not expr:
        return None

    # Remove all whitespace from the expression
    expr = expr.replace(' ', '')

    # Check for basic pattern: optional sign followed by digits and optional operator with more digits
    match_expr = re.fullmatch(r'^(-?\d+)([\+\-\*]\d+)?$', expr)
    if not match_expr:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} on evaluate_instr_math_expression(): match_expr didn't match: {expr}")
        return None

    if match_expr.group(2) is None:
        return int(match_expr.group(1))

    try:
        # Safe evaluation using operator precedence
        ops = {
            '+': operator.add,
            '-': operator.sub,
            '*': operator.mul,
        }

        # Find all numbers and operators
        tokens = re.split(r'([\+\-\*])', expr)  # Split on +, *, or -
        if len(tokens) == 1:
            # No operators, just a number
            return int(tokens[0])

        # Handle multiplication first (higher precedence)
        for i in range(1, len(tokens), 2):
            if tokens[i] == '*':
                result = int(tokens[i-1]) * int(tokens[i+1])
                tokens[i-1:i+2] = [str(result)]
                i -= 2  # Adjust index after merging tokens

        # Now evaluate left to right for + and -
        result = int(tokens[0])
        for i in range(1, len(tokens), 2):
            op = tokens[i]
            num = int(tokens[i+1])
            result = ops[op](result, num)

        return result
    except (ValueError, IndexError, KeyError):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} on evaluate_instr_math_expression(): {expr}")
        return None

def get_displacement_and_areg(match):
    """
    This is exclusively to use with the match object from pattern move_disp_aN_into_xN_pattern
    """
    if not match:
        return (None, None)

    disp = None
    areg = None
    if match.group(4):
        disp = evaluate_instr_math_expression(match.group(4))
        areg = match.group(5)
    elif match.group(6):
        disp = evaluate_instr_math_expression(match.group(6))
        areg = match.group(7)
    elif match.group(8):
        disp = 0
        areg = match.group(8)

    return (disp, areg)

def are_regs_sorted(regs):
    """
    Given a list of "%dN"s and "%aN"s ("%sp" too), test if they are sorted
    in the expected M68000 standard: d0,d1,...,d7,a0,a1,...,a7
    """
    # Convert "sp" to "a7" for consistent processing
    normalized_regs = ['%a7' if reg == '%sp' else reg for reg in regs]

    # Split into data and address registers
    data_regs = [r for r in normalized_regs if r.startswith('%d')]
    addr_regs = [r for r in normalized_regs if r.startswith('%a')]

    # Check if the original list was grouped properly (all data before all address)
    found_addr = False
    for reg in normalized_regs:
        if reg.startswith('%a'):
            found_addr = True
        elif reg.startswith('%d') and found_addr:
            # Data register after address register -> invalid grouping
            return False

    def is_increasing(regs, prefix):
        if not regs:
            return True
        # Extract numbers
        numbers = [int(reg[len(prefix):]) for reg in regs]
        
        # Check if strictly increasing (no duplicates, no decreasing)
        return numbers == sorted(numbers) and len(numbers) == len(set(numbers))

    # Check if each group is in strictly increasing order                            
    return is_increasing(data_regs, '%d') and is_increasing(addr_regs, '%a')

# Table for opcode base sizes in words
BASE_SIZES_IN_WORDS = {
    'abcd': 1, 'adda': 1, 'add': 1, 'addi': 1, 'addq': 1, 'addx': 1, 'and': 1, 'andi': 1, 'asl': 1, 'asr': 1, 'bcc': 1, 'bcs': 1, 
    'beq': 1, 'bge': 1, 'bgt': 1, 'bhi': 1, 'bhs': 1, 'ble': 1, 'blo': 1, 'bls': 1, 'blt': 1, 'bmi': 1, 'bne': 1, 'bpl': 1, 
    'bra': 1, 'bset': 1, 'bsr': 1, 'btst': 1, 'bvc': 1, 'bvs': 1, 'chk': 1, 'clr': 1, 'cmpa': 1, 'cmp': 1, 'cmpi': 1, 'cmpm': 1, 'dbcc': 1,
    'dbcs': 1, 'dbeq': 1, 'dbf': 1, 'dbra': 1, 'dbge': 1, 'dbgt': 1, 'dbhi': 1, 'dble': 1, 'dbls': 1, 'dblt': 1, 'dbmi': 1, 'dbne': 1,
    'dbpl': 1, 'dbra': 1, 'dbt': 1, 'dbvc': 1, 'dbvs': 1, 'divs': 1, 'divu': 1, 'eor': 1, 'eori': 1, 'exg': 1, 'ext': 1, 'jcc': 1, 
    'jcs': 1, 'jeq': 1, 'jge': 1, 'jgt': 1, 'jhi': 1, 'jhs': 1, 'jle': 1, 'jlo': 1, 'jls': 1, 'jlt': 1, 'jmi': 1, 'jmp': 1, 'jne': 1, 
    'jpl': 1, 'jra': 1, 'jsr': 1, 'jvc': 1, 'jvs': 1, 'lea': 1, 'link': 1, 'lsl': 1, 'lsr': 1, 'movea': 1, 'move': 1, 'movem': 2, 
    'movep': 2, 'moveq': 1, 'muls': 1, 'mulu': 1, 'nbcd': 1, 'neg': 1, 'negx': 1, 'not': 1, 'or': 1, 'ori': 1, 'pea': 1, 'rol': 1, 'ror': 1, 
    'roxl': 1, 'roxr': 1, 'sbcd': 1, 'scc': 1, 'scs': 1, 'sf': 1, 'sge': 1, 'sgt': 1, 'shi': 1, 'sle': 1, 'sls': 1, 'slt': 1, 
    'smi': 1, 'sne': 1, 'spl': 1, 'st': 1, 'suba': 1, 'sub': 1, 'subi': 1, 'subq': 1, 'subx': 1, 'svc': 1, 'swap': 1, 'tas': 1, 
    'tst': 1, 'unlk': 1,
    'nop': 1, 'rte': 1, 'rts': 1
}
    
# Addressing mode extra words (per operand)
# Note: These are *extra* words beyond the opcode
MODE_EXTRA_SIZES_IN_WORDS = {
    'Dn': 0, 'An': 0, '(An)': 0, '(An)+': 0, '-(An)': 0,   # Register direct/indirect
    '(An,Xn)': 1, '(d16,An)': 1, '(d8,An,Xn)': 1,          # Displacement/index
    '(ABS.w)': 1, '(ABS.l)': 2,                            # Absolute indirect
    'ABS.w': 1, 'ABS.l': 2,                                # Absolute
    '#imm.w': 1, '#imm.l': 2,                              # Immediate
    'encoded': 0,                                          # Encoded in the instruction
}

# d[0-7]
RE_Dn = re.compile(r'^%d[0-7]$')
# a[0-7], sp
RE_An = re.compile(r'^(%a[0-7]|%sp)$')
# (a[0-7]), (sp)
RE_An_paren = re.compile(r'^\((%a[0-7]|%sp)\)$')
# (a[0-7])+, (sp)+
RE_An_paren_plus = re.compile(r'^\((%a[0-7]|%sp)\)\+$')
# -(a[0-7]), -(sp)
RE_An_minus_paren = re.compile(r'^-\((%a[0-7]|%sp)\)$')
# (a[0-7]|pc,[ad][0-7][.s]), and all combinations
RE_An_Xn = re.compile(r'^\((%a[0-7]|%sp|%pc),(%[ad][0-7]|%sp)(\.[bwl])?\)$')
# d16[+-*N](a[0-7]|pc), and all combinations. ie: 20+2(a0)
RE_d16_An = re.compile(r'^([0-9a-zA-Z_\.]+|-?\d+([\-\+\*]\d+)?)\((%a[0-7]|%sp|%pc)\)$')
# (d16[+-*N],a[0-7]|pc), and all combinations. ie: (20+2,a0)
RE_paren_d16_An = re.compile(r'^\(([0-9a-zA-Z_\.]+|-?\d+([\-\+\*]\d+)?),(%a[0-7]|%sp|%pc)\)$')
# d8[+-*N](a[0-7]|pc,[ad][0-7][.s]), and all combinations
RE_d8_An_Xn = re.compile(r'^([0-9a-zA-Z_\.]+|-?\d+([\-\+\*]\d+)?)\((%a[0-7]|%sp|%pc),(%[ad][0-7]|%sp)(\.[bwl])?\)$')
# (d8[+-*N],a[0-7]|pc,[ad][0-7][.s]), and all combinations
RE_paren_d8_An_Xn = re.compile(r'^\(([0-9a-zA-Z_\.]+|-?\d+([\-\+\*]\d+)?),(%a[0-7]|%sp|%pc),(%[ad][0-7]|%sp)(\.[bwl])?\)$')
# (value[.s])
RE_paren_ABS_value = re.compile(r'^\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?\)$')
# (symbolName[.s][+-N][.s]). ie: (context3D+12.l)
RE_paren_ABS_sym = re.compile(r'^\([0-9a-zA-Z_\.]+(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?\)$')
# Any label, function, or symbolName. ie: 1b, .L37, _loc1, memsetU16, xlt_all.0, context3D+12.l
RE_label_function_symbol = re.compile(r'^[0-9a-zA-Z_\.]+(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?$')
# #symbolName. ie: #xlt_all.0, #context3D+12.l
RE_imm_symbol = re.compile(r'^#[0-9a-zA-Z_\.]+(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?$')
# value.s
RE_value_size = re.compile(r'^(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?$')
# #value.s
RE_imm_value = re.compile(r'^#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?$')

bcc_or_jcc_instructions = {
    'bcc','bcs','beq','bge','bgt','bhi','bhs','ble','blo','bls','blt','bmi','bne','bpl','bvc','bvs',
    'jcc','jcs','jeq','jge','jgt','jhi','jhs','jle','jlo','jls','jlt','jmi','jne','jpl','jvc','jvs'
}

unconditional_short_instructions = {'bra','jra','bsr'}

def classify_operand(op, op_base, op_size):
    """
    Classify operand into addressing mode key for MODE_EXTRA_SIZES_IN_WORDS
    """
    op = op.strip()

    if RE_Dn.match(op):
        return 'Dn'
    if RE_An.match(op):
        return 'An'
    if RE_An_paren.match(op):
        return '(An)'
    if RE_An_paren_plus.match(op):
        return '(An)+'
    if RE_An_minus_paren.match(op):
        return '-(An)'
    # Match (An,Xn[.bwl])
    if RE_An_Xn.match(op):
        return '(An,Xn)'
    # Match d16(aN)
    if RE_d16_An.match(op):
        return '(d16,An)'
    # Match (d16,aN)
    if RE_paren_d16_An.match(op):
        return '(d16,An)'
    # Match d8(An,Xn[.bwl])
    if RE_d8_An_Xn.match(op):
        return '(d8,An,Xn)'
    # Match (d8,An,Xn[.bwl])
    if RE_paren_d8_An_Xn.match(op):
        return '(d8,An,Xn)'
    # (ABS[.bwl])
    if RE_paren_ABS_value.match(op):
        if op.endswith(('.b','.w')):
            return '(ABS.w)'
        return '(ABS.l)'
    # (symbol[.bwl])
    if RE_paren_ABS_sym.match(op):
        if op.endswith(('.b','.w')):
            return '(ABS.w)'
        return '(ABS.l)'
    # Labels, functions, and symbols. gcc might add +N[.l] or -N[.l]. Ie: ammoInventory[.bwl][+-N][.l]
    if RE_label_function_symbol.match(op):
        if op_size == 's':
            return 'encoded'  # The label is encoded inside the op_base so is free
        elif op_base.startswith('db') or op_base in bcc_or_jcc_instructions or op_base in unconditional_short_instructions:
            return 'ABS.w'
        return 'ABS.l'
    # Symbol with starting #. gcc might add +N[.l] or -N[.l]. Ie:  #ammoInventory[.bwl][+-N][.l]
    if RE_imm_symbol.match(op):
        return 'ABS.l'
    # Value with size (ie: pea  1.w)
    if RE_value_size.match(op):
        if op.endswith(('.b','.w')):
            return 'ABS.w'
        return 'ABS.l'
    # Immediate value
    if match := RE_imm_value.match(op):
        if op_base in ('addq','moveq','subq','movem'):
            return 'encoded'  # The immediate operand is encoded inside the op_base so is free
        elif op.endswith(('.b','.w')):
            return '#imm.w'
        elif op.endswith('.l'):
            return '#imm.l'
        if op_size in ('b','w'):
            return '#imm.w'
        elif op_size == 'l':
            return '#imm.l'
        val = parseConstantUnsigned(match.group(1))
        if 0 <= val <= 65535:
            return '#imm.w'
        return '#imm.l'

    # Not considered:
    #   xN/xM... and xN-xM... which are part of movem
    # But they are encoded into the op_base so returning None won't add up in size.
    #print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {op}")
    return None

def split_operands(operand_field: str):
    """Split operand field into operands, ignoring commas inside (...) or quotes."""
    ops, cur = [], []
    depth = 0
    for ch in operand_field:
        if ch == '(':
            depth += 1
            cur.append(ch)
            continue
        if ch == ')':
            depth = max(0, depth - 1)
            cur.append(ch)
            continue
        if ch == ',' and depth == 0:
            op = ''.join(cur).strip()
            if op:
                ops.append(op)
            cur = []
            continue
        cur.append(ch)
    tail = ''.join(cur).strip()
    if tail:
        ops.append(tail)
    return ops

def instruction_size(line_stripped):
    """
    Calculates the byte size of the instruction. It analyzes opcode and operands.
    """
    # Split opcode and operands
    parts = re.split(r'\s+', line_stripped, maxsplit=1)
    opcode = parts[0]
    operands = split_operands(parts[1]) if len(parts) > 1 else []

    # Strip size suffix for lookup
    opcode_components = opcode.split('.')
    op_base = opcode_components[0]
    op_size = '' if len(opcode_components) == 1 else opcode_components[1]
    if op_base not in BASE_SIZES_IN_WORDS:
        #print(f'0\t{line_stripped}   op_code={opcode}  operands={operands}  op_base={op_base}  op_size={op_size}')
        return 0  # Unknown opcode

    size_words = BASE_SIZES_IN_WORDS[op_base]

    # Parse operands
    if operands:
        for op in operands:
            mode = classify_operand(op, op_base, op_size)
            if mode:
                size_words += MODE_EXTRA_SIZES_IN_WORDS.get(mode, 0)

    # Convert words into bytes
    #print(f'{size_words*2}\t{line_stripped}   op_code={opcode}  operands={operands}  op_base={op_base}  op_size={op_size}')
    return size_words * 2

MAX_BYTES_IN_8_BYTES_RANGE_BACKWARDS = 126
MAX_BYTES_IN_8_BYTES_RANGE_FORWARDS = 128

def is_label_within_8_bytes_range(label, i_line, lines, modified_lines):
    """
    Checks if a label is within an 8-byte range (backwards or forwards).
    """
    target_label_def = f'{label}:'

    # Helper function to scan lines and check for label
    def check_if_label_is_in_range(target_lines, start_idx, end_idx, max_bytes):
        bytes_accum = 0
        i = start_idx
        rept_stack = []  # Stack to track nested .rept blocks
        variables = {}   # Dictionary to store variables defined with .set

        while i < end_idx:
            line = target_lines[i]
            # Remove leading whitespaces for next checks. Trailing whitespaces were removed in an earlier stage
            stripped = line.lstrip()
            i += 1  # Advance to next line

            if stripped.startswith('#'):
                continue

            # Stop if reaching or exceeding max bytes
            if bytes_accum >= max_bytes:
                return False

            # Handles .set directive. Eg: .set regs, 15
            # Save regs in a dictionary (or map).
            # Also handlex .set with arithmetic over the variable. Eg: .set regs, regs + 40 * 2
            if stripped.startswith('.set'):
                # Special case when gcc uses .set after the size calculation of a routine
                if FUNCTION_SIZE_CALCULATION_REGEX.match(target_lines[i-2]):
                    continue
                parts = stripped.split(',', 1)
                if len(parts) == 2:
                    var_name = parts[0].replace('.set', '').strip()
                    expr = parts[1].strip()
                    
                    # Substitute variables in the expression with their values
                    for var, value in variables.items():
                        # Use word boundaries to ensure we match whole words only
                        expr = re.sub(r'\b' + re.escape(var) + r'\b', str(value), expr)
                    
                    try:
                        result = eval(expr)
                        variables[var_name] = result
                    except:
                        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} on evaluation of: {stripped}")
                continue

            # Skip lines inside .if block when it evaluates to false
            if stripped.startswith('.if'):
                condition_result = False
                if_condition_expr = stripped.replace('.if', '').strip()
                
                # Substitute variables in the condition expression with their values
                for var, value in variables.items():
                    # Use word boundaries to ensure we match whole words only
                    if_condition_expr = re.sub(r'\b' + re.escape(var) + r'\b', str(value), if_condition_expr)

                # Replace GNU AS logical operators with Python ones
                if_condition_expr = if_condition_expr.replace('&&', ' and ').replace('||', ' or ')

                try:
                    result = eval(if_condition_expr)
                    condition_result = bool(result)
                except:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} on evaluation of: {stripped}")

                if not condition_result:
                    if_count = 1
                    # Skip until corresponding .endif
                    while i < len(target_lines):
                        next_line = target_lines[i].strip()
                        i += 1  # Advance to next line
                        if next_line.startswith('.if'):
                            if_count += 1
                        elif next_line.startswith('.endif'):
                            if_count -= 1
                            if if_count == 0:
                                break
                    continue

            # Handles .rept directives
            if stripped.startswith('.rept'):
                rept_count_expr = stripped.replace('.rept', '').strip()
                
                # Substitute variables in the rept count expression with their values
                for var, value in variables.items():
                    # Use word boundaries to ensure we match whole words only
                    rept_count_expr = re.sub(r'\b' + re.escape(var) + r'\b', str(value), rept_count_expr)

                # Replace GNU AS logical operators with Python ones
                rept_count_expr = rept_count_expr.replace('&&', ' and ').replace('||', ' or ')

                try:
                    rept_count = eval(rept_count_expr)
                except:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} on evaluation of: {stripped}")
                    rept_count = 1  # Default to 1 if evaluation fails

                rept_stack.append({
                    'rept_count': rept_count,
                    'bytes_accum': 0
                })
                continue

            # Handles .endr directives
            if stripped.startswith('.endr') and rept_stack:
                current_rept = rept_stack[-1]
                rept_count = current_rept['rept_count']
                bytes_accum += rept_count * current_rept['bytes_accum']
                rept_stack.pop()
                continue

            # Check if this is the target label
            if stripped.startswith(target_label_def):
                break

            instr_size = 0

            # Handles .byte, .word, .long directives
            if stripped.startswith('.byte'):
                instr_size = 1
            elif stripped.startswith('.word'):
                instr_size = 2
            elif stripped.startswith('.long'):
                instr_size = 4
            # Skip if it's a label or compiler info or directive
            elif stripped.endswith(':') or containsCompilerInfo(stripped) or containsCompilerDirective(stripped):
                pass  # Do nothing
            # Handles instruction size
            else:
                instr_size = instruction_size(stripped)

            # If we're inside a .rept block, track bytes for this block
            if rept_stack:
                current_rept = rept_stack[-1]
                current_rept['bytes_accum'] += instr_size
            # Otherwise just accumulate
            else:
                bytes_accum += instr_size

        # We can safely say that target label is within range
        return True

    # Phase 1: Backward scan (modified_lines)
    # But we are going to scan it in forward fashion.
    # So first find target_label_def position
    target_label_def_position = len(modified_lines) - 1  # fail safe position in case we can't find target_label_def
    start_idx = len(modified_lines) - 1
    end_idx = 0
    for i in range(start_idx, end_idx - 1, -1):
        line = modified_lines[i]
        # Remove leading whitespaces for next checks. Trailing whitespaces were removed in an earlier stage
        stripped = line.lstrip()
        # Check if this is the target label
        if stripped.startswith(target_label_def):
            # Special case for infnite loops (like the one in VDP_resetScreen())
            if i == start_idx:
                return True  # target label is in range
            target_label_def_position = i
            # Now scan modified_lines in a forward fashion starting at the target_label_def position
            is_in_range = check_if_label_is_in_range(
                modified_lines,
                target_label_def_position + 1,
                len(modified_lines),
                MAX_BYTES_IN_8_BYTES_RANGE_BACKWARDS
            )
            if is_in_range:
                return True
            break

    # Phase 2: Forward scan (remaining lines)
    is_in_range = check_if_label_is_in_range(
        lines,
        i_line + 1,
        len(lines),
        MAX_BYTES_IN_8_BYTES_RANGE_FORWARDS
    )
    return is_in_range

IS_ASL_INSTRUCTION_REGEX = re.compile(r'^\s*asl\.[bwl]\s+[^,]+,\s*%d[0-7]')

IS_ASR_INSTRUCTION_REGEX = re.compile(r'^\s*asr\.[bwl]\s+[^,]+,\s*%d[0-7]')

IS_DIV_INSTRUCTION_REGEX = re.compile(r'^\s*(?:divs\.w|divu\.w)\s+[^,]+,\s*%d[0-7]')

IS_MOVEQ_INSTRUCTION_REGEX = re.compile(r'^\s*(?:moveq|move)\.?[bwl]?\s+#[^,]+,\s*%d[0-7]')

IS_MUL_INSTRUCTION_REGEX = re.compile(r'^\s*(?:muls\.w|mulu\.w)\s+[^,]+,\s*%d[0-7]')

IS_MULS_INSTRUCTION_REGEX = re.compile(r'^\s*(?:muls\.w)\s+[^,]+,\s*%d[0-7]')

IS_MULU_INSTRUCTION_REGEX = re.compile(r'^\s*(mulu\.w)\s+[^,]+,\s*%d[0-7]')

IS_LSL_INSTRUCTION_REGEX = re.compile(r'^\s*lsl\.[bwl]\s+[^,]+,\s*%d[0-7]')

IS_LSR_INSTRUCTION_REGEX = re.compile(r'^\s*lsr\.[bwl]\s+[^,]+,\s*%d[0-7]')

IS_ROL_INSTRUCTION_REGEX = re.compile(r'^\s*rol\.[bwl]\s+[^,]+,\s*%d[0-7]')

IS_ROR_INSTRUCTION_REGEX = re.compile(r'^\s*ror\.[bwl]\s+[^,]+,\s*%d[0-7]')

IS_ROXL_INSTRUCTION_REGEX = re.compile(r'^\s*roxl\.[bwl]\s+[^,]+,\s*%d[0-7]')

move_disp_aN_into_xN_pattern = re.compile(
    r'^(\s*)(?:move|movea)\.([wl])(\s+)'  # move.[w/l] or movea.[w/l]
    r'(?:'                                # Non-capturing group
        r'(-?\d+(?:[\-\+\*]\d+)?)\((%a[0-7]|%sp)\)'   # disp(aN) where disp can be disp[+-*N]
        r'|'                              # OR
        r'\((-?\d+(?:[\-\+\*]\d+)?),(%a[0-7]|%sp)\)'  # (disp,aN) where disp can be disp[+-*N]
        r'|'                              # OR
        r'\((%a[0-7]|%sp)\)'              # (aN)
    r')'                                  # End non-capturing group
    r',\s*(%[ad][0-7]|%sp)'               # destination register
)

btst_7_effective_address_pattern = re.compile(
    r'^(\s*)btst\.b(\s+)#7,\s*'
    r'(?!'                              # Negative lookahead for invalid modes
        r'%d[0-7]\b'                        # Data registers %d0-%d7
        r'|'                                # OR
        r'-?\d+(?:[\-\+\*]\d+)?\(%pc\)'     # disp(pc), where disp can be disp[+-*N]
        r'|'                                # OR
        r'\(-?\d+(?:[\-\+\*]\d+)?,%pc\)'    # (disp,pc), where disp can be disp[+-*N]
        r'|'                                # OR
        r'-?\d+(?:[\-\+\*]\d+)?\(%pc,(?:%[ad][0-7](?:\.[bwl])?|%sp)\)'   # disp(pc,xN.s) where disp can be disp[+-*N]
        r'|'                                # OR
        r'\(-?\d+(?:[\-\+\*]\d+)?,%pc,(?:%[ad][0-7](?:\.[bwl])?|%sp)\)'  # (disp,pc,xN.s) where disp can be disp[+-*N]
    r')'                                # End negative lookahead for invalid modes
    r'(.+)'                             # Capture the valid effective address
)

move_disp_aN_or_pc_into_aM_pattern = re.compile(
    r'^(\s*)(move|movea)\.l(\s+)'          # Instruction
    r'(?:'                                 # Non-capturing group
        r'(-?\d+(?:[\-\+\*]\d+)?)?\('      # "val(" or just "(" where val can be val[+-*N]
        r'|'                               # OR
        r'\((-?\d+(?:[\-\+\*]\d+)?,)?'     # "(val," or just "(" where val can be val[+-*N]
    r')'                                   # End non-capturing group
    r'(%a[0-7]|%sp|%pc)\),\s*(%a[0-7]|%sp)'  # aN),aM
)

move_disp_aN_or_pc_dN_into_aM_pattern = re.compile(
    r'^(\s*)(move|movea)\.l(\s+)'          # Instruction
    r'(?:'                                 # Non-capturing group
        r'(-?\d+(?:[\-\+\*]\d+)?)?\('      # "val(" or just "(" where val can be val[+-*N]
        r'|'                               # OR
        r'\((-?\d+(?:[\-\+\*]\d+)?,)?'     # "(val," or just "(" where val can be val[+-*N]
    r')'                                   # End non-capturing group
    r'(%a[0-7]|%sp|%pc),(%d[0-7]\.[bwl])\),\s*(%a[0-7]|%sp)'  # aN,dN.s),aM
)

lea_label_or_disp_aN_or_pc_into_aM_pattern = re.compile(
    r'^(\s*)lea(\s+)'                        # Instruction
    r'(?:'                                   # Non-capturing group
        r'([0-9a-zA-Z_\.]+(?:\.[bwl])?(?:[\-\+\*]\d+)?|-?\d+(?:[\-\+\*]\d+)?)?\('    # "label_or_disp(" or just "(". Also matches label_or_disp[.bwl][+-*N]
        r'|'                                 # OR
        r'\(([0-9a-zA-Z_\.]+(?:\.[bwl])?(?:[\-\+\*]\d+)?,|-?\d+(?:[\-\+\*]\d+)?,)?'  # "(label_or_disp," or just "(". Also matches label_or_disp[.bwl][+-*N]
    r')'                                     # End non-capturing group
    r'(%a[0-7]|%sp|%pc)\),\s*(%a[0-7]|%sp)'  # aN),aM
)

lea_label_or_disp_aN_or_pc_dN_into_aM_pattern = re.compile(
    r'^(\s*)lea(\s+)'                      # Instruction
    r'(?:'                                 # Non-capturing group
        r'([0-9a-zA-Z_\.]+(?:\.[bwl])?(?:[\-\+\*]\d+)?|-?\d+(?:[\-\+\*]\d+)?)?\('    # "label_or_disp(" or just "(". Also matches label_or_disp[.bwl][+-*N]
        r'|'                               # OR
        r'\(([0-9a-zA-Z_\.]+(?:\.[bwl])?(?:[\-\+\*]\d+)?,|-?\d+(?:[\-\+\*]\d+)?,)?'  # "(label_or_disp," or just "(". Also matches label_or_disp[.bwl][+-*N]
    r')'                                   # End non-capturing group
    r'(%a[0-7]|%sp|%pc),(%d[0-7]\.[bwl])\),\s*(%a[0-7]|%sp)'  # aN,dN.s),aM
)

move_ea_into_dN_pattern = re.compile(
    r'^(\s*)move\.([bwl])(\s+)'
    r'(?:'
    r'(%d[0-7]|\(%a[0-7]\)\+?|-?\(%sp\))'  # dN or (aN) or (aN)+ or -(aN)
    r'|'
    r'(#?[0-9a-zA-Z_\.]+(?:\.[bwl])?)'  # label or symbol[.s] or #symbol[.s].
    r'|'
    r'(#?(?:-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?)'  # ABS[.s] or imm[.s] or #imm[.s]
    r'|'
    r'(\((?:%a[0-7]|%sp|%pc),(?:%[ad][0-7](?:\.[bwl])?|%sp)\))'  # (aN/PC,xN.s)
    r'|'
    r'((?:[0-9a-zA-Z_\.]+|-?\d+(?:[\-\+\*]\d+)?)\((?:%a[0-7]|%sp|%pc)\))'  # label_or_disp[+-*N](aN/PC)
    r'|'
    r'(\((?:[0-9a-zA-Z_\.]+|-?\d+(?:[\-\+\*]\d+)?),(?:%a[0-7]|%sp|%pc)\))'  # (label_or_disp[+-*N],aN/PC)
    r'|'
    r'((?:[0-9a-zA-Z_\.]+|-?\d+(?:[\-\+\*]\d+)?)\((?:%a[0-7]|%sp|%pc),(?:%[ad][0-7](?:\.[bwl])?|%sp)\))'  # label_or_disp[+-*N](aN/PC,xN.s)
    r'|'
    r'(\((?:[0-9a-zA-Z_\.]+|-?\d+(?:[\-\+\*]\d+)?),(?:%a[0-7]|%sp|%pc),(?:%[ad][0-7](?:\.[bwl])?|%sp)\))'  # (label_or_disp[+-*N],aN/PC,xN.s)
    r')'
    r',\s*(%d[0-7]);?$'
)

def optimizeMultipleLines(multi_limit, i_line, lines, modified_lines):
    """
    Detect optimization opportunities that span multiple lines.
    Returns a tuple of (optimized_lines, lines_to_remove) if pattern matches, (None, 0) otherwise.
    - optimized_lines is a list of new optimized lines.
    - lines_to_remove indicates how many lines will be removed prior to add the new optimized lines.
    """

    # Check for patterns whenever we have at least 6 lines
    if multi_limit == 6:

        line_A = modified_lines[-6]
        line_B = modified_lines[-5]
        line_C = modified_lines[-4]
        line_D = modified_lines[-3]
        line_E = modified_lines[-2]
        line_F = modified_lines[-1]

        if OPTIMIZE_INLINE_ASM_BLOCKS:
            # If any line (already right stripped) ends with the flag that mandates to skip it from be optimized -> do nothing and return
            if (line_A.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_B.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_C.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_D.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_E.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_F.endswith(SKIP_OPTIMIZATION_FLAG)):
                return (None, 0)

        if USE_FABRI1983_OPTIMIZATIONS:

            # This pattern comes up after applying optimization for lsr.w #8,dN
            # But may apply for other similar situation.
            # clr.w     dN         ->   moveq   #0,dN          ; Saves 12 cycles. Leaves dN with different value than expected.
            # move.b    *,dN            move.b  *,dN    
            # move.w    dN,aN           move.w  dN,aN
            # moveq[.l] #0,dN
            # move.w    aN,dN
            # move.l    dN,aN
            matchA = re.match(r'^(\s*)clr\.w(\s+)(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(3)
                matchB = re.match(r'^\s*move\.b\s+([^,]+),\s*(%d[0-7]);?$', line_B)
                if matchB and dN == matchB.group(2):
                    src_B = matchB.group(1)
                    matchC = re.match(r'^\s*move\.w\s+(%d[0-7]),\s*(%a[0-7])', line_C)
                    if matchC and dN == matchC.group(1):
                        aN = matchC.group(2)
                        matchD = re.match(r'^\s*moveq(\.l)?\s+#0,\s*(%d[0-7])', line_D)
                        if matchD and dN == matchD.group(2):
                            matchE = re.match(r'^\s*move\.w\s+(%a[0-7]),\s*(%d[0-7])', line_E)
                            if matchE and aN == matchE.group(1) and dN == matchE.group(2):
                                matchF = re.match(r'^\s*move\.l\s+(%d[0-7]),\s*(%a[0-7])', line_F)
                                if matchF and dN == matchF.group(1) and aN == matchF.group(2):
                                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                                        optimized_lines = [
                                            f'{matchA.group(1)}moveq {matchA.group(2)}#0,{dN}',
                                            f'{matchA.group(1)}move.b{matchA.group(2)}{src_B},{dN}',
                                            f'{matchA.group(1)}move.w{matchA.group(2)}{dN},{aN}'
                                        ]
                                        return (optimized_lines, 6)

            # This pattern comes up after applying optimization for lsl.w #8,dN
            # clr.w   dN            ->   move.b  disp(aN),-(sp)    ; Saves 12 cycles
            # move.b  disp(aN),dN        move.w  (sp)+,dN
            # move.b  dN,-(sp)           move.b  dM,dN
            # move.w  (sp)+,dN
            # clr.b   dN
            # move.b  dM,dN
            matchA = re.match(r'^(\s*)clr\.w(\s+)(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(3)
                matchB = re.match(r'^\s*move\.b\s+(-?\d+)\((%a[0-7])\),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(3):
                    disp = matchB.group(1)
                    aN = matchB.group(2)
                    matchC = re.match(r'^\s*move\.b\s+(%d[0-7]),\s*-\(%sp\)', line_C)
                    if matchC and dN == matchC.group(1):
                        matchD = re.match(r'^\s*move\.w\s+\(%sp\)\+,\s*(%d[0-7])', line_D)
                        if matchD and dN == matchD.group(1):
                            matchE = re.match(r'^\s*clr\.b\s+(%d[0-7])', line_E)
                            if matchE and dN == matchE.group(1):
                                matchF = re.match(r'^\s*move\.b\s+(%d[0-7]),\s*(%d[0-7])', line_F)
                                if matchF and dN == matchF.group(2):
                                    dM = matchF.group(1)
                                    optimized_lines = [
                                        f'{matchA.group(1)}move.b{matchA.group(2)}{disp}({aN}),-(%sp)',
                                        f'{matchA.group(1)}move.w{matchA.group(2)}(%sp)+,{dN}',
                                        f'{matchA.group(1)}move.b{matchA.group(2)}{dM},{dN}'
                                    ]
                                    return (optimized_lines, 6)

            # Calculates offset indexes for accessing arrays.
            # moveq[.l]  #0,dN              ->    move.w     disp(sp),dN       ; Saves 8 cycles
            # move.w     disp(sp),dN              move.w     dN,dM
            # move.l     dN,dM                    add/sub.w  dN,dM
            # add/sub.l  dN,dM                    lea        symbolName1,aN
            # lea        symbolName1,aN           move.[wl]  (aN,dM.w),dP
            # move.[wl]  (aN,dM.[wl]),dP
            # Where:
            # symbolName1[.wl][-+*N][.bwl]
            # dP can be dN
            matchA = re.match(r'^(\s*)moveq(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+(-?\d+)\(%sp\),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    disp = matchB.group(1)
                    matchC = re.match(r'^\s*move\.l\s+(%d[0-7]),\s*(%d[0-7])', line_C)
                    if matchC and dN == matchC.group(1):
                        dM = matchC.group(2)
                        matchD = re.match(r'^\s*(add|sub)\.l\s+(%d[0-7]),\s*(%d[0-7])', line_D)
                        if matchD and dN == matchD.group(2) and dM == matchD.group(3):
                            alu = matchD.group(1)
                            matchE = re.match(r'^\s*lea\s+([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_E)
                            if matchE:
                                symbolName_1_full = ''.join(matchE.group(i) for i in range(1, 5) if matchE.group(i))
                                aN = matchE.group(5)
                                matchF = re.match(r'^\s*move\.([wl])\s+\((%a[0-7]),(%d[0-7])(\.[wl])?\),\s*(%d[0-7])', line_F)
                                if matchF and aN == matchF.group(2) and dM == matchF.group(3):
                                    sF = matchF.group(1)
                                    dP = matchF.group(5)
                                    optimized_lines = [
                                        f'{matchA.group(1)}move.w{matchA.group(3)}{disp}(%sp),{dN}',
                                        f'{matchA.group(1)}move.w{matchA.group(3)}{dN},{dM}',
                                        f'{matchA.group(1)}{alu}.w {matchA.group(3)}{dN},{dM}',
                                        f'{matchA.group(1)}lea   {matchA.group(3)}{symbolName_1_full},{aN}',
                                        f'{matchA.group(1)}move.{sF}{matchA.group(3)}({aN},{dM}.w),{dP}'
                                    ]
                                    return (optimized_lines, 6)

        # Add more multi-line patterns here for 6 lines

    # Check for patterns whenever we have at least 5 lines
    if multi_limit == 5:

        line_A = modified_lines[-5]
        line_B = modified_lines[-4]
        line_C = modified_lines[-3]
        line_D = modified_lines[-2]
        line_E = modified_lines[-1]

        if OPTIMIZE_INLINE_ASM_BLOCKS:
            # If any line (already right stripped) ends with the flag that mandates to skip it from be optimized -> do nothing and return
            if (line_A.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_B.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_C.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_D.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_E.endswith(SKIP_OPTIMIZATION_FLAG)):
                return (None, 0)

        matchA = lea_label_or_disp_aN_or_pc_into_aM_pattern.match(line_A)
        if matchA:
            aN_or_pc = matchA.group(5)
            aM = matchA.group(6)

            # lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm
            # move.w  disp1(Am),Dn                  (movem does sign extension)
            # move.w  disp2(Am),Dm
            # ext.l   Dn
            # ext.l   Dm
            matchB = move_disp_aN_into_xN_pattern.match(line_B)
            matchC = move_disp_aN_into_xN_pattern.match(line_C)
            if matchB and matchC:
                sB = matchB.group(2)
                sC = matchC.group(2)
                dN = matchB.group(9)
                dM = matchC.group(9)

                # Same size?
                if sB == 'w' and sC == 'w':
                    # stride 2 for words
                    stride = 2

                    # Extract displacements and address registers
                    dispB, aregB = get_displacement_and_areg(matchB)
                    dispC, aregC = get_displacement_and_areg(matchC)

                    # Coincident address registers and consecutive displacements?
                    # As any disp can be 0 then use "is not None"
                    if aregB and aregB == aM and aregC and aregC == aM and dispB is not None and dispC is not None and dispC == dispB + stride:
                        matchD = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_D)
                        matchE = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_E)

                        # Do both match with dN and dM?
                        if matchD and matchE and dN == matchD.group(1) and dM == matchE.group(1):
                            label_or_val = ''
                            if matchA.group(3):
                                label_or_val = matchA.group(3)
                            elif matchA.group(4):
                                label_or_val = matchA.group(4)[:-1]  # remove ,
                            # Ensure dN is smaller than dM
                            d_reg_1 = int(dN[2])  # reg index
                            d_reg_2 = int(dM[2])  # reg index
                            if d_reg_1 < d_reg_2:
                                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 5)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.w{matchA.group(2)}{label_or_val}({aN_or_pc}),{dN}/{dM}'
                                ]
                                return (optimized_lines, 5)

            # lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm
            # move.w  disp1(Am),Dn                  (movem does sign extension)
            # ext.l   Dn
            # move.w  disp2(Am),Dm
            # ext.l   Dm
            matchB = move_disp_aN_into_xN_pattern.match(line_B)
            matchD = move_disp_aN_into_xN_pattern.match(line_D)
            if matchB and matchD:
                sB = matchB.group(2)
                sD = matchD.group(2)
                dN = matchB.group(9)
                dM = matchD.group(9)

                # Same size?
                if sB == 'w' and sD == 'w':
                    # stride 2 for words
                    stride = 2

                    # Extract displacements and address registers
                    dispB, aregB = get_displacement_and_areg(matchB)
                    dispD, aregD = get_displacement_and_areg(matchD)

                    # Coincident address registers and consecutive displacements?
                    # As any disp can be 0 then use "is not None"
                    if aregB and aregB == aM and aregD and aregD == aM and dispB is not None and dispD is not None and dispD == dispB + stride:
                        matchC = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_C)
                        matchE = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_E)

                        # Do both match with dN and dM?
                        if matchC and matchE and dN == matchC.group(1) and dM == matchE.group(1):
                            label_or_val = ''
                            if matchA.group(3):
                                label_or_val = matchA.group(3)
                            elif matchA.group(4):
                                label_or_val = matchA.group(4)[:-1]  # remove ,
                            # Ensure dN is smaller than dM
                            d_reg_1 = int(dN[2])  # reg index
                            d_reg_2 = int(dM[2])  # reg index
                            if d_reg_1 < d_reg_2:
                                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 5)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.w{matchA.group(2)}{label_or_val}({aN_or_pc}),{dN}/{dM}'
                                ]
                                return (optimized_lines, 5)

            # lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm       ; Saves 16 cycles
            # move.w  (Am)+,Dn                      (movem does sign extension)
            # move.w  (Am)[+],Dm
            # ext.l   Dn
            # ext.l   Dm
            # Note: Ensure Am is not used afterwards unless is overwritten/cleared before any usage
            matchB = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)\+,\s*(%d[0-7])', line_B)
            if matchB and aM == matchB.group(3):
                matchC = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)(?:\+)?,\s*(%d[0-7])', line_C)
                if matchC and aM == matchC.group(3):
                    dN = matchB.group(4)
                    dM = matchC.group(4)
                    matchD = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_D)
                    matchE = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_E)
                    # Do both match with dN and dM?
                    if matchD and matchE and dN == matchD.group(1) and dM == matchE.group(1):
                        if not is_reg_used_before_being_overwritten_or_cleared_afterwards(aM, i_line, lines, modified_lines):
                            label_or_val = ''
                            if matchA.group(3):
                                label_or_val = matchA.group(3)
                            elif matchA.group(4):
                                label_or_val = matchA.group(4)[:-1]  # remove ,
                            # Ensure dN is smaller than dM
                            d_reg_1 = int(dN[2])  # reg index
                            d_reg_2 = int(dM[2])  # reg index
                            if d_reg_1 < d_reg_2:
                                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 5)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.w{matchA.group(2)}{label_or_val}({aN_or_pc}),{dN}/{dM}'
                                ]
                                return (optimized_lines, 5)

            # lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm     ; Saves 16 cycles
            # move.w  (Am)+,Dn                      (movem does sign extension)
            # ext.l   Dn
            # move.w  (Am)[+],Dm
            # ext.l   Dm
            # Note: Ensure Am is not used afterwards unless is overwritten/cleared before any usage
            matchB = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)\+,\s*(%d[0-7])', line_B)
            aN_or_pc = matchA.group(5)
            aM = matchA.group(6)
            if matchB and aM == matchB.group(3):
                matchD = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)(?:\+)?,\s*(%d[0-7])', line_D)
                if matchD and aM == matchD.group(3):
                    dN = matchB.group(4)
                    dM = matchD.group(4)
                    matchC = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_C)
                    matchE = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_E)
                    # Do both match with dN and dM?
                    if matchC and matchE and dN == matchC.group(1) and dM == matchE.group(1):
                        if not is_reg_used_before_being_overwritten_or_cleared_afterwards(aM, i_line, lines, modified_lines):
                            label_or_val = ''
                            if matchA.group(3):
                                label_or_val = matchA.group(3)
                            elif matchA.group(4):
                                label_or_val = matchA.group(4)[:-1]  # remove ,
                            # Ensure dN is smaller than dM
                            d_reg_1 = int(dN[2])  # reg index
                            d_reg_2 = int(dM[2])  # reg index
                            if d_reg_1 < d_reg_2:
                                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 5)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.w{matchA.group(2)}{label_or_val}({aN_or_pc}),{dN}/{dM}'
                                ]
                                return (optimized_lines, 5)

        if USE_FABRI1983_MOVEM_OPTIMIZATIONS:

            # Consecutively push into stack a sequence of registers
            # move.[wl]  xN5,-(aN)   ->   movem.[wl]  xN5/xN4/xN3/xN2/xN1,-(aN)    ; Saves 12 cycles
            # move.[wl]  xN4,-(aN)
            # move.[wl]  xN3,-(aN)
            # move.[wl]  xN2,-(aN)
            # move.[wl]  xN1,-(aN)
            # IMPORTANT: movem.l regs,-(An) starts reading reg x7 and goes down to x0
            push_xn_into_stack_pattern = r'^(\s*)move\.([wl])(\s+)(%[ad][0-7]),\s*-\((%a[0-7]|%sp)\)'
            matchA = re.match(push_xn_into_stack_pattern, line_A)
            if matchA:
                s = matchA.group(2)
                aN = matchA.group(5)
                matchB = re.match(push_xn_into_stack_pattern, line_B)
                if matchB and s == matchB.group(2) and aN == matchB.group(5):
                    matchC = re.match(push_xn_into_stack_pattern, line_C)
                    if matchC and s == matchC.group(2) and aN == matchC.group(5):
                        matchD = re.match(push_xn_into_stack_pattern, line_D)
                        if matchD and s == matchD.group(2) and aN == matchD.group(5):
                            matchE = re.match(push_xn_into_stack_pattern, line_E)
                            if matchE and s == matchE.group(2) and aN == matchE.group(5):
                                xN5 = matchA.group(4)
                                xN4 = matchB.group(4)
                                xN3 = matchC.group(4)
                                xN2 = matchD.group(4)
                                xN1 = matchE.group(4)
                                xregs = [xN5, xN4, xN3, xN2, xN1]
                                # Check if registers are sorted in their categories
                                reversed_xregs = xregs[::-1]
                                if are_regs_sorted(reversed_xregs):
                                    # Format register list for movem
                                    xreg_list = '/'.join(f'{r}' for r in xregs)
                                    optimized_lines = [
                                        f'{matchA.group(1)}movem.{s}{matchA.group(3)}{xreg_list},-({aN})'
                                    ]
                                    return (optimized_lines, 5)

            # Consecutively pop from stack into a sequence of registers
            # move.[wl]  (aN)+,xN1   ->   movem.[wl]  (aN)+,xN1/xN2/xN3/xN4/xN5    ; Saves 4 cycles
            # move.[wl]  (aN)+,xN2
            # move.[wl]  (aN)+,xN3
            # move.[wl]  (aN)+,xN4
            # move.[wl]  (aN)+,xN5
            pop_xn_from_stack_pattern = r'^(\s*)move\.([wl])(\s+)\((%a[0-7]|%sp)\)\+,\s*(%[ad][0-7])'
            matchA = re.match(pop_xn_from_stack_pattern, line_A)
            if matchA:
                s = matchA.group(2)
                aN = matchA.group(4)
                matchB = re.match(pop_xn_from_stack_pattern, line_B)
                if matchB and s == matchB.group(2) and aN == matchB.group(4):
                    matchC = re.match(pop_xn_from_stack_pattern, line_C)
                    if matchC and s == matchC.group(2) and aN == matchC.group(4):
                        matchD = re.match(pop_xn_from_stack_pattern, line_D)
                        if matchD and s == matchD.group(2) and aN == matchD.group(4):
                            matchE = re.match(pop_xn_from_stack_pattern, line_E)
                            if matchE and s == matchE.group(2) and aN == matchE.group(4):
                                xN1 = matchA.group(5)
                                xN2 = matchB.group(5)
                                xN3 = matchC.group(5)
                                xN4 = matchD.group(5)
                                xN5 = matchE.group(5)
                                xregs = [xN1, xN2, xN3, xN4, xN5]
                                # Check if registers are sorted in their categories
                                if are_regs_sorted(xregs):
                                    # Format register list for movem
                                    xreg_list = '/'.join(f'{r}' for r in xregs)
                                    optimized_lines = [
                                        f'{matchA.group(1)}movem.{s}{matchA.group(3)}({aN})+,{xreg_list}'
                                    ]
                                    return (optimized_lines, 5)

        if USE_FABRI1983_OPTIMIZATIONS:

            # Unnecessary clear of data register to load 2 word values
            # moveq[.l]  #0,dN     ->   move.w  *,dN               ; Saves 8 cycles
            # move.w     *,dN           swap    dN
            # swap[.w]   dN             move.w  *,dN
            # clr.w      dN
            # move.w     *,dN
            matchA = re.match(r'^(\s*)moveq(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+([^,]+),\s*(%d[0-7]);?$', line_B)
                if matchB and dN == matchB.group(2):
                    matchC = re.match(r'^\s*swap(\.w)?\s+(%d[0-7])', line_C)
                    if matchC and dN == matchC.group(2):
                        matchD = re.match(r'^\s*clr\.w?\s+(%d[0-7])', line_D)
                        if matchD and dN == matchD.group(1):
                            matchE = re.match(r'^\s*move\.w\s+([^,]+),\s*(%d[0-7]);?$', line_E)
                            if matchE and dN == matchE.group(2):
                                src_B = matchB.group(1)
                                src_E = matchE.group(1)
                                optimized_lines = [
                                    f'{matchA.group(1)}move.w{matchA.group(3)}{src_B},{dN}',
                                    f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                                    f'{matchA.group(1)}move.w{matchA.group(3)}{src_E},{dN}'
                                ]
                                return (optimized_lines, 5)

            # Unnecessary clear of data register to multiply by 4 an address register and add/sub a constant
            # moveq[.l]  #0,dN     ->   add.l      aN,aN           ; Saves 8 cycles. Leaves dN with different value than expected.
            # move.w     aN,dN          add.l      aN,aN
            # lsl.l      #2,dN          add/sub.l  #val,aN
            # move.l     dN,aN
            # add/sub.l  #val,aN
            matchA = re.match(r'^(\s*)moveq(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+(%a[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    aN = matchB.group(1)
                    matchC = re.match(r'^\s*(lsl|asl)\.l\s+#2,\s*(%d[0-7])', line_C)
                    if matchC and dN == matchC.group(2):
                        matchD = re.match(r'^\s*(move|movea)\.l\s+(%d[0-7]),\s*(%a[0-7])', line_D)
                        if matchD and dN == matchD.group(2) and aN == matchD.group(3):
                            matchE = re.match(r'^\s*(add|adda|addq|sub|suba|subq)\.l\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7])', line_E)
                            if matchE and aN == matchE.group(3):
                                alu = matchE.group(1)
                                val = matchE.group(2)
                                if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                                    optimized_lines = [
                                        f'{matchA.group(1)}add.l{matchA.group(3)}{aN},{aN}',
                                        f'{matchA.group(1)}add.l{matchA.group(3)}{aN},{aN}',
                                        f'{matchA.group(1)}{alu}.l{matchA.group(3)}#{val},{aN}'
                                    ]
                                    return (optimized_lines, 5)

            # Unnecessary clear of data register to multiply by 2 an address register and add/sub a constant
            # moveq[.l]  #0,dN     ->   move.l     aN,aM           ; Saves 8 cycles. Leaves dN with different value than expected.
            # move.w     aN,dN          add.l      aM,aM
            # add.l      dN,dN          add/sub.l  #val,aM
            # move.l     dN,aM
            # add/sub.l  #val,aM
            matchA = re.match(r'^(\s*)moveq(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+(%a[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    aN = matchB.group(1)
                    matchC = re.match(r'^\s*add\.l\s+(%d[0-7]),\s*(%d[0-7])', line_C)
                    if matchC and dN == matchC.group(1) and dN == matchC.group(2):
                        matchD = re.match(r'^\s*(move|movea)\.l\s+(%d[0-7]),\s*(%a[0-7])', line_D)
                        if matchD and dN == matchD.group(2):
                            aM = matchD.group(3)
                            matchE = re.match(r'^\s*(add|adda|addq|sub|suba|subq)\.l\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7])', line_E)
                            if matchE and aM == matchE.group(3):
                                alu = matchE.group(1)
                                val = matchE.group(2)
                                if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                                    optimized_lines = [
                                        f'{matchA.group(1)}move.l{matchA.group(3)}{aN},{aM}',
                                        f'{matchA.group(1)}add.l {matchA.group(3)}{aM},{aM}',
                                        f'{matchA.group(1)}{alu}.l {matchA.group(3)}#{val},{aM}'
                                    ]
                                    return (optimized_lines, 5)

            # Calculates offset indexes for accessing arrays.
            # moveq[.l]  #0,dN              ->    move.w     symbolName1,dN        ; Saves 8 cycles
            # move.w     symbolName1,dN           add/sub.w  dN,dN
            # add/sub.l  dN,dN                    lea        symbolName2,aN
            # lea        symbolName2,aN           move.[wl]  (aN,dN.w),dP
            # move.[wl]  (aN,dN.[wl]),dP
            # Where:
            # symbolName1[.w][-+*N][.bwl]
            # symbolName2[.wl][-+*N][.bwl]
            # dP can be dN
            matchA = re.match(r'^(\s*)moveq(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+([0-9a-zA-Z_\.]+)(\.w)?([\-\+\*]\d+)?(\.[bwl])?,\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(5):
                    symbolName_1_full = ''.join(matchB.group(i) for i in range(1, 5) if matchB.group(i))
                    matchC = re.match(r'^\s*(add|sub)\.l\s+(%d[0-7]),\s*(%d[0-7])', line_C)
                    if matchC and dN == matchC.group(2) and dN == matchC.group(3):
                        alu = matchC.group(1)
                        matchD = re.match(r'^\s*lea\s+([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_D)
                        if matchD:
                            symbolName_2_full = ''.join(matchD.group(i) for i in range(1, 5) if matchD.group(i))
                            aN = matchD.group(5)
                            matchE = re.match(r'^\s*move\.([wl])\s+\((%a[0-7]),(%d[0-7])(\.[wl])?\),\s*(%d[0-7])', line_E)
                            if matchE and aN == matchE.group(2) and dN == matchE.group(3):
                                sE = matchE.group(1)
                                dP = matchE.group(5)
                                optimized_lines = [
                                    f'{matchA.group(1)}move.w{matchA.group(3)}{symbolName_1_full},{dN}',
                                    f'{matchA.group(1)}{alu}.w {matchA.group(3)}{dN},{dN}',
                                    f'{matchA.group(1)}lea   {matchA.group(3)}{symbolName_2_full},{aN}',
                                    f'{matchA.group(1)}move.{sE}{matchA.group(3)}({aN},{dN}.w),{dP}'
                                ]
                                return (optimized_lines, 5)

            # Calculates offset indexes for accessing arrays. The offset at dN has already the correct stride.
            # moveq[.l]  #0,dN             ->   move.w     disp1(sp),dN            ; Saves 16 cycles
            # move.w     disp1(sp),dN           move.l     disp2(sp),aN
            # move.l     disp2(sp),aN           lea        symbolName1(aN,dN.w),aN
            # add/sub.l  #symbolName1,aN        move.[wl]  (aN),dP
            # move.[wl]  (aN,dN.[wl]),dP
            # Where:
            # symbolName1[.wl][-+*N][.bwl]
            # dP can be dN
            matchA = re.match(r'^(\s*)moveq(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+(-?\d+)\(%sp\),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    disp1 = matchB.group(1)
                    matchC = re.match(r'^\s*move\.l\s+(-?\d+)\(%sp\),\s*(%a[0-7])', line_C)
                    if matchC:
                        disp2 = matchC.group(1)
                        aN = matchC.group(2)
                        matchD = re.match(r'^\s*(add|adda|sub|suba)\.l\s+#([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_D)
                        if matchD and aN == matchD.group(6) and isValue(matchD.group(2)):
                            alu = matchD.group(1)
                            symbolName_1_full = ''.join(matchD.group(i) for i in range(2, 6) if matchD.group(i))
                            matchE = re.match(r'^\s*move\.([wl])\s+\((%a[0-7]),(%d[0-7])(\.[wl])?\),\s*(%d[0-7])', line_E)
                            if matchE and aN == matchE.group(2) and dN == matchE.group(3):
                                sE = matchE.group(1)
                                dP = matchE.group(5)
                                optimized_lines = [
                                    f'{matchA.group(1)}move.w{matchA.group(3)}{disp1}(sp),{dN}',
                                    f'{matchA.group(1)}move.l{matchA.group(3)}{disp2}(sp),{aN}',
                                    f'{matchA.group(1)}lea   {matchA.group(3)}{symbolName_1_full}({aN},{dN}.w),{aN}',
                                    f'{matchA.group(1)}move.{sE}{matchA.group(3)}({aN}),{dP}'
                                ]
                                return (optimized_lines, 5)

            # Calculates jump offsets is always a word length operation.
            # moveq[.wl] #0,dN              ->    move.w  symbolName1,dN       ; Saves 8 cycles
            # move.w     symbolName1,dN           add.w   dN,dN
            # add.[wl]   dN,dN                    move.w  label(pc,dN.w),dP
            # move.w     label(pc,dN.[wl]),dP     jmp     disp(pc,dP.w)
            # jmp        disp(pc,dP.w)
            # Where:
            # symbolName1[.w][-+*N][.bwl]
            # dP can be dN
            matchA = re.match(r'^(\s*)moveq(\.[wl])?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+([0-9a-zA-Z_\.]+)(\.w)?([\-\+\*]\d+)?(\.[bwl])?,\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(5):
                    symbolName_1_full = ''.join(matchB.group(i) for i in range(1, 5) if matchB.group(i))
                    matchC = re.match(r'^\s*add\.([wl])\s+(%d[0-7]),\s*(%d[0-7])', line_C)
                    if matchC and dN == matchC.group(2) and dN == matchC.group(3):
                        matchD = re.match(r'^\s*move\.w\s+([0-9a-zA-Z_\.]+)\(%pc,(%d[0-7])(\.[wl])?\),\s*(%d[0-7])', line_D)
                        if matchD and dN == matchD.group(2):
                            label = matchD.group(1)
                            dP = matchD.group(4)
                            matchE = re.match(r'^\s*jmp\s+(-?\d+)\(%pc,(%d[0-7])(\.[wl])?\)', line_E)
                            if matchE and dP == matchE.group(2):
                                disp = matchE.group(1)
                                optimized_lines = [
                                    f'{matchA.group(1)}move.w{matchA.group(3)}{symbolName_1_full},{dN}',
                                    f'{matchA.group(1)}add.w {matchA.group(3)}{dN},{dN}',
                                    f'{matchA.group(1)}move.w{matchA.group(3)}{label}(%pc,{dN}.w),{dP}',
                                    f'{matchA.group(1)}jmp   {matchA.group(3)}{disp}(%pc,{dP}.w)'
                                ]
                                return (optimized_lines, 5)

            # This pattern comes up after applying optimization for lsr.w #8,dN
            # clr.w   dN           ->   move.w  dM,-(sp)       ; Saves 8 cycles
            # move.w  dM,dN             clr.w   dN
            # move.w  dN,-(sp)          move.b  (sp)+,dN
            # clr.w   dN
            # move.b  (sp)+,dN
            matchA = re.match(r'^(\s*)clr\.w(\s+)(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(3)
                matchB = re.match(r'^\s*move\.w\s+(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    dM = matchB.group(1)
                    matchC = re.match(r'^\s*move\.w\s+(%d[0-7]),\s*-\(%sp\)', line_C)
                    if matchC and dN == matchC.group(1):
                        matchD = re.match(r'^\s*clr\.w\s+(%d[0-7])', line_D)
                        if matchD and dN == matchD.group(1):
                            matchE = re.match(r'^\s*move\.b\s+\(%sp\)\+,\s*(%d[0-7])', line_E)
                            if matchE and dN == matchE.group(1):
                                optimized_lines = [
                                    f'{matchA.group(1)}move.w{matchA.group(2)}{dM},-(%sp)',
                                    f'{matchA.group(1)}clr.w {matchA.group(2)}{dN}',
                                    f'{matchA.group(1)}move.b{matchA.group(2)}(%sp)+,{dN}'
                                ]
                                return (optimized_lines, 5)

        # Add more multi-line patterns here for 5 lines

    # Check for patterns whenever we have at least 4 lines
    if multi_limit == 4:

        line_A = modified_lines[-4]
        line_B = modified_lines[-3]
        line_C = modified_lines[-2]
        line_D = modified_lines[-1]

        if OPTIMIZE_INLINE_ASM_BLOCKS:
            # If any line (already right stripped) ends with the flag that mandates to skip it from be optimized -> do nothing and return
            if (line_A.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_B.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_C.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_D.endswith(SKIP_OPTIMIZATION_FLAG)):
                return (None, 0)

        # move.w  disp1(Am),Dn    ->    movem.w  disp1(Am),Dn/Dm         ; Saves 8 cycles
        # move.w  disp2(Am),Dm          (movem does sign extension)
        # ext.l   Dn
        # ext.l   Dm
        matchA = move_disp_aN_into_xN_pattern.match(line_A)
        if matchA:
            matchB = move_disp_aN_into_xN_pattern.match(line_B)
            if matchB:
                sA = matchA.group(2)
                sB = matchB.group(2)
                dN = matchA.group(9)
                dM = matchB.group(9)

                # Same size?
                if sA == 'w' and sB == 'w':
                    # stride 2 for words
                    stride = 2

                    # Extract displacements and address registers
                    dispA, aregA = get_displacement_and_areg(matchA)
                    dispB, aregB = get_displacement_and_areg(matchB)
                    aM = aregA

                    # Coincident address registers and consecutive displacements?
                    # As any disp can be 0 then use "is not None"
                    if aregB and aregB == aM and dispA is not None and dispB is not None and dispB == dispA + stride:
                        matchC = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_C)
                        matchD = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_D)

                        # Do both match with dN and dM?
                        if matchC and matchD and dN == matchC.group(1) and dM == matchD.group(1):
                            # Ensure dN is smaller than dM
                            d_reg_1 = int(dN[2])  # reg index
                            d_reg_2 = int(dM[2])  # reg index
                            if d_reg_1 < d_reg_2:
                                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 4)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.w{matchA.group(2)}{dispA}({aM}),{dN}/{dM}'
                                ]
                                return (optimized_lines, 4)

        # move.w  disp1(Am),Dn    ->    movem.w  disp1(Am),Dn/Dm         ; Saves 8 cycles
        # ext.l   Dn                    (movem does sign extension)
        # move.w  disp2(Am),Dm
        # ext.l   Dm
        matchA = move_disp_aN_into_xN_pattern.match(line_A)
        if matchA:
            matchC = move_disp_aN_into_xN_pattern.match(line_C)
            if matchC:
                sA = matchA.group(2)
                sC = matchC.group(2)
                dN = matchA.group(9)
                dM = matchC.group(9)

                # Same size?
                if sA == 'w' and sC == 'w':
                    # stride 2 for words
                    stride = 2

                    # Extract displacements and address registers
                    dispA, aregA = get_displacement_and_areg(matchA)
                    dispC, aregC = get_displacement_and_areg(matchC)
                    aM = aregA

                    # Coincident address registers and consecutive displacements?
                    # As any disp can be 0 then use "is not None"
                    if aregC and aregC == aM and dispA is not None and dispC is not None and dispC == dispA + stride:
                        matchB = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_B)
                        matchD = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_D)

                        # Do both match with dN and dM?
                        if matchB and matchD and dN == matchB.group(1) and dM == matchD.group(1):
                            # Ensure dN is smaller than dM
                            d_reg_1 = int(dN[2])  # reg index
                            d_reg_2 = int(dM[2])  # reg index
                            if d_reg_1 < d_reg_2:
                                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 4)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.w{matchA.group(2)}{dispA}({aM}),{dN}/{dM}'
                                ]
                                return (optimized_lines, 4)

        # move.w  (Am)+,Dn      ->   movem.w  (Am)+,Dn/Dm
        # move.w  (Am)+,Dm           (movem does sign extension)
        # ext.l   Dn
        # ext.l   Dm
        matchA = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)\+,\s*(%d[0-7])', line_A)
        if matchA:
            aM = matchA.group(3)
            dN = matchA.group(4)
            matchB = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)\+,\s*(%d[0-7])', line_B)
            if matchB and aM == matchB.group(3):
                dM = matchB.group(4)
                matchC = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_C)
                matchD = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_D)
                # Do both match with dN and dM in any order?
                if matchC and matchD and dN == matchC.group(1) and dM == matchD.group(1):
                    # Ensure dN is smaller than dM
                    d_reg_1 = int(dN[2])  # reg index
                    d_reg_2 = int(dM[2])  # reg index
                    if d_reg_1 < d_reg_2:
                        optimized_lines = [
                            f'{matchA.group(1)}movem.w{matchA.group(2)}({aM})+,{dN}/{dM}'
                        ]
                        return (optimized_lines, 4)

        # move.w  (Am)+,Dn      ->   movem.w  (Am)+,Dn/Dm
        # ext.l   Dn                 (movem does sign extension)
        # move.w  (Am)+,Dm
        # ext.l   Dm
        matchA = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)\+,\s*(%d[0-7])', line_A)
        if matchA:
            aM = matchA.group(3)
            dN = matchA.group(4)
            matchC = re.match(r'^(\s*)move\.w(\s+)\((%a[0-7]|%sp)\)\+,\s*(%d[0-7])', line_C)
            if matchC and aM == matchC.group(3):
                dM = matchC.group(4)
                matchB = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_B)
                matchD = re.match(r'^\s*ext\.l\s+(%d[0-7])', line_D)
                # Do both match with dN and dM?
                if matchB and matchD and dN == matchB.group(1) and dM == matchD.group(1):
                    # Ensure dN is smaller than dM
                    d_reg_1 = int(dN[2])  # reg index
                    d_reg_2 = int(dM[2])  # reg index
                    if d_reg_1 < d_reg_2:
                        optimized_lines = [
                            f'{matchA.group(1)}movem.w{matchA.group(2)}({aM})+,{dN}/{dM}'
                        ]
                        return (optimized_lines, 4)

        # Test if aN is in range 0xFFFF8000 <= aN <= 0x00007FFF (-32768 <= aN <= 32767)
        # cmpa.w/l  #0x8000,aN     ->   cmpa.w   aN,aN
        # blt       OutOfRange          bne      OutOfRange
        # cmpa.w/l  #0x7FFF,aN
        # bgt       OutOfRange
        # Note: we also considered the inverted order of instructions
        matchA = re.match(r'^(\s*)cmpa\.[wl](\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            # Considers both blt and bgt appearing in line_B
            matchB = re.match(r'^(\s*)(blt|jlt|bgt|jgt)(\.[bsw])?(\s+)([0-9a-zA-Z_\.]+)', line_B)
            if matchB:
                matchC = re.match(r'^(\s*)cmpa\.[wl](\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_C)
                if matchC:
                    # Considers both blt and bgt appearing in line_D
                    matchD = re.match(r'^(\s*)(blt|jlt|bgt|jgt)(\.[bsw])?(\s+)([0-9a-zA-Z_\.]+)', line_D)
                    if matchD:
                        aN = matchA.group(4)
                        label = matchB.group(5)
                        if matchC.group(4) == aN and matchD.group(5) == label:
                            s_label = '' if not matchB.group(3) else matchB.group(3)
                            val_low = parseConstantSigned(matchA.group(3), 16)
                            val_high = parseConstantSigned(matchC.group(3), 16)
                            if (val_low == -32768 and val_high == 32767) or (val_high == -32768 and val_low == 32767):
                                optimized_lines = [
                                    f'{matchA.group(1)}cmpa.w{matchA.group(2)}{aN},{aN}',
                                    f'{matchA.group(1)}bne{s_label}{matchA.group(2)}{label}'
                                ]
                                return (optimized_lines, 4)

        # Test if dN is in range 0xFFFF8000 <= dN <= 0x00007FFF (-32768 <= dN <= 32767)
        # cmp.l     #0xFFFF8000,dN     ->   move.w   dN,aN
        # blt       OutOfRange              cmpa.w   aN,aN
        # cmp.l     #0x00007FFF,dN          bne      OutOfRange
        # bgt       OutOfRange
        # Note: we also considered the inverted order of instructions
        # Needs a free aN register
        matchA = re.match(r'^(\s*)cmp[i]?\.[wl](\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
        if matchA:
            # Considers both blt and bgt appearing in line_B
            matchB = re.match(r'^(\s*)(blt|jlt|bgt|jgt)(\.[bsw])?(\s+)([0-9a-zA-Z_\.]+)', line_B)
            if matchB:
                matchC = re.match(r'^(\s*)cmp[i]?\.[wl](\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_C)
                if matchC:
                    # Considers both blt and bgt appearing in line_D
                    matchD = re.match(r'^(\s*)(blt|jlt|bgt|jgt)(\.[bsw])?(\s+)([0-9a-zA-Z_\.]+)', line_D)
                    if matchD:
                        dN = matchA.group(4)
                        label = matchB.group(5)
                        if matchC.group(4) == dN and matchD.group(5) == label:
                            s_label = '' if not matchB.group(3) else matchB.group(3)
                            val_low = parseConstantSigned(matchA.group(3), 16)
                            val_high = parseConstantSigned(matchC.group(3), 16)
                            aN = find_free_after_use_address_register([], i_line, lines, modified_lines)[0]
                            if aN is None:
                                aN = find_unused_address_register([], i_line, lines, modified_lines)[0]
                            if aN is not None:
                                if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([aN], i_line, lines, modified_lines):
                                    if (val_low == -32768 and val_high == 32767) or (val_high == -32768 and val_low == 32767):
                                        optimized_lines = [
                                            f'{matchA.group(1)}move.w{matchA.group(2)}{dN},{aN}',
                                            f'{matchA.group(1)}cmpa.w{matchA.group(2)}{aN},{aN}',
                                            f'{matchA.group(1)}bne{s_label}{matchA.group(2)}{label}'
                                        ]
                                        return (optimized_lines, 4)

        if USE_FABRI1983_MOVEM_OPTIMIZATIONS:

            # Consecutively push into stack a sequence of registers
            # move.[wl]  xN4,-(aN)   ->   movem.[wl]  xN4/xN3/xN2/xN1,-(aN)      ; Saves 8 cycles
            # move.[wl]  xN3,-(aN)
            # move.[wl]  xN2,-(aN)
            # move.[wl]  xN1,-(aN)
            # IMPORTANT: movem.l regs,-(An) starts reading reg x7 and goes down to x0
            push_xn_into_stack_pattern = r'^(\s*)move\.([wl])(\s+)(%[ad][0-7]),\s*-\((%a[0-7]|%sp)\)'
            matchA = re.match(push_xn_into_stack_pattern, line_A)
            if matchA:
                s = matchA.group(2)
                aN = matchA.group(5)
                matchB = re.match(push_xn_into_stack_pattern, line_B)
                if matchB and s == matchB.group(2) and aN == matchB.group(5):
                    matchC = re.match(push_xn_into_stack_pattern, line_C)
                    if matchC and s == matchC.group(2) and aN == matchC.group(5):
                        matchD = re.match(push_xn_into_stack_pattern, line_D)
                        if matchD and s == matchD.group(2) and aN == matchD.group(5):
                            xN4 = matchA.group(4)
                            xN3 = matchB.group(4)
                            xN2 = matchC.group(4)
                            xN1 = matchD.group(4)
                            xregs = [xN4, xN3, xN2, xN1]
                            # Check if registers are sorted in their categories
                            reversed_xregs = xregs[::-1]
                            if are_regs_sorted(reversed_xregs):
                                # Format register list for movem
                                xreg_list = '/'.join(f'{r}' for r in xregs)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.{s}{matchA.group(3)}{xreg_list},-({aN})'
                                ]
                                return (optimized_lines, 4)

            # Consecutively pop from stack into a sequence of registers
            # move.[wl]  (aN)+,xN1   ->   movem.[wl]  (aN)+,xN1/xN2/xN3/xN4      ; Saves 4 cycles
            # move.[wl]  (aN)+,xN2
            # move.[wl]  (aN)+,xN3
            # move.[wl]  (aN)+,xN4
            pop_xn_from_stack_pattern = r'^(\s*)move\.([wl])(\s+)\((%a[0-7]|%sp)\)\+,\s*(%[ad][0-7])'
            matchA = re.match(pop_xn_from_stack_pattern, line_A)
            if matchA:
                s = matchA.group(2)
                aN = matchA.group(4)
                matchB = re.match(pop_xn_from_stack_pattern, line_B)
                if matchB and s == matchB.group(2) and aN == matchB.group(4):
                    matchC = re.match(pop_xn_from_stack_pattern, line_C)
                    if matchC and s == matchC.group(2) and aN == matchC.group(4):
                        matchD = re.match(pop_xn_from_stack_pattern, line_D)
                        if matchD and s == matchD.group(2) and aN == matchD.group(4):
                            xN1 = matchA.group(5)
                            xN2 = matchB.group(5)
                            xN3 = matchC.group(5)
                            xN4 = matchD.group(5)
                            xregs = [xN1, xN2, xN3, xN4]
                            # Check if registers are sorted in their categories
                            if are_regs_sorted(xregs):
                                # Format register list for movem
                                xreg_list = '/'.join(f'{r}' for r in xregs)
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.{s}{matchA.group(3)}({aN})+,{xreg_list}'
                                ]
                                return (optimized_lines, 4)

            # Move consecutive words or longs with fixed stride
            # move.[wl]  disp1(aN),xN    ->   movem.[wl] disp1(aN),xN/xM/xP/xQ      ; Saves 8 cycles
            # move.[wl]  disp2(aN),xM         (4th line here if it didn't satisfy the criteria)
            # move.[wl]  disp3(aN),xP
            # move.[wl]  disp4(aN),xQ    <- this could be whatever line
            # aN is address register or sp.
            # Where disp1 to disp4 are consecutive displacements with the correct stride: +2 for word, +4 for long.
            # Where xN,xM,xP,xQ are already sorted by data reg type and then address reg type, with consecutive reg index per type.
            # Note that gcc might put the displacement like next: (d,aN)
            matchA = move_disp_aN_into_xN_pattern.match(line_A)
            if matchA:
                matchB = move_disp_aN_into_xN_pattern.match(line_B)
                matchC = move_disp_aN_into_xN_pattern.match(line_C)
                if matchB and matchC:
                    sA = matchA.group(2)
                    sB = matchB.group(2)
                    sC = matchC.group(2)

                    # All same size?
                    if sA == sB == sC:
                        # stride 2 for words, stride 4 for longs
                        stride = 2 if sA == 'w' else 4

                        # Extract displacements and address registers (they can be None)
                        dispA, aregA = get_displacement_and_areg(matchA)
                        dispB, aregB = get_displacement_and_areg(matchB)
                        dispC, aregC = get_displacement_and_areg(matchC)

                        # Same address registers and consecutive displacements?
                        are_same_aregs = aregA and aregA == aregB and aregC and aregC == aregB
                        # As any disp can be 0 then use "is not None"
                        are_consecutive_disps = dispA is not None and dispB is not None and dispC is not None and dispB == dispA + stride and dispC == dispB + stride
                        if are_same_aregs and are_consecutive_disps:

                            # At this point we have at least three consecutive moves

                            disps = [dispA, dispB, dispC]
                            xregs = [matchA.group(9), matchB.group(9), matchC.group(9)]

                            # Check for fourth consecutive move
                            matchD = move_disp_aN_into_xN_pattern.match(line_D)
                            matchD_ok = False
                            if matchD and matchD.group(2) == sA:
                                dispD, aregD = get_displacement_and_areg(matchD)
                                if aregD == aregA and dispD is not None and dispD == dispC + stride:
                                    xregs.append(matchD.group(9))
                                    disps.append(dispD)
                                    matchD_ok = True

                            # Check if registers are sorted in their categories
                            if are_regs_sorted(xregs):
                                # Format the register list for movem
                                xreg_list = '/'.join(f'{r}' for r in xregs)
                                first_disp = '' if dispA == 0 else dispA
                                optimized_lines = [
                                    f'{matchA.group(1)}movem.{sA}{matchA.group(3)}{first_disp}({aregA}),{xreg_list}'
                                ]
                                if not matchD_ok:
                                    optimized_lines.append(line_D)
                                return (optimized_lines, 4)

            # Move pseudo-consecutive words or longs with fixed stride but 1, 2, or 3 wrong strides.
            # The gap left by the wrong stride will be filled by a free register.
            # move.[wl]  disp1(aN),xN    ->   (1st line here if it has wrong stride)      ; Saves [4,8,12] cycles
            # move.[wl]  disp2(aN),xM         movem.[wl] disp(aN),regs_list
            # move.[wl]  disp3(aN),xP         (4th line here if it has wrong stride)
            # move.[wl]  disp4(aN),xQ
            # aN is address register or sp.
            # Where disp1 to disp4 are increasing displacements with 1, 2, or 3 wrong strides.
            # Where xN,xM,xP,xQ are already sorted by data reg type and then address reg type, with increasing reg index per type.
            # Test case:
            #    move.w 12(%a2),%d7
            #    move.w 14(%a2),%a3
            #    move.w 18(%a2),%a5  <- here we have to find a free reg between a3 and a5
            #    move.w 22(%a2),%d4  <- d4 is not in order with previous regs
            matchA = move_disp_aN_into_xN_pattern.match(line_A)
            if matchA:
                matchB = move_disp_aN_into_xN_pattern.match(line_B)
                matchC = move_disp_aN_into_xN_pattern.match(line_C)
                matchD = move_disp_aN_into_xN_pattern.match(line_D)
                if matchB and matchC and matchD:
                    sA = matchA.group(2)
                    sB = matchB.group(2)
                    sC = matchC.group(2)
                    sD = matchD.group(2)

                    # All same size?
                    if sA == sB == sC == sD:
                        # stride 2 for words, stride 4 for longs
                        stride = 2 if sA == 'w' else 4

                        # Extract displacements and address registers (they can be None)
                        dispA, aregA = get_displacement_and_areg(matchA)
                        dispB, aregB = get_displacement_and_areg(matchB)
                        dispC, aregC = get_displacement_and_areg(matchC)
                        dispD, aregD = get_displacement_and_areg(matchD)

                        # Same address registers?
                        are_same_aregs = aregA and aregA == aregB and aregC and aregC == aregB and aregD and aregD == aregC
                        # Only if first or last 3 xregs are in order due to min movem amount of regs to save on cycles
                        are_first_three_xregs_sorted = are_regs_sorted([matchA.group(9), matchB.group(9), matchC.group(9)])
                        are_last_three_xregs_sorted = are_regs_sorted([matchB.group(9), matchC.group(9), matchD.group(9)])

                        if are_same_aregs and (are_first_three_xregs_sorted or are_last_three_xregs_sorted):

                            disps = [dispA, dispB, dispC, dispD]
                            xregs = [matchA.group(9), matchB.group(9), matchC.group(9), matchD.group(9)]

                            # Define the register order for comparison
                            register_order = ['%d0','%d1','%d2','%d3','%d4','%d5','%d6','%d7','%a0','%a1','%a2','%a3','%a4','%a5','%a6','%sp']

                            # Detect which regs are using wrong strides by saving the wrong gap
                            wrong_stride_gaps_with_increasing_xreg = [0] * len(disps)  # Initialized with 0
                            for i in range(1, len(disps)):
                                actual_gap = disps[i] - disps[i-1]
                                xregs_increasing = register_order.index(xregs[i-1]) < register_order.index(xregs[i])

                                # If the gap is larger than expected stride and the involved xregs are increasing, 
                                # save the wrong gap at index
                                if actual_gap > stride and xregs_increasing:
                                    wrong_stride_gaps_with_increasing_xreg[i] = actual_gap

                            # Special case when there is a wrong gap between dispA and dispB but is correct between dispB and dispC,
                            # meaning that the dispA is wrong and not dispB with dispA
                            if wrong_stride_gaps_with_increasing_xreg[1] != 0 and wrong_stride_gaps_with_increasing_xreg[2] == 0:
                                wrong_stride_gaps_with_increasing_xreg[0] = wrong_stride_gaps_with_increasing_xreg[1]
                                wrong_stride_gaps_with_increasing_xreg[1] = 0
                            
                            '''print("---------")
                            print(line_A)
                            print(line_B)
                            print(line_C)
                            print(line_D)
                            print(f"wrong_stride_gaps_with_increasing_xreg: {wrong_stride_gaps_with_increasing_xreg}")'''

                            # Count how many disp(aN) with wrong strides we have
                            disp_aN_with_wrong_gaps = 0
                            for i in range(len(wrong_stride_gaps_with_increasing_xreg)):
                                if wrong_stride_gaps_with_increasing_xreg[i] != 0:
                                    disp_aN_with_wrong_gaps += 1
                                    #print(f"  {disps[i]}({xregs[i]})")

                            #print(f"disp(aN) with wrong gaps: {disp_aN_with_wrong_gaps}")

                            # Separate used regs
                            used_data_regs = [r for r in xregs if r.startswith('%d')]
                            used_addr_regs = [r for r in xregs if r.startswith('%a')]

                            # Get free data regs
                            free_data_regs_1 = find_free_after_use_data_register(used_data_regs, i_line, lines, modified_lines)
                            free_data_regs_2 = find_unused_data_register(used_data_regs, i_line, lines, modified_lines)
                            free_data_regs_1 = [] if free_data_regs_1[0] == None else free_data_regs_1
                            free_data_regs_2 = [] if free_data_regs_2[0] == None else free_data_regs_2
                            free_data_regs = sorted(list(set(free_data_regs_1) | set(free_data_regs_2)), key=lambda r: int(r[2:]))

                            # Get free address regs
                            free_addr_regs_1 = find_free_after_use_address_register(used_addr_regs, i_line, lines, modified_lines)
                            free_addr_regs_2 = find_unused_address_register(used_addr_regs, i_line, lines, modified_lines)
                            free_addr_regs_1 = [] if free_addr_regs_1[0] == None else free_addr_regs_1
                            free_addr_regs_2 = [] if free_addr_regs_2[0] == None else free_addr_regs_2
                            free_addr_regs = sorted(list(set(free_addr_regs_1) | set(free_addr_regs_2)), key=lambda r: int(r[2:]))
                            
                            free_regs = free_data_regs + free_addr_regs
                            #print(f"free_regs: {free_regs}")

                            # A consecutively immediate bigger or smaller reg is based on next order: d0,d1,d2,d3,d4,d5,d6,d7,a0,a1,a2,a3,a4,a5,a6
                            # Eg:
                            #    A consecutively immediate bigger reg than d2 is d3 (or whatever is next to d2)
                            #    A consecutively immediate smaller reg than d2 is d1 (or whatever is prio to d2)

                            # Visit wrong_stride_gaps_with_increasing_xreg[].
                            # If wrong_stride_gaps_with_increasing_xreg[0] != 0 (ie wrong gap) then we need a free reg consecutively immediate bigger 
                            # than the reg in xregs[0] but smaller than xregs[1].
                            # For the remaining wrong_stride_gaps_with_increasing_xreg[i] != 0 we need a free reg consecutively immediate smaller than 
                            # the reg in xregs[i] but bigger than xregs[i-1].
                            # Once a free reg is picked it has to be removed.
                            additional_regs = []

                            for gap_index in range(len(wrong_stride_gaps_with_increasing_xreg)):
                                if wrong_stride_gaps_with_increasing_xreg[gap_index] != 0:
                                    if gap_index == 0:
                                        # First gap: need register bigger than xregs[0] but smaller than xregs[1]
                                        current_idx = register_order.index(xregs[0])
                                        next_idx = register_order.index(xregs[1])

                                        # Find the first free reg in the range set before
                                        for candidate_idx in range(current_idx + 1, next_idx):
                                            candidate_reg = register_order[candidate_idx]
                                            if candidate_reg in free_regs:
                                                additional_regs.append(candidate_reg)
                                                free_regs.remove(candidate_reg)
                                                break
                                    else:
                                        # Subsequent gaps (1, 2): need register smaller than xregs[i] but bigger than xregs[i-1]
                                        prev_idx = register_order.index(xregs[gap_index - 1])
                                        current_idx = register_order.index(xregs[gap_index])
                                        
                                        # Find the first free reg in the range set before
                                        for candidate_idx in range(prev_idx + 1, current_idx):
                                            candidate_reg = register_order[candidate_idx]
                                            if candidate_reg in free_regs:
                                                additional_regs.append(candidate_reg)
                                                free_regs.remove(candidate_reg)
                                                break

                            #print(f'additional_regs: {additional_regs}')

                            if len(additional_regs) > 0 and len(additional_regs) == disp_aN_with_wrong_gaps:

                                if add_regs_into_push_pop_if_not_scratch_or_in_interrupt(additional_regs, i_line, lines, modified_lines):

                                    xregs_for_movem = []

                                    # Only add first xreg if it is in correct increasing order
                                    if register_order.index(xregs[0]) < register_order.index(xregs[1]):
                                        xregs_for_movem.append(xregs[0])

                                    if wrong_stride_gaps_with_increasing_xreg[0] != 0:
                                        xregs_for_movem.append(additional_regs.pop(0))
                                    if wrong_stride_gaps_with_increasing_xreg[1] != 0:
                                        xregs_for_movem.append(additional_regs.pop(0))
                                    xregs_for_movem.append(xregs[1])
                                    if wrong_stride_gaps_with_increasing_xreg[2] != 0:
                                        xregs_for_movem.append(additional_regs.pop(0))
                                    xregs_for_movem.append(xregs[2])
                                    if wrong_stride_gaps_with_increasing_xreg[3] != 0:
                                        xregs_for_movem.append(additional_regs.pop(0))

                                    # Only add last xreg if it is in correct increasing order
                                    if register_order.index(xregs[3]) > register_order.index(xregs[2]):
                                        xregs_for_movem.append(xregs[0])

                                    # Format the register list for movem
                                    xregs_for_movem_str = '/'.join(f'{r}' for r in xregs_for_movem)
                                    
                                    # First xreg is not in correct increasing order
                                    if register_order.index(xregs[0]) > register_order.index(xregs[1]):
                                        first_disp = '' if dispA + stride == 0 else dispA + stride
                                        optimized_lines = [
                                            line_A,
                                            f'{matchA.group(1)}movem.{sA}{matchA.group(3)}{first_disp}({aregA}),{xregs_for_movem_str}'
                                        ]
                                        return (optimized_lines, 4)
                                    # Last xreg is not in correct increasing order
                                    elif register_order.index(xregs[2]) > register_order.index(xregs[3]):
                                        first_disp = '' if dispA == 0 else dispA
                                        optimized_lines = [
                                            f'{matchA.group(1)}movem.{sA}{matchA.group(3)}{first_disp}({aregA}),{xregs_for_movem_str}',
                                            line_D
                                        ]
                                        return (optimized_lines, 4)

        if USE_FABRI1983_OPTIMIZATIONS:

            # Calculates offset indexes for accessing arrays.
            # and.l      #65535,dN       ->    add/sub.w  dN,dN            ; Saves 20 cycles (16 cycles saved from removed and.l)
            # add/sub.l  dN,dN                 lea        symbolName1,aN
            # lea        symbolName1,aN        move.[wl]  disp(sp),(aN,dN.w)
            # move.[wl]  disp(sp),(aN,dN.[wl])
            # Where:
            # symbolName1[.wl][-+*N][.bwl]
            # Displacement d in d(sp) is optional
            matchA = re.match(r'^(\s*)(andi|and)\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(3)
                matchB = re.match(r'^\s*(add|sub)\.l\s+(%d[0-7]),(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2) and dN == matchB.group(3):
                    alu = matchB.group(1)
                    matchC = re.match(r'^\s*lea\s+([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_C)
                    if matchC:
                        symbolName_1_full = ''.join(matchC.group(i) for i in range(1, 5) if matchC.group(i))
                        aN = matchC.group(5)
                        matchD = re.match(r'^\s*move\.([wl])\s+(-?\d+)?\(%sp\),\s*\((%a[0-7]),(%d[0-7])(\.[wl])?\)', line_D)
                        if matchD and aN == matchD.group(3) and dN == matchD.group(4):
                            sD = matchD.group(1)
                            disp = '' if matchD.group(2) is None else matchD.group(2)
                            optimized_lines = [
                                f'{matchA.group(1)}{alu}.w {matchA.group(3)}{dN},{dN}',
                                f'{matchA.group(1)}lea   {matchA.group(3)}{symbolName_1_full},{aN}',
                                f'{matchA.group(1)}move.{sD}{matchA.group(3)}{disp}(%sp),({aN},{dN}.w)'
                            ]
                            return (optimized_lines, 4)

            # This pattern comes up after applying optimization for lsr.w #8,dN
            # move.w  dM,dN        ->   move.w  dM,-(sp)       ; Saves 4 cycles
            # move.w  dN,-(sp)          clr.w   dN
            # clr.w   dN                move.b  (sp)+,dN
            # move.b  (sp)+,dN
            matchA = re.match(r'^(\s*)move\.w(\s+)(%d[0-7]),\s*(%d[0-7])', line_A)
            if matchA:
                dM = matchA.group(3)
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+(%d[0-7]),\s*-\(%sp\)', line_B)
                if matchB and dN == matchB.group(1):
                    matchC = re.match(r'^\s*clr\.w\s+(%d[0-7])', line_C)
                    if matchC and dN == matchC.group(1):
                        matchD = re.match(r'^\s*move\.b\s+\(%sp\)\+,\s*(%d[0-7])', line_D)
                        if matchD and dN == matchD.group(1):
                            optimized_lines = [
                                f'{matchA.group(1)}move.w{matchA.group(2)}{dM},-(%sp)',
                                f'{matchA.group(1)}clr.w {matchA.group(2)}{dN}',
                                f'{matchA.group(1)}move.b{matchA.group(2)}(%sp)+,{dN}'
                            ]
                            return (optimized_lines, 4)

            # Unnecessary redundant initial move dN into aN
            # move.[wl]      dN,aN       ->   add*/sub*.[wl] #val,dN      ; Saves 4 cycles
            # add*/sub*.[wl] #val,aN          move.[wl]      dN,d(aM)
            # move.[wl]      aN,disp(aM)      move.[wl]      dN,aN
            # move.[wl]      aN,dN
            matchA = re.match(r'^(\s*)(move|movea)\.([wl])(\s+)(%d[0-7]),\s*(%a[0-7])', line_A)
            if matchA:
                s = matchA.group(3)
                dN = matchA.group(5)
                aN = matchA.group(6)
                matchB = re.match(r'^\s*(add|adda|addq|sub|suba|subq)\.([wl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7])', line_B)
                if matchB and s == matchB.group(2) and aN == matchB.group(4):
                    alu = matchB.group(1)
                    val = matchB.group(3)
                    matchC = re.match(r'^\s*move\.([wl])\s+(%a[0-7]),\s*(?:(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7]|%sp)\)|\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?,(%a[0-7]|%sp)\))', line_C)
                    if matchC and s == matchC.group(1) and aN == matchC.group(2):
                        matchD = re.match(r'^\s*move\.([wl])\s+(%a[0-7]),\s*(%d[0-7])', line_D)
                        if matchD and s == matchD.group(1) and aN == matchD.group(2) and dN == matchD.group(3):
                            aM = matchC.group(4) or matchC.group(6)
                            # Try first matching group: d(aN)
                            dispC = 0 if matchC.group(3) is None else parseConstantSigned(matchC.group(3), 16)
                            if dispC == 0:
                                # Try second matching group: (d,aN)
                                dispC = 0 if matchC.group(5) is None else parseConstantSigned(matchC.group(5), 16)
                            disp_str = '' if dispC == 0 else f'{dispC}'
                            optimized_lines = [
                                f'{matchA.group(1)}{alu}.{s} {matchA.group(4)}#{val},{dN}',
                                f'{matchA.group(1)}move.{s}{matchA.group(4)}{dN},{disp_str}({aM})',
                                f'{matchA.group(1)}move.{s}{matchA.group(4)}{dN},{aN}'
                            ]
                            return (optimized_lines, 4)

            # Unnecessary clear of data register to multiply by 2 an address register
            # moveq[.l]  #0,dN     ->    add.l   aN,aN         ; Saves 12 cycles. Leaves dN with different value than expected.
            # move.w     aN,dN
            # move.l     dN,aN
            # add/sub.l  aN,aN
            matchA = re.match(r'^(\s*)moveq(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+(%a[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    aN = matchB.group(1)
                    matchC = re.match(r'^\s*(move|movea)\.l\s+(%d[0-7]),\s*(%a[0-7])', line_C)
                    if matchC and dN == matchC.group(2) and aN == matchC.group(3):
                        matchD = re.match(r'^\s*(add|adda|sub|suba)\.l\s+(%a[0-7]),\s*(%a[0-7])', line_D)
                        if matchD and aN == matchD.group(2) and aN == matchD.group(3):
                            if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                                alu = matchD.group(1)
                                optimized_lines = [
                                    f'{matchA.group(1)}{alu}.l{matchA.group(3)}{aN},{aN}'
                                ]
                                return (optimized_lines, 4)

            # Unnecessary clear of data register to multiply by 2 an address register and add/sub a constant
            # move.w     aN,dN     ->   add.l      aN,aN           ; Saves 4 cycles. Leaves dN with different value than expected.
            # lsl.l      #2,dN          add.l      aN,aN
            # move.l     dN,aN          add/sub.l  #val,aN
            # add/sub.l  #val,aN
            matchA = re.match(r'^(\s*)move\.w(\s+)(%a[0-7]),\s*(%d[0-7])', line_A)
            if matchA:
                aN = matchA.group(3)
                dN = matchA.group(4)
                matchB = re.match(r'^\s*(lsl|asl)\.l\s+#2,\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    matchC = re.match(r'^\s*(move|movea)\.l\s+(%d[0-7]),\s*(%a[0-7])', line_C)
                    if matchC and dN == matchC.group(2) and aN == matchC.group(3):
                        matchD = re.match(r'^\s*(add|adda|addq|sub|suba|subq)\.l\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7])', line_D)
                        if matchD and aN == matchD.group(3):
                            alu = matchD.group(1)
                            val = matchD.group(2)
                            if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                                optimized_lines = [
                                    f'{matchA.group(1)}add.l{matchA.group(2)}{aN},{aN}',
                                    f'{matchA.group(1)}add.l{matchA.group(2)}{aN},{aN}',
                                    f'{matchA.group(1)}{alu}.l{matchA.group(2)}#{val},{aN}'
                                ]
                                return (optimized_lines, 4)

        # Tail recursion for BSR/JSR or exploiting PEA opportunities
        matchA = re.match(r'^(\s*)(bsr|jsr)(\.[bsw])?(\s+)([0-9a-zA-Z_\.]+)', line_A)
        if matchA:

            # Tail recursion. Replace many BSR/JSR+RTS by many PEA+BRA/JMP
            # bsr/jsr subr1     ->    pea subr3          ; Saves 16 cycles. Different stack depth
            # bsr/jsr subr2           pea subr2
            # bsr/jsr subr3           bra/jmp subr1
            # rts
            matchD = re.match(r'^\s*rts\b', line_D)
            if matchD:
                bsr_jsr_routine = r'^\s*(bsr|jsr)(\.[bsw])?\s+([0-9a-zA-Z_\.]+)'
                matchB = re.match(bsr_jsr_routine, line_B)
                matchC = re.match(bsr_jsr_routine, line_C)
                if matchB and matchC:
                    subr1 = matchA.group(5)
                    subr2 = matchB.group(3)
                    subr3 = matchC.group(3)
                    last_instr = "jmp  "
                    if not matchA.group(2) == "jsr":
                        last_instr = "bra  "
                        if matchA.group(3):
                            last_instr = f'bra{matchA.group(3)}'
                    optimized_lines = [
                        f'{matchA.group(1)}pea  {matchA.group(4)}{subr3}',
                        f'{matchA.group(1)}pea  {matchA.group(4)}{subr2}',
                        f'{matchA.group(1)}{last_instr}{matchA.group(4)}{subr1}'
                    ]
                    return (optimized_lines, 4)
                                        
        if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION:

            # Clearing consecutively the stack by just offseting the sp.
            # clr.w  -(sp)     ->    subq    #8,sp         ; Saves 48 cycles.
            # clr.w  -(sp)
            # clr.w  -(sp)
            # clr.w  -(sp)
            matchA = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line_A)
            if matchA:
                matchB = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_B)
                if matchB:
                    matchC = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_C)
                    if matchC:
                        matchD = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_D)
                        if matchD:
                            optimized_lines = [
                                f'{matchA.group(1)}subq{matchA.group(2)}#8,%sp'
                            ]
                            return (optimized_lines, 4)

            # Clearing consecutively the stack by just offseting the sp.
            # clr.l  -(sp)     ->    lea     -16(sp),sp    ; Saves 80 cycles.
            # clr.l  -(sp)
            # clr.l  -(sp)
            # clr.l  -(sp)
            # Also considers:  pea  0.w
            matchA_clr = re.match(r'^(\s*)clr\.l(\s+)-\(%sp\)', line_A)
            matchA_pea = re.match(r'^(\s*)pea(\s+)0.w', line_A)
            matchA = matchA_clr or matchA_pea
            if matchA:
                matchB_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_B)
                matchB_pea = re.match(r'^\s*pea\s+0.w', line_B)
                if matchB_clr or matchB_pea:
                    matchC_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_C)
                    matchC_pea = re.match(r'^\s*pea\s+0.w', line_C)
                    if matchC_clr or matchC_pea:
                        matchD_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_D)
                        matchD_pea = re.match(r'^\s*pea\s+0.w', line_D)
                        if matchD_clr or matchD_pea:
                            optimized_lines = [
                                f'{matchA.group(1)}lea{matchA.group(2)}-16(%sp),%sp'
                            ]
                            return (optimized_lines, 4)

        else:

            # Clearing consecutively the stack by pushing 0.
            # clr.w  -(sp)     ->    pea     0.w           ; Saves 24 cycles.
            # clr.w  -(sp)           pea     0.w
            # clr.w  -(sp)
            # clr.w  -(sp)
            matchA = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line_A)
            if matchA:
                matchB = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_B)
                if matchB:
                    matchC = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_C)
                    if matchC:
                        matchD = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_D)
                        if matchD:
                            optimized_lines = [
                                f'{matchA.group(1)}pea{matchA.group(2)}0.w',
                                f'{matchA.group(1)}pea{matchA.group(2)}0.w'
                            ]
                            return (optimized_lines, 4)

            # Clearing consecutively the stack by pushing 0.
            # clr.l  -(sp)     ->    moveq   #0,dN         ; Saves 32 cycles.
            # clr.l  -(sp)           moveq   #0,dM
            # clr.l  -(sp)           moveq   #0,dP
            # clr.l  -(sp)           moveq   #0,dQ
            #                        movem.l dN/dM/dP/dQ,-(sp)
            # Needs 4 free data registers or already holding 0
            # Also considers:  pea  0.w
            matchA_clr = re.match(r'^(\s*)clr\.l(\s+)-\(%sp\)', line_A)
            matchA_pea = re.match(r'^(\s*)pea(\s+)0.w', line_A)
            matchA = matchA_clr or matchA_pea
            if matchA:
                matchB_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_B)
                matchB_pea = re.match(r'^\s*pea\s+0.w', line_B)
                if matchB_clr or matchB_pea:
                    matchC_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_C)
                    matchC_pea = re.match(r'^\s*pea\s+0.w', line_C)
                    if matchC_clr or matchC_pea:
                        matchD_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_D)
                        matchD_pea = re.match(r'^\s*pea\s+0.w', line_D)
                        if matchD_clr or matchD_pea:
                            free_d_regs = find_free_after_use_data_register([], i_line, lines, modified_lines)
                            if len(free_d_regs) < 4:
                                free_d_regs = find_unused_data_register([], i_line, lines, modified_lines)
                            if len(free_d_regs) >= 4:
                                dN, dM, dP, dQ = free_d_regs[:4]
                                if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dN,dM,dP,dQ], i_line, lines, modified_lines):
                                    optimized_lines = [
                                        f'{matchA.group(1)}moveq  {matchA.group(2)}#0,{dN}',
                                        f'{matchA.group(1)}moveq  {matchA.group(2)}#0,{dM}',
                                        f'{matchA.group(1)}moveq  {matchA.group(2)}#0,{dP}',
                                        f'{matchA.group(1)}moveq  {matchA.group(2)}#0,{dQ}',
                                        f'{matchA.group(1)}movem.l{matchA.group(2)}{dN}/{dM}/{dP}/{dQ},-(%sp)'
                                    ]
                                    return (optimized_lines, 4)

        # Add more multi-line patterns here for 4 lines

    # Check for patterns whenever we have at least 3 lines
    if multi_limit == 3:

        line_A = modified_lines[-3]
        line_B = modified_lines[-2]
        line_C = modified_lines[-1]

        if OPTIMIZE_INLINE_ASM_BLOCKS:
            # If any line (already right stripped) ends with the flag that mandates to skip it from be optimized -> do nothing and return
            if (line_A.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_B.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_C.endswith(SKIP_OPTIMIZATION_FLAG)):
                return (None, 0)

        matchA = re.match(r'^(\s*)(move|movea)\.([bwl])(\s+)(%[a][0-7]|%sp),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            matchC = re.match(r'^(\s*)(add|adda)\.([bwl])(\s+)(%[a][0-7]|%sp),\s*(%a[0-7]|%sp)', line_C)
            if matchC:
                sA = matchA.group(3)
                sC = matchA.group(3)
                aN = matchA.group(5)
                aP = matchA.group(6)
                aM = matchC.group(5)

                # Same size and same aP regs? And different regs?
                if sA == sC and aP == matchC.group(6) and aN != aP and aP != aM and aN != aM:

                    # If -32768 <= val <= 32767
                    # move.s  aN,aP      ->    lea     val(aN,aM),aP
                    # add.s   #val,aP
                    # add.s   aM,aP
                    # Considers case when add.s #val,aP is replaced by a addq.s
                    matchB = re.match(r'^(\s*)(add|adda|addq)\.([bwl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_B)
                    if matchB and sA == matchB.group(3) and aP == matchB.group(6):
                        val = parseConstantSigned(matchB.group(5), 32)
                        if sA == 'b':
                            val = parseConstantSigned(matchB.group(5), 8)
                        elif sA == 'w':
                            val = parseConstantSigned(matchB.group(5), 16)
                        if -32768 <= val <= 32767:
                            optimized_line = f'{matchC.group(1)}lea{matchC.group(4)}{val}({aN},{aM}),{aP}'
                            return ([optimized_line], 3)

                    # If -32768 <= val <= 32767
                    # move.s  aN,aP      ->    lea     -val(aN,aM),aP
                    # sub.s   #val,aP
                    # add.s   aM,aP
                    # Considers case when sub.s #val,aP is replaced by a subq.s
                    matchB = re.match(r'^(\s*)(sub|suba|subq)\.([bwl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_B)
                    if matchB and (matchB.group(2) == "subq" or sA == matchB.group(3)) and aP == matchB.group(6):
                        val = parseConstantSigned(matchB.group(5), 32)
                        if sA == 'b':
                            val = parseConstantSigned(matchB.group(5), 8)
                        elif sA == 'w':
                            val = parseConstantSigned(matchB.group(5), 16)
                        if -32768 <= val <= 32767:
                            optimized_line = f'{matchC.group(1)}lea{matchC.group(4)}{-val}({aN},{aM}),{aP}'
                            return ([optimized_line], 3)

        # If -32767 <= val <= 32767
        # move.l  aN,-(sp)   ->    link    aN,#val
        # move.l  sp,aN
        # add.w   #val,sp
        matchA = re.match(r'^(\s*)(move|movea)\.l(\s+)(%a[0-7]),\s*-\(%sp\)', line_A)
        if matchA:
            aN = matchA.group(4)
            matchB = re.match(r'^(\s*)(move|movea)\.l(\s+)%sp,\s*(%a[0-7])', line_B)
            if matchB and aN == matchB.group(4):
                matchC = re.match(r'^(\s*)(add|adda|addq)\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*%sp', line_C)
                if matchC:
                    val = parseConstantSigned(matchC.group(4), 16)
                    if -32767 <= val <= 32767:
                        optimized_line = f'{matchC.group(1)}link{matchC.group(3)}{aN},#{val}'
                        return ([optimized_line], 3)

        # Testing for null (or 0)
        # move.l  aN,-(sp)   ->    move.l  aN,dM           ; Saves 16 cycles
        # addq    #4,sp            beq     label
        # beq     label
        # Needs a free dM register
        matchA = re.match(r'^(\s*)(move|movea)\.l(\s+)(%a[0-7]),\s*-\(%sp\)', line_A)
        if matchA:
            matchB = re.match(r'^(\s*)(add|adda|addq)(?:\.[bwl])?(\s+)#4,\s*%sp', line_B)
            if matchB:
                matchC = re.match(r'^(\s*)(jeq|beq)(\.[bsw])?\s+([0-9a-zA-Z_\.]+)', line_C)
                if matchC:
                    aN = matchA.group(4)
                    label = matchC.group(4)
                    s_branch = '' if matchC.group(3) is None else matchC.group(3)
                    dM = find_free_after_use_data_register([], i_line, lines, modified_lines)[0]
                    if dM is None:
                        dM = find_unused_data_register([], i_line, lines, modified_lines)[0]
                    if dM is not None:
                        if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                            optimized_lines = [
                                f'{matchA.group(1)}move.l{matchA.group(3)}{aN},{dM}',
                                f'{matchA.group(1)}beq{s_branch}{matchA.group(3)}{label}'
                            ]
                            return (optimized_lines, 3)

        # Tail recursion for BSR/JSR or exploiting PEA opportunities
        matchA = re.match(r'^(\s*)(bsr|jsr)(\.[bsw])?(\s+)([0-9a-zA-Z_\.]+)', line_A)
        if matchA:

            # Tail recursion. Replace many BSR/JSR+RTS by many PEA+BRA/JMP
            # bsr/jsr subr1     ->    pea subr2            ; Saves 20 cycles. Different stack depth
            # bsr/jsr subr2           bra/jmp subr1
            # rts
            matchC = re.match(r'^\s*rts\b', line_C)
            if matchC:
                matchB = re.match(r'^\s*(bsr|jsr)(\.[bsw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    subr1 = matchA.group(5)
                    subr2 = matchB.group(3)
                    last_instr = "jmp  "
                    if not matchA.group(2) == "jsr":
                        last_instr = "bra  "
                        if matchA.group(3):
                            last_instr = f'bra{matchA.group(3)}'
                    optimized_lines = [
                        f'{matchA.group(1)}pea  {matchA.group(4)}{subr2}',
                        f'{matchA.group(1)}{last_instr}{matchA.group(4)}{subr1}'
                    ]
                    return (optimized_lines, 3)

        if USE_FABRI1983_MOVEM_OPTIMIZATIONS:

            # Consecutively push into stack a sequence of registers
            # move.[wl]  xN3,-(aN)   ->   movem.[wl]  xN3/xN2/xN1,-(aN)     ; Saves 4 cycles
            # move.[wl]  xN2,-(aN)
            # move.[wl]  xN1,-(aN)
            # IMPORTANT: movem.l regs,-(An) starts reading reg x7 and goes down to x0
            push_xn_into_stack_pattern = r'^(\s*)move\.([wl])(\s+)(%[ad][0-7]),\s*-\((%a[0-7]|%sp)\)'
            matchA = re.match(push_xn_into_stack_pattern, line_A)
            if matchA:
                s = matchA.group(2)
                aN = matchA.group(5)
                matchB = re.match(push_xn_into_stack_pattern, line_B)
                if matchB and s == matchB.group(2) and aN == matchB.group(5):
                    matchC = re.match(push_xn_into_stack_pattern, line_C)
                    if matchC and s == matchC.group(2) and aN == matchC.group(5):
                        xN3 = matchA.group(4)
                        xN2 = matchB.group(4)
                        xN1 = matchC.group(4)
                        xregs = [xN3, xN2, xN1]
                        # Check if registers are sorted in their categories
                        reversed_xregs = xregs[::-1]
                        if are_regs_sorted(reversed_xregs):
                            # Format register list for movem
                            xreg_list = '/'.join(f'{r}' for r in xregs)
                            optimized_lines = [
                                f'{matchA.group(1)}movem.{s}{matchA.group(3)}{xreg_list},-({aN})'
                            ]
                            return (optimized_lines, 3)

        if USE_FABRI1983_OPTIMIZATIONS:

            # Calculates offset indexes for accessing arrays.
            # add/sub.l  dM,dN           ->    add/sub.w  dM,dN            ; Saves 4 cycles
            # lea        symbolName1,aN        lea        symbolName1,aN
            # move.[wl]  dP,(aN,dN.[wl])       move.[wl]  dP,(aN,dN.w)
            # Where:
            # symbolName1[.wl][-+*N][.bwl]
            # dM can be dN
            matchA = re.match(r'^(\s*)(add|sub)\.l(\s+)(%d[0-7]),(%d[0-7])', line_A)
            if matchA:
                alu = matchA.group(2)
                dM = matchA.group(4)
                dN = matchA.group(5)
                matchB = re.match(r'^\s*lea\s+([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_B)
                if matchB:
                    symbolName_1_full = ''.join(matchB.group(i) for i in range(1, 5) if matchB.group(i))
                    aN = matchB.group(5)
                    matchC = re.match(r'^\s*move\.([wl])\s+(%d[0-7]),\s*\((%a[0-7]),(%d[0-7])(\.[wl])?\)', line_C)
                    if matchC and aN == matchC.group(3) and dN == matchC.group(4):
                        sC = matchC.group(1)
                        dP = matchC.group(2)
                        optimized_lines = [
                            f'{matchA.group(1)}{alu}.w {matchA.group(3)}{dM},{dN}',
                            f'{matchA.group(1)}lea   {matchA.group(3)}{symbolName_1_full},{aN}',
                            f'{matchA.group(1)}move.{sC}{matchA.group(3)}{dP},({aN},{dN}.w)'
                        ]
                        return (optimized_lines, 3)

            # Calculates offset indexes for accessing arrays.
            # add/sub.l  dM,dN           ->    add/sub.w  dM,dN            ; Saves 4 cycles
            # lea        symbolName1,aN        lea        symbolName1,aN
            # move.[wl]  d(sp),(aN,dN.[wl])    move.[wl]  d(sp),(aN,dN.w)
            # Where:
            # symbolName1[.wl][-+*N][.bwl]
            # dM can be dN
            # Displacement d in d(sp) is optional
            matchA = re.match(r'^(\s*)(add|sub)\.l(\s+)(%d[0-7]),(%d[0-7])', line_A)
            if matchA:
                alu = matchA.group(2)
                dM = matchA.group(4)
                dN = matchA.group(5)
                matchB = re.match(r'^\s*lea\s+([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_B)
                if matchB:
                    symbolName_1_full = ''.join(matchB.group(i) for i in range(1, 5) if matchB.group(i))
                    aN = matchB.group(5)
                    matchC = re.match(r'^\s*move\.([wl])\s+(-?\d+)?\(%sp\),\s*\((%a[0-7]),(%d[0-7])(\.[wl])?\)', line_C)
                    if matchC and aN == matchC.group(3) and dN == matchC.group(4):
                        sC = matchC.group(1)
                        disp = '' if matchC.group(2) is None else matchC.group(2)
                        optimized_lines = [
                            f'{matchA.group(1)}{alu}.w {matchA.group(3)}{dM},{dN}',
                            f'{matchA.group(1)}lea   {matchA.group(3)}{symbolName_1_full},{aN}',
                            f'{matchA.group(1)}move.{sC}{matchA.group(3)}{disp}(%sp),({aN},{dN}.w)'
                        ]
                        return (optimized_lines, 3)

            # Unnecessary redundant use of register aN
            # move.s     dM,aN        ->    add/sub.s   dM,dN         ; Saves [4,8] cycles. Leaves aN as a potential free register
            # add/sub.s  aN,dN              move.s      dN,-(sp)
            # move.s     dN,-(sp)
            # s: w,l
            # Only valid if aN is not used afterwards as source or in any indirection, before it's clear or overwritten.
            # Leaves aN as a potential free register.
            matchA = re.match(r'^(\s*)(move|movea)\.([wl])(\s+)(%d[0-7]),\s*(%a[0-7])', line_A)
            if matchA:
                s = matchA.group(3)
                dM = matchA.group(5)
                aN = matchA.group(6)
                matchB = re.match(r'^\s*(add|sub)\.([wl])\s+(%a[0-7]),(%d[0-7])', line_B)
                if matchB and s == matchB.group(2) and aN == matchB.group(3):
                    alu = matchB.group(1)
                    dN = matchB.group(4)
                    matchC = re.match(r'^\s*move\.([wl])\s+(%d[0-7]),\s*-\(%sp\)', line_C)
                    if matchC and s == matchC.group(1) and dN == matchC.group(2):
                        if not is_reg_used_before_being_overwritten_or_cleared_afterwards(aN, i_line, lines, modified_lines):
                            optimized_lines = [
                                f'{matchA.group(1)}{alu}.{s} {matchA.group(4)}{dM},{dN}',
                                f'{matchA.group(1)}move.{s}{matchA.group(4)}{dN},-(%sp)'
                                
                            ]
                            return (optimized_lines, 3)

            # Unnecessary copy
            # move.l  dN,aN     ->   move.l  dN,aN           ; Saves 4 cycles
            # move.w  aN,dN          instr other than [jb]cc
            # instr other than [jb]cc
            matchA = re.match(r'^(\s*)move\.l(\s+)(%d[0-7]),(%a[0-7])', line_A)
            if matchA:
                dN = matchA.group(3)
                aN = matchA.group(4)
                matchB = re.match(r'^\s*move\.w\s+(%a[0-7]),(%d[0-7])', line_B)
                if matchB and aN == matchB.group(1) and dN == matchB.group(2):
                    matchC = re.match(r'^\s*([jb]w+)(\.[sbw])?\s+([0-9A-Za-z_\.]+)', line_C)
                    if matchC is None or matchC.group(1) not in bcc_or_jcc_instructions:
                        optimized_lines = [
                            f'{matchA.group(1)}move.l{matchA.group(2)}{dN},{aN}',
                            line_C
                        ]
                        return (optimized_lines, 3)

        if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION:

            # Clearing consecutively the stack by just offseting the sp.
            # clr.w  -(sp)     ->    subq    #6,sp         ; Saves 34 cycles.
            # clr.w  -(sp)
            # clr.w  -(sp)
            matchA = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line_A)
            if matchA:
                matchB = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_B)
                if matchB:
                    matchC = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_C)
                    if matchC:
                        optimized_lines = [
                            f'{matchA.group(1)}subq{matchA.group(2)}#6,%sp'
                        ]
                        return (optimized_lines, 3)

            # Clearing consecutively the stack by just offseting the sp.
            # clr.l  -(sp)     ->    lea     -12(sp),sp    ; Saves 58 cycles.
            # clr.l  -(sp)
            # clr.l  -(sp)
            # Also considers:  pea  0.w
            matchA_clr = re.match(r'^(\s*)clr\.l(\s+)-\(%sp\)', line_A)
            matchA_pea = re.match(r'^(\s*)pea(\s+)0.w', line_A)
            matchA = matchA_clr or matchA_pea
            if matchA:
                matchB_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_B)
                matchB_pea = re.match(r'^\s*pea\s+0.w', line_B)
                if matchB_clr or matchB_pea:
                    matchC_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_C)
                    matchC_pea = re.match(r'^\s*pea\s+0.w', line_C)
                    if matchC_clr or matchC_pea:
                        optimized_lines = [
                            f'{matchA.group(1)}lea{matchA.group(2)}-12(%sp),%sp'
                        ]
                        return (optimized_lines, 3)

        else:

            # Clearing consecutively the stack by pushing 0.
            # clr.w  -(sp)     ->    pea     0.w           ; Saves 14 cycles.
            # clr.w  -(sp)           move.w  #0,-(sp)
            # clr.w  -(sp)
            matchA = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line_A)
            if matchA:
                matchB = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_B)
                if matchB:
                    matchC = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_C)
                    if matchC:
                        optimized_lines = [
                            f'{matchA.group(1)}pea   {matchA.group(2)}0.w,{dN}',
                            f'{matchA.group(1)}move.w{matchA.group(2)}#0,-(%sp)'
                        ]
                        return (optimized_lines, 3)

            # Clearing consecutively the stack by pushing 0.
            # clr.l  -(sp)     ->    moveq   #0,dN         ; Saves 22 cycles.
            # clr.l  -(sp)           moveq   #0,dM
            # clr.l  -(sp)           moveq   #0,dP
            #                        movem.l dN/dM/dP,-(sp)
            # Needs 3 free data registers or already holding 0
            # Also considers:  pea  0.w
            matchA_clr = re.match(r'^(\s*)clr\.l(\s+)-\(%sp\)', line_A)
            matchA_pea = re.match(r'^(\s*)pea(\s+)0.w', line_A)
            matchA = matchA_clr or matchA_pea
            if matchA:
                matchB_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_B)
                matchB_pea = re.match(r'^\s*pea\s+0.w', line_B)
                if matchB_clr or matchB_pea:
                    matchC_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_C)
                    matchC_pea = re.match(r'^\s*pea\s+0.w', line_C)
                    if matchC_clr or matchC_pea:
                        free_d_regs = find_free_after_use_data_register([], i_line, lines, modified_lines)
                        if len(free_d_regs) < 3:
                            free_d_regs = find_unused_data_register([], i_line, lines, modified_lines)
                        if len(free_d_regs) >= 3:
                            dN, dM, dP = free_d_regs[:3]
                            if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dN,dM,dP], i_line, lines, modified_lines):
                                optimized_lines = [
                                    f'{matchA.group(1)}moveq  {matchA.group(2)}#0,{dN}',
                                    f'{matchA.group(1)}moveq  {matchA.group(2)}#0,{dM}',
                                    f'{matchA.group(1)}moveq  {matchA.group(2)}#0,{dP}',
                                    f'{matchA.group(1)}movem.l{matchA.group(2)}{dN}/{dM}/{dP},-(%sp)'
                                ]
                                return (optimized_lines, 3)

        # Add more multi-line patterns here for 3 lines

    # Check for patterns whenever we have at least 2 lines
    if multi_limit == 2:

        line_A = modified_lines[-2]
        line_B = modified_lines[-1]

        if OPTIMIZE_INLINE_ASM_BLOCKS:
            # If any line (already right stripped) ends with the flag that mandates to skip it from be optimized -> do nothing and return
            if (line_A.endswith(SKIP_OPTIMIZATION_FLAG) or 
                line_B.endswith(SKIP_OPTIMIZATION_FLAG)):
                return (None, 0)

        # Fast sign-extend bytes into words and words into longs when the sign bit is at an position N.
        # lsl.w/l  #val,dN     ->   move.w/l  #mask,dM     ; Saves ?? cycles as long as N decreases
        # asr.w/l  #val,dN          add.w/l   dM,dN
        #                           eor.w/l   dM,dN
        # Where val=16-N for bytes, val=32-N for words. mask=-(2^(N-1))
        # Needs a free dM
        matchA = re.match(r'^(\s*)lsl\.([wl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
        if matchA:
            matchB = re.match(r'^\s*asr\.([wl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_B)
            if matchB:
                s = matchA.group(2)
                val = parseConstantUnsigned(matchA.group(4))
                dN = matchA.group(5)
                if s == matchB.group(1) and matchA.group(4) == matchB.group(2) and dN == matchB.group(3):
                    n = 16-val
                    if s == 'l':
                        n = 32-val
                    mask = -(2 ** (n - 1))
                    dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
                    if dM is None:
                        dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
                    if dM is not None:
                        if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                            optimized_lines = [
                                f'{matchA.group(1)}move.{s}{matchA.group(3)}#{mask},{dM}',
                                f'{matchA.group(1)}add.{s} {matchA.group(3)}{dM},{dN}',
                                f'{matchA.group(1)}eor.{s} {matchA.group(3)}{dM},{dN}'
                            ]
                            return (optimized_lines, 2)


        # Test bit #7 (8th position) on byte size
        matchA = btst_7_effective_address_pattern.match(line_A)
        if matchA:
            ea = matchA.group(3)

            # btst.b  #7,<ea>    ->    tst.b   <ea>        ; Saves 4 cycles. Status flags wrong
            # beq     label            bpl     label
            # Not valid for dN, d16(PC), d8(PC,Xn.s) dest address modes.
            # <ea>: effective address valid for this tst optimization:
            #   dN   (aN)   (aN)+   -(aN)   d(aN)   d(aN,xN.s)   ABS.w   ABS.l
            # Note that gcc might put the displacement like next: (d,aN)   (d,aN,xN.s)
            # Note that gcc might put a symbol name instead of ABS.w or ABS.l: symbolName or #symbolName
            matchB = re.match(r'^\s*[jb]eq(\.[bsw])?\s+([0-9a-zA-Z_\.]+)', line_B)
            if matchB:
                s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                label = matchB.group(2)
                print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Next optimization won't compile for PC indirection")
                optimized_lines = [
                    f'{matchA.group(1)}tst.b{matchA.group(2)}{ea}',
                    f'{matchA.group(1)}bpl{s_branch}{matchA.group(2)}{label}'
                ]
                return (optimized_lines, 2)

            # btst.b  #7,<ea>    ->    tst.b   <ea>        ; Saves 4 cycles. Status flags wrong
            # bne     label            bmi     label
            # Not valid for dN, d16(PC), d8(PC,Xn.s) dest address modes.
            # <ea>: effective address valid for this tst optimization:
            #   dN   (aN)   (aN)+   -(aN)   d(aN)   d(aN,xN.s)   ABS.w   ABS.l
            # Note that gcc might put the displacement like next: (d,aN)   (d,aN,xN.s)
            # Note that gcc might put a symbol name instead of ABS.w or ABS.l: symbolName or #symbolName
            matchB = re.match(r'^\s*[jb]ne(\.[bsw])?\s+([0-9a-zA-Z_\.]+)', line_B)
            if matchB:
                s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                label = matchB.group(2)
                print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Next optimization won't compile for PC indirection")
                optimized_lines = [
                    f'{matchA.group(1)}tst.b{matchA.group(2)}{ea}',
                    f'{matchA.group(1)}bmi{s_branch}{matchA.group(2)}{label}'
                ]
                return (optimized_lines, 2)

        # Test bit #7,15,31 (8th,16th,31th position) on long size
        matchA = re.match(r'^(\s*)btst\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
        if matchA:
            dN = matchA.group(4)
            val = parseConstantUnsigned(matchA.group(3))
            if val in [7, 15, 31]:
                s_for_tst = 'l'
                if val == 7:
                    s_for_tst = 'b'
                elif val == 15:
                    s_for_tst = 'w'

                # If val in [7, 15, 31]
                # btst.l  #val,dN    ->    tst.s   dN          ; Saves 4 cycles. Status flags wrong
                # beq     label            bpl     label
                # s = b|w|l for 7|15|31
                matchB = re.match(r'^\s*[jb]eq(\.[bsw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                    label = matchB.group(2)
                    optimized_lines = [
                        f'{matchA.group(1)}tst.{s_for_tst}{matchA.group(2)}{dn}',
                        f'{matchA.group(1)}bpl{s_branch}{matchA.group(2)}{label}'
                    ]
                    return (optimized_lines, 2)

                # If val in [7, 15, 31]
                # btst.l  #val,dN    ->    tst.s   dN          ; Saves 4 cycles. Status flags wrong
                # bne     label            bmi     label
                # s = b|w|l for 7|15|31
                matchB = re.match(r'^\s*[jb]ne(\.[bsw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                    label = matchB.group(2)
                    optimized_lines = [
                        f'{matchA.group(1)}tst.{s_for_tst}{matchA.group(2)}{dn}',
                        f'{matchA.group(1)}bmi{s_branch}{matchA.group(2)}{label}'
                    ]
                    return (optimized_lines, 2)

        # Optimizations using TAS instruction are only safe if used on regular RAM and not on memory-mapped I/O 
        # like VDP regs, YM2612 sound chip, Z80 bus, control ports. Hardware registers like (aN) is valid if 
        # pointing to RAM (not memory-mapped I/O).
        if USE_TAS_ON_MAPPED_IO_MEMORY_OPTIMIZATION:

            # bset.b #7,mem
            # gcc might add +-*N[.bwl]. Ie: ammoInventory+2
            matchA = re.match(r'^(\s*)bset\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(#?[a-zA-Z_]\w*|-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?([\+\-\*]\d+)?(\.[bwl])?', line_A)
            if matchA:

                mem_address = ''.join(matchA.group(i) for i in range(4, 8) if matchA.group(i))
                val = parseConstantUnsigned(matchA.group(3))
                if val == 7:

                    # bset.b #7,mem    ->    tas  mem           ; Saves 4 cycles. Status flags wrong
                    # beq    label           bpl  label
                    # mem must be address allowing read-modify-write transfer.
                    # gcc might add +N or -N. Ie: ammoInventory+2
                    matchB = re.match(r'^\s*[jb]eq(\.[sbw])?\s+([0-9A-Za-z_\.]+)', line_B)
                    if matchB:
                        s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                        label = matchB.group(2)
                        optimized_lines = [
                            f'{matchA.group(1)}tas  {matchA.group(2)}{mem_address}',
                            f'{matchA.group(1)}bpl{s_branch}{matchA.group(2)}{label}'
                        ]
                        return (optimized_lines, 2)

                    # bset.b #7,mem    ->    tas  mem           ; Saves 4 cycles. Status flags wrong
                    # bne    label           bmi  label
                    # mem must be address allowing read-modify-write transfer.
                    # gcc might add +-*N. Ie: ammoInventory+2
                    matchB = re.match(r'^\s*[jb]ne(\.[sbw])?\s+([0-9A-Za-z_\.]+)', line_B)
                    if matchB:
                        s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                        label = matchB.group(2)
                        optimized_lines = [
                            f'{matchA.group(1)}tas  {matchA.group(2)}{mem_address}',
                            f'{matchA.group(1)}bmi{s_branch}{matchA.group(2)}{label}'
                        ]
                        return (optimized_lines, 2)

        # bset.l #7,dN
        matchA = re.match(r'^(\s*)bset\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
        if matchA:

            dN = matchA.group(4)
            val = parseConstantUnsigned(matchA.group(3))
            if val == 7:

                # bset.l #7,dN     ->    tas   dN          ; Saves 4 cycles. Status flags wrong
                # beq    label           bpl   label
                matchB = re.match(r'^\s*[jb]eq(\.[sbw])?\s+([0-9A-Za-z_\.]+)', line_B)
                if matchB:
                    s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                    label = matchB.group(2)
                    optimized_lines = [
                        f'{matchA.group(1)}tas  {matchA.group(2)}{dN}',
                        f'{matchA.group(1)}bpl{s_branch}{matchA.group(2)}{label}'
                    ]
                    return (optimized_lines, 2)

                # bset.l #7,dN     ->    tas   dN          ; Saves 4 cycles. Status flags wrong
                # bne    label           bmi   label
                matchB = re.match(r'^\s*[jb]ne(\.[sbw])?\s+([0-9A-Za-z_\.]+)', line_B)
                if matchB:
                    s_branch = '  ' if matchB.group(1) is None else matchB.group(1)
                    label = matchB.group(2)
                    optimized_lines = [
                        f'{matchA.group(1)}tas  {matchA.group(2)}{dN}',
                        f'{matchA.group(1)}bmi{s_branch}{matchA.group(2)}{label}'
                    ]
                    return (optimized_lines, 2)

        # Flags for tst.w:
        # ---------------
        # N: 1 if bit 15 of dN is set, else 0
        # Z: 1 if dN.w = 0
        # V: always 0
        # C: always 0
        #
        # DBcc dN,label -> fall through when the condition is met, otherwise branch to label.
        # So the logic is inverted as from the bcc we want to optimize.
        if USE_TST_BCC_BY_DBCC_OPTIMIZATION:

            matchA = re.match(r'^(\s*)tst\.w(\s+)(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(3)

                # tst.w  dN        ->    dbf    dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # bne    label
                matchB = re.match(r'^\s*[jb]ne(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbf{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

                # tst.w  dN        ->    dbne   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # beq    label
                matchB = re.match(r'^\s*[jb]eq(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbne{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

                # tst.w  dN        ->    dbmi   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # bpl    label
                matchB = re.match(r'^\s*[jb]pl(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbmi{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

                # tst.w  dN        ->    dbpl   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # bmi    label
                matchB = re.match(r'^\s*[jb]mi(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbpl{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

                # tst.w  dN        ->    dbmi   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # bge    label
                matchB = re.match(r'^\s*[jb]ge(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbmi{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

                # tst.w  dN        ->    dbpl   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # blt    label
                matchB = re.match(r'^\s*[jb]lt(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbpl{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

                # tst.w  dN        ->    dbeq   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # bhi    label
                matchB = re.match(r'^\s*[jb]hi(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbeq{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

                # tst.w  dN        ->    dbne   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
                # bls    label
                matchB = re.match(r'^\s*[jb]ls(\.[sbw])?\s+([0-9a-zA-Z_\.]+)', line_B)
                if matchB:
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dN, i_line, lines, modified_lines):
                        return (None, 0)  # NOT_WORKING
                        label = matchB.group(2)
                        optimized_line = f'{matchA.group(1)}dbne{matchA.group(2)}{dN},{label}'
                        return ([optimized_line], 2)

        # Tail recursion for BSR or exploiting PEA opportunities
        matchA = re.match(r'^(\s*)[j]?bsr(\.[bsw])?(\s+)([0-9a-zA-Z_\.]+)(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?;?$', line_A)
        if matchA:
            s_branch = '  ' if matchA.group(2) is None else matchA.group(2)
            subr = ''.join(matchA.group(i) for i in range(4, 8) if matchA.group(i))

            # Tail recursion. Replace BSR+RTS by BRA
            # bsr subr         ->    bra   subr         ; Saves 24 cycles. Different stack depth
            # rts
            matchB = re.match(r'^\s*rts\b', line_B)
            if matchB:
                optimized_line = f'{matchA.group(1)}bra{s_branch}{matchA.group(3)}{subr}'
                return ([optimized_line], 2)

        # Tail recursion for JSR or exploiting PEA opportunities
        matchA = re.match(r'^(\s*)jsr(\s+)([0-9a-zA-Z_\.]+)(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?;?$', line_A)
        if matchA:
            subr = ''.join(matchA.group(i) for i in range(3, 7) if matchA.group(i))

            # Tail recursion. Replace JSR+RTS
            # jsr subr         ->    jmp subr           ; Saves 24 cycles. Different stack depth
            # rts
            matchB = re.match(r'^\s*rts\b', line_B)
            if matchB:
                optimized_line = f'{matchA.group(1)}jmp{matchA.group(2)}{subr}'
                return ([optimized_line], 2)

        # lea     subr,aN    ->   jsr  subr          ; Saves 8 cycles. Leaves aN unused
        # jsr     (aN)
        matchA = re.match(r'^(\s*)lea(\s+)([0-9a-zA-Z_\.]+)(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_A)
        if matchA:
            subr = ''.join(matchA.group(i) for i in range(3, 7) if matchA.group(i))
            aN = matchA.group(7)
            matchB = re.match(r'^\s*jsr\s+\((%a[0-7])\);?$', line_B)
            if matchB and aN == matchB.group(1):
                optimized_lines = [
                    f'{matchA.group(1)}jsr{matchA.group(2)}{subr}'
                ]
                return (None, 0)  # NOT_WORKING: one of the next functions is introducing a bug
                replace_remaining_jsr_aN_calls(aN, i_line, lines, modified_lines, optimized_lines[0])
                if_reg_not_used_anymore_then_remove_from_push_pop(aN, i_line, lines, modified_lines, 2)
                return (optimized_lines, 2)

        # move.l  #subr,aN   ->   jsr  subr          ; Saves 8 cycles. Leaves aN unused
        # jsr     (aN)
        matchA = re.match(r'^(\s*)(move|movea)\.l(\s+)#([0-9a-zA-Z_\.]+)(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7])', line_A)
        if matchA:
            subr = ''.join(matchA.group(i) for i in range(4, 8) if matchA.group(i))
            aN = matchA.group(8)
            matchB = re.match(r'^\s*jsr\s+\((%a[0-7])\);?$', line_B)
            if matchB and aN == matchB.group(1):
                optimized_lines = [
                    f'{matchA.group(1)}jsr{matchA.group(3)}{subr}'
                ]
                return (None, 0)  # NOT_WORKING: one of the next functions is introducing a bug
                replace_remaining_jsr_aN_calls(aN, i_line, lines, modified_lines, optimized_lines[0])
                if_reg_not_used_anymore_then_remove_from_push_pop(aN, i_line, lines, modified_lines, 2)
                return (optimized_lines, 2)

        # move.l  val(aN),aM   ->   jmp  val(aN)     ; Saves 14 cycles. Leaves aM unused
        # jmp     (aM)
        # aN can be pc
        matchA = move_disp_aN_or_pc_into_aM_pattern.match(line_A)
        if matchA:
            aN_or_pc = matchA.group(6)
            aM = matchA.group(7)
            matchB = re.match(r'^\s*jmp\s+\((%a[0-7]|%sp)\);?$', line_B)
            if matchB and aM == matchB.group(1):
                val = ''
                if matchA.group(4):
                    val = matchA.group(4)
                elif matchA.group(5):
                    val = matchA.group(5)[:-1]  # remove ,
                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 2)
                optimized_lines = [
                    f'{matchA.group(1)}jmp{matchA.group(3)}{val}({aN_or_pc})'
                ]
                return (optimized_lines, 2)

        # move.l  val(aN,dN.s),aM   ->   jmp  val(aN,dN.s)    ; Saves 12 cycles. Leaves aM unused
        # jmp     (aM)
        # aN can be pc
        matchA = move_disp_aN_or_pc_dN_into_aM_pattern.match(line_A)
        if matchA:
            aN_or_pc = matchA.group(6)
            dN_s = matchA.group(7)
            aM = matchA.group(8)
            matchB = re.match(r'^\s*jmp\s+\((%a[0-7]|%sp)\);?$', line_B)
            if matchB and aM == matchB.group(1):
                val = ''
                if matchA.group(4):
                    val = matchA.group(4)
                elif matchA.group(5):
                    val = matchA.group(5)[:-1]  # remove ,
                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 2)
                optimized_lines = [
                    f'{matchA.group(1)}jmp{matchA.group(3)}{val}({aN_or_pc},{dN_s})'
                ]
                return (optimized_lines, 2)

        # lea     label_or_val(aN),aM   ->   jmp  label_or_val(aN)    ; Saves 6 cycles. Leaves aM unused
        # jmp     (aM)
        # aN can be pc
        matchA = lea_label_or_disp_aN_or_pc_into_aM_pattern.match(line_A)
        if matchA:
            an_or_pc = matchA.group(5)
            aM = matchA.group(6)
            matchB = re.match(r'^\s*jmp\s+\((%a[0-7]|%sp)\);?$', line_B)
            if matchB and aM == matchB.group(1):
                label_or_val = ''
                if matchA.group(3):
                    label_or_val = matchA.group(3)
                elif matchA.group(4):
                    label_or_val = matchA.group(4)[:-1]  # remove ,
                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 2)
                optimized_lines = [
                    f'{matchA.group(1)}jmp{matchA.group(2)}{label_or_val}({aN_or_pc})'
                ]
                return (optimized_lines, 2)

        # lea     label_or_val(aN,dN.s),aM   ->   jmp  label_or_val(aN,dN.s)    ; Saves 6 cycles. Leaves aM unused
        # jmp     (aM)
        matchA = lea_label_or_disp_aN_or_pc_dN_into_aM_pattern.match(line_A)
        if matchA:
            an_or_pc = matchA.group(5)
            dN_s = matchA.group(6)
            aM = matchA.group(7)
            matchB = re.match(r'^\s*jmp\s+\((%a[0-7]|%sp)\);?$', line_B)
            if matchB and aM == matchB.group(1):
                label_or_val = ''
                if matchA.group(3):
                    label_or_val = matchA.group(3)
                elif matchA.group(4):
                    label_or_val = matchA.group(4)[:-1]  # remove ,
                if_reg_not_used_anymore_then_remove_from_push_pop(aM, i_line, lines, modified_lines, 2)
                optimized_lines = [
                    f'{matchA.group(1)}jmp{matchA.group(2)}{label_or_val}({aN_or_pc},{dN_s})'
                ]
                return (optimized_lines, 2)

        # Apply a mask where -128 ≤ mask ≤ 127
        # move.s   <ea>,dN    ->    moveq   #mask,dN      ; Saves 4 cycles. Top bits of dN different
        # andi.s   #mask,dN         and.s   <ea>,dN
        # <ea>: effective address valid for AND instruction:
        #   dN   (aN)   (aN)+   -(aN)   d(aN)   d(aN,xN.s)   ABS.w   ABS.l   d(PC)   d(PC,xN.s)   imm
        # Where s in xN.s is: b,w,l
        # Note that gcc might put the displacement like next: (d,aN)   (d,aN,xN.s)   (d,PC)   (d,PC,xN.s)
        # Note that gcc might put a symbol name instead of ABS.w or ABS.l: symbolName
        matchA = move_ea_into_dN_pattern.match(line_A)
        if matchA:
            s = matchA.group(2)
            dN = matchA.group(12)
            matchB = re.match(r'^\s*(andi|and)\.([bwl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_B)
            if matchB and dN == matchB.group(4):
                ea = matchA.group(4) or matchA.group(5) or matchA.group(6) or matchA.group(7) or matchA.group(8) or matchA.group(9) or matchA.group(10) or matchA.group(11)
                mask = parseConstantSigned(matchB.group(3), 8)
                if -128 <= mask <= 127 and not ea.startswith(('%a','%sp')):
                    # if ea is #symbolName then remove the '#'
                    #if re.match(r'^#[0-9a-zA-Z_\.]+', ea):
                    #    ea = ea[1:]
                    optimized_lines = [
                        f'{matchA.group(1)}moveq{matchA.group(3)}#{mask},{dN}',
                        f'{matchA.group(1)}and.{s}{matchA.group(3)}{ea},{dN}'
                    ]
                    return (optimized_lines, 2)

        # move.l  aN,sp      ->    unlk    aN
        # move.l  (sp)+,aN
        matchA = re.match(r'^(\s*)(move|movea)\.l(\s+)(%a[0-7]),\s*%sp', line_A)
        if matchA:
            aN = matchA.group(4)
            matchB = re.match(r'^\s*(move|movea)\.l\s+\(%sp\)\+,\s*(%a[0-7])', line_A)
            if matchB and aN == matchB.group(2):
                optimized_lines = [
                    f'{matchA.group(1)}unlk{matchA.group(3)}{aN}'
                ]
                return (optimized_lines, 2)

        # Push aN into sp and then add/sub constant into sp
        matchA = re.match(r'^(\s*)move\.([wl])(\s+)(%a[0-7]),\s*-\(%sp\)', line_A)
        if matchA:
            sA = matchA.group(2)
            aN = matchA.group(4)

            # move.[wl]  aN,-(sp)   ->    pea   val(aN)
            # add*.[wl]  #val,(sp)            
            matchB = re.match(r'^\s*(add|adda|addq|addi)\.([wl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*\(%sp\)', line_B)
            if matchB and sA == matchB.group(2):
                val = parseConstantSigned(matchB.group(3), 16)
                optimized_lines = [
                    f'{matchA.group(1)}pea{matchA.group(3)}{val}({aN})'
                ]
                return (optimized_lines, 2)

            # move.[wl]  aN,-(sp)   ->    pea   -val(aN)
            # sub*.[wl]  #val,(sp)            
            matchB = re.match(r'^\s*(sub|suba|subq|subi)\.([wl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*\(%sp\)', line_B)
            if matchB and sA == matchB.group(2):
                val = parseConstantSigned(matchB.group(3), 16)
                optimized_lines = [
                    f'{matchA.group(1)}pea{matchA.group(3)}{-val}({aN})'
                ]
                return (optimized_lines, 2)

        if USE_FABRI1983_OPTIMIZATIONS:

            # Increment by 1 byte after reading 1 byte from memory
            # move.b   (aN),xN      ->    move.b   (aN)+,xN        ; Saves 8 cycles
            # add*     #1,aN
            # Here aN can't be sp because it doesn't support increment by 1 byte.
            matchA = re.match(r'^(\s*)(move|movea)\.w(\s+)\((%a[0-7])\),\s*(%[ad][0-7])', line_A)
            if matchA:
                aN = matchA.group(4)
                xN = matchA.group(5)
                matchB = re.match(r'^\s*(add|adda|addq)\.([bwl])\s+#1,\s*(%a[0-7])', line_B)
                if matchB and aN == matchB.group(3):
                    optimized_lines = [
                        f'{matchA.group(1)}move.b{matchA.group(3)}({aN})+,{xN}'
                    ]
                    return (optimized_lines, 2)

            # Decrement by 1 byte before reading 1 byte from memory
            # sub*     #1,aN        ->    move.b   -(aN),xN        ; Saves 6 cycles
            # move.b   (aN),xN
            # Here aN can't be sp because it doesn't support increment by 1 byte.
            matchA = re.match(r'^(\s*)(sub|suba|subq)\.([bwl])(\s+)#1,\s*(%a[0-7])', line_A)
            if matchA:
                aN = matchA.group(5)
                matchB = re.match(r'^\s*(move|movea)\.w\s+\((%a[0-7])\),\s*(%[ad][0-7])', line_B)
                if matchB and aN == matchB.group(2):
                    xN = matchB.group(3)
                    optimized_lines = [
                        f'{matchA.group(1)}move.b{matchA.group(4)}-({aN}),{xN}'
                    ]
                    return (optimized_lines, 2)

            # Increment by 2 bytes after reading 1 word from memory
            # move.w   (aN),xN      ->    move.w   (aN)+,xN        ; Saves 8 cycles
            # add*     #2,aN
            matchA = re.match(r'^(\s*)(move|movea)\.w(\s+)\((%a[0-7]|%sp)\),\s*(%[ad][0-7])', line_A)
            if matchA:
                aN = matchA.group(4)
                xN = matchA.group(5)
                matchB = re.match(r'^\s*(add|adda|addq)\.([bwl])\s+#2,\s*(%a[0-7]|%sp)', line_B)
                if matchB and aN == matchB.group(3):
                    optimized_lines = [
                        f'{matchA.group(1)}move.w{matchA.group(3)}({aN})+,{xN}'
                    ]
                    return (optimized_lines, 2)

            # Decrement by 2 bytes before reading 1 word from memory
            # sub*     #2,aN        ->    move.w   -(aN),xN        ; Saves 6 cycles
            # move.w   (aN),xN
            matchA = re.match(r'^(\s*)(sub|suba|subq)\.([bwl])(\s+)#2,\s*(%a[0-7]|%sp)', line_A)
            if matchA:
                aN = matchA.group(5)
                matchB = re.match(r'^\s*(move|movea)\.w\s+\((%a[0-7]|%sp)\),\s*(%[ad][0-7])', line_B)
                if matchB and aN == matchB.group(2):
                    xN = matchB.group(3)
                    optimized_lines = [
                        f'{matchA.group(1)}move.w{matchA.group(4)}-({aN}),{xN}'
                    ]
                    return (optimized_lines, 2)

            # Increment by 4 bytes after reading 1 long from memory
            # move.l   (aN),xN      ->    move.l   (aN)+,xN        ; Saves 8 cycles
            # add*     #4,aN
            matchA = re.match(r'^(\s*)(move|movea)\.l(\s+)\((%a[0-7]|%sp)\),\s*(%[ad][0-7])', line_A)
            if matchA:
                aN = matchA.group(4)
                xN = matchA.group(5)
                matchB = re.match(r'^\s*(add|adda|addq)\.([bwl])\s+#4,\s*(%a[0-7]|%sp)', line_B)
                if matchB and aN == matchB.group(3):
                    optimized_lines = [
                        f'{matchA.group(1)}move.l{matchA.group(3)}({aN})+,{xN}'
                    ]
                    return (optimized_lines, 2)

            # Decrement by 4 bytes before reading 1 long from memory
            # sub*     #4,aN        ->    move.l   -(aN),xN        ; Saves 6 cycles
            # move.l   (aN),xN
            matchA = re.match(r'^(\s*)(add|adda|addq)\.([bwl])(\s+)#4,\s*(%a[0-7]|%sp)', line_A)
            if matchA:
                aN = matchA.group(5)
                matchB = re.match(r'^\s*(move|movea)\.l\s+\((%a[0-7]|%sp)\),\s*(%[ad][0-7])', line_B)
                if matchB and aN == matchB.group(2):
                    xN = matchB.group(3)
                    optimized_lines = [
                        f'{matchA.group(1)}move.l{matchA.group(4)}-({aN}),{xN}'
                    ]
                    return (optimized_lines, 2)

            # Unnecessary redundant use of register dM
            # add.s  dN,dM     ->   add.s  dN,dP           ; Saves 4 cycles. Leaves dM as a potential free register
            # move.s dM,dP
            # s: b,w,l
            # Only valid if dM is not used afterwards as source or in any indirection, before it's clear or overwritten.
            # Leaves dM as a potential free register.
            matchA = re.match(r'^(\s*)add\.([bwl])(\s+)(%d[0-7]),\s*(%d[0-7])', line_A)
            if matchA:
                s = matchA.group(2)
                dN = matchA.group(4)
                dM = matchA.group(5)
                matchB = re.match(r'^\s*move\.([bwl])\s+(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and s == matchB.group(1) and dM == matchB.group(2):
                    dP = matchB.group(3)
                    if not is_reg_used_before_being_overwritten_or_cleared_afterwards(dM, i_line, lines, modified_lines):
                        optimized_lines = [
                            f'{matchA.group(1)}add.{s}{matchA.group(3)}{dN},{dP}'
                        ]
                        return (optimized_lines, 2)

            # Calculates offset indexes for accessing arrays.
            # lea     symbolName1,aN    ->   move.l  *,aN                 ; Saves [6,8] cycles
            # add.l   *,aN                   lea     symbolName1(aN),aN
            matchA = re.match(r'^(\s*)lea(\s+)([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?,\s*(%a[0-7]|%sp)', line_A)
            if matchA:
                symbolName_1_full = ''.join(matchA.group(i) for i in range(3, 7) if matchA.group(i))
                aN = matchA.group(7)
                matchB = re.match(r'^\s*(add|adda)\.l\s+([^,]+),\s*(%a[0-7]|%sp);?$', line_B)
                if matchB and aN == matchB.group(3):
                    src_B = matchB.group(2)
                    optimized_lines = [
                        f'{matchA.group(1)}move.l{matchA.group(2)}{src_B},{aN}',
                        f'{matchA.group(1)}lea   {matchA.group(2)}{symbolName_1_full}({aN}),{aN}'
                    ]
                    return (optimized_lines, 2)

            # Load a memory value with an offset into a data register
            # lea     symbolName1,aN       ->   lea     symbolName1,aN       ; Saves 4 cycles
            # move.s  symbolName1+/-N,dN        move.s  N(aN),dN
            matchA = re.match(r'^(\s*)lea(\s+)([0-9a-zA-Z_\.]+)(\.[wl])?,\s*(%a[0-7]|%sp)', line_A)
            if matchA:
                symbolName_1_full = ''.join(matchA.group(i) for i in range(3, 5) if matchA.group(i))
                aN = matchA.group(5)
                matchB = re.match(r'^\s*move\.([bwl])\s+([0-9a-zA-Z_\.]+)(\.[wl])?([\-\+]\d+)(\.[bwl])?,\s*(%d[0-7])', line_B)
                if matchB:
                    symbolName_1_full_B = ''.join(matchB.group(i) for i in range(2, 4) if matchB.group(i))
                    if symbolName_1_full == symbolName_1_full_B:
                        s = matchB.group(1)
                        op_N = matchB.group(4)
                        if op_N.startswith('+'):
                            op_N = op_N[1:]
                        dN = matchB.group(6)
                        optimized_lines = [
                            f'{matchA.group(1)}lea   {matchA.group(2)}{symbolName_1_full},{aN}',
                            f'{matchA.group(1)}move.{s}{matchA.group(2)}{op_N}({aN}),{dN}'
                        ]
                        return (optimized_lines, 2)

            # This pattern comes up after applying optimization for lsl.w #8,dN
            # clr.b   dN            ->   move.b  dM,dN             ; Saves 4 cycles
            # move.b  dM,dN
            matchA = re.match(r'^(\s*)clr\.b(\s+)(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(3)
                matchB = re.match(r'^\s*move\.b\s+(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(2):
                    dM = matchB.group(1)
                    optimized_lines = [
                        f'{matchA.group(1)}move.b{matchA.group(2)}{dM},{dN}'
                    ]
                    return (optimized_lines, 2)

        # Move xN into dM and then add/sub a constant into dM
        # If -128 <= val <= 127
        # move.[wl]       xN,dM      ->    moveq         #val,dM        ; Saves 8 cycles
        # add*/sub*.[wl]  #val,dM          add/sub.[wl]  xN,dM
        matchA = re.match(r'^(\s*)move\.([wl])(\s+)(%[ad][0-7]|%sp),\s*(%d[0-7])', line_A)
        if matchA:
            sA = matchA.group(2)
            xN = matchA.group(4)
            dM = matchA.group(5)
            matchB = re.match(r'^\s*(add|addq|addi|sub|subq|subi)\.([wl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_B)
            if matchB and dM == matchB.group(4):
                val = parseConstantSigned(matchB.group(3), 8)
                if -128 <= val <= 127:
                    alu = matchB.group(1)[:3]  # First 3 chars is 'add' or 'sub'
                    if alu == 'sub':
                        val = -val
                    optimized_lines = [
                        f'{matchA.group(1)}moveq{matchA.group(3)}#{val},{dM}',
                        f'{matchA.group(1)}add.{sA}{matchA.group(3)}{xN},{dM}'
                    ]
                    return (optimized_lines, 2)

        # Calculating effective address between address registers and a constant
        matchA = re.match(r'^(\s*)(move|movea)\.([bwl])(\s+)(%a[0-7]),\s*(%a[0-7])', line_A)
        if matchA:
            s = matchA.group(3)
            aN = matchA.group(5)
            aM = matchA.group(6)

            # If -32767 <= val <= 32767
            # move.s  aN,aM      ->    lea   val(aN),aM
            # add.s   #val,aM
            # s: b,w,l
            matchB = re.match(r'^\s*(add|adda|addq)\.([bwl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_B)
            if matchB and s == matchB.group(2) and aM == matchB.group(4):
                val = parseConstantSigned(matchB.group(3), 32)
                if s == 'b':
                    val = parseConstantSigned(matchB.group(3), 8)
                elif s == 'w':
                    val = parseConstantSigned(matchB.group(3), 16)
                if -32767 <= val <= 32767:
                    optimized_lines = [
                        f'{matchA.group(1)}lea{matchA.group(4)}{val}({aN}),{aM}'
                    ]
                    return (optimized_lines, 2)

            # If -32768 <= val <= 32767
            # move.s  aN,aM      ->    lea   -val(aN),aM
            # sub.s   #val,aM
            # s: b,w,l
            matchB = re.match(r'^\s*(sub|suba|subq)\.([bwl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_B)
            if matchB and s == matchB.group(2) and aM == matchB.group(4):
                val = parseConstantSigned(matchB.group(3), 32)
                if s == 'b':
                    val = parseConstantSigned(matchB.group(3), 8)
                elif s == 'w':
                    val = parseConstantSigned(matchB.group(3), 16)
                if -32768 <= val <= 32767:
                    optimized_lines = [
                        f'{matchA.group(1)}lea{matchA.group(4)}{-val}({aN}),{aM}'
                    ]
                    return (optimized_lines, 2)

        # Reduce addition and move into memory with only one move instruction.
        # add.[wl]   xN,aN     ->    move.[wl] (aN,xN.w),aM     ; Saves 2 cycles
        # move.[wl]  (aN),aM
        # aM can be aN
        matchA = re.match(r'^(\s*)(add|adda)\.([wl])(\s+)(%[ad][0-7]|%sp),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            xN = matchA.group(5)
            aN = matchA.group(6)
            matchB = re.match(r'^\s*(move|movea)\.([wl])\s+\((%a[0-7]|%sp)\),\s*(%a[0-7]|%sp)', line_B)
            if matchB and aN == matchB.group(3):
                sB = matchB.group(2)
                aM = matchB.group(4)
                optimized_lines = [
                    f'{matchA.group(1)}move.{sB}{matchA.group(4)}({aN},{xN}.w),{aM}'
                ]
                return (optimized_lines, 2)

        # Calculating effective address involving a value and registers xN and aN.
        # If -32768 <= val <= 32767
        # move.[wl]  #val,aN   ->    move.[wl]  xN,aN        ; Saves 4 cycles
        # add.[wl]   xN,aN           lea        val(aN),aN
        matchA = re.match(r'^(\s*)(move|movea)\.([wl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            val = parseConstantSigned(matchA.group(5), 16)
            aN = matchA.group(6)
            matchB = re.match(r'^\s*(add|adda)\.([wl])\s+(%[ad][0-7]|%sp),\s*(%a[0-7]|%sp)', line_B)
            if matchB and aN == matchB.group(4):
                if -32768 <= val <= 32767:
                    sB = matchB.group(2)
                    xN = matchB.group(3)
                    optimized_lines = [
                        f'{matchA.group(1)}move.{sB}{matchA.group(4)}{xN},{aN}',
                        f'{matchA.group(1)}lea   {matchA.group(4)}{val}({aN}),{aN}'
                    ]
                    return (optimized_lines, 2)

        # Calculating effective address involving a value and registers xN and aN.
        # If -128 <= val <= 127
        # add.[wl]  #val,aN    ->    lea  val(aN,xN.s),aN    ; Saves 8 cycles
        # add.s     xN,aN
        # s: b,w,l
        matchA = re.match(r'^(\s*)(add|adda|addq)\.([wl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            val = parseConstantSigned(matchA.group(5), 8)
            aN = matchA.group(6)
            matchB = re.match(r'^\s*(add|adda)\.([bwl])\s+(%[ad][0-7]|%sp),\s*(%a[0-7]|%sp)', line_B)
            if matchB and aN == matchB.group(4):
                sB = matchB.group(2)
                xN = matchB.group(3)
                # If xN == aN means the original instructions are a multiplication by 2, so modify accordingly
                if xN == aN:
                    val *= 2
                if -128 <= val <= 127:
                    optimized_lines = [
                        f'{matchA.group(1)}lea{matchA.group(4)}{val}({aN},{xN}.{sB}),{aN}'
                    ]
                    return (optimized_lines, 2)

        # Calculating effective address involving a value and registers xN and aN.
        # If -128 <= val <= 127
        # add.s     xN,aN      ->    lea  val(aN,xN.s),aN    ; Saves 8 cycles
        # add.[wl]  #val,aN
        # s: b,w,l
        matchA = re.match(r'^(\s)*(add|adda)\.([bwl])(\s+)(%[ad][0-7]|%sp),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            sA = matchA.group(3)
            xN = matchA.group(5)
            aN = matchA.group(6)
            matchB = re.match(r'^\s*(add|adda|addq)\.([wl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_B)
            if matchB and aN == matchB.group(4):
                val = parseConstantSigned(matchB.group(3), 8)
                # If xN == aN means the original instructions are a multiplication by 2, so modify accordingly
                if xN == aN:
                    val *= 2
                if -128 <= val <= 127:
                    optimized_lines = [
                        f'{matchA.group(1)}lea{matchA.group(4)}{val}({aN},{xN}.{sA}),{aN}'
                    ]
                    return (optimized_lines, 2)

        # Calculating effective address involving a value and registers xN and aN.
        # If -127 <= val <= 128
        # sub.[wl]  #val,aN    ->    lea  -val(aN,xN.s),aN   ; Saves 8 cycles
        # add.s     xN,aN
        # s: b,w,l
        matchA = re.match(r'^(\s*)(sub|suba|subq)\.([wl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            val = parseConstantSigned(matchA.group(5), 8)
            aN = matchA.group(6)
            matchB = re.match(r'^\s*(add|adda|addq)\.([bwl])\s+(%[ad][0-7]|%sp),\s*(%a[0-7]|%sp)', line_B)
            if matchB and aN == matchB.group(4):
                sB = matchB.group(2)
                xN = matchB.group(3)
                # If xN == aN means the original instructions are a multiplication by 2, so modify accordingly
                if xN == aN:
                    val *= 2
                if -127 <= val <= 128:
                    optimized_lines = [
                        f'{matchA.group(1)}lea{matchA.group(4)}-{val}({aN},{xN}.{sB}),{aN}'
                    ]
                    return (optimized_lines, 2)

        # Calculating effective address involving a value and registers xN and aN.
        # If -128 <= val <= 127
        # add.s     xN,aN      ->    lea  -val(aN,xN.s),aN   ; Saves 8 cycles
        # sub.[wl]  #val,aN
        # s: b,w,l
        matchA = re.match(r'^(\s)*(add|adda)\.([bwl])(\s+)(%[ad][0-7]|%sp),\s*(%a[0-7]|%sp)', line_A)
        if matchA:
            sA = matchA.group(3)
            xN = matchA.group(5)
            aN = matchA.group(6)
            matchB = re.match(r'^\s*(sub|suba|subq)\.([wl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line_B)
            if matchB and aN == matchB.group(4):
                val = parseConstantSigned(matchB.group(3), 8)
                # If xN == aN means the original instructions are a multiplication by 2, so modify accordingly
                if xN == aN:
                    val *= 2
                if -128 <= val <= 127:
                    optimized_lines = [
                        f'{matchA.group(1)}lea{matchA.group(4)}-{val}({aN},{xN}.{sA}),{aN}'
                    ]
                    return (optimized_lines, 2)

        # Addition using indexing modes
        # add.s   (aN,dP.z),xN  ->  add.z   dP,aN          ; Saves [2,4] cycles. Leaves aN with different value than expected
        # add.s   (aN,dP.z),xM      add.s   (aN),xN
        #                           add.s   (aN),xM
        matchA = re.match(r'^(\s*)(add|adda)\.([bwl])(\s+)\((%a[0-7]),(%d[0-7])(\.[bwl])?\),\s*(%[ad][0-7])', line_A)
        if matchA:
            s = matchA.group(3)
            aN = matchA.group(5)
            dP = matchA.group(6)
            xN = matchA.group(8)
            z = '' if matchA.group(7) is None else matchA.group(7)[1:]  # removes the .
            matchB = re.match(r'^\s*(add|adda)\.([bwl])\s+\((%a[0-7]),(%d[0-7])(\.[bwl])?\),\s*(%[ad][0-7])', line_B)
            if matchB and s == matchB.group(2) and aN == matchB.group(3) and dP == matchB.group(4):
                if not is_reg_used_before_being_overwritten_or_cleared_afterwards(aN, i_line, lines, modified_lines):
                    xM = matchB.group(6)
                    optimized_lines = [
                        f'{matchA.group(1)}add.{z}{matchA.group(4)}{dP},{aN}',
                        f'{matchA.group(1)}add.{s}{matchA.group(4)}({aN}),{xN}',
                        f'{matchA.group(1)}add.{s}{matchA.group(4)}({aN}),{xM}'
                    ]
                    return (optimized_lines, 2)

        # Substraction using indexing modes
        # sub.s   (aN,dP.z),xN  ->  sub.z   dP,aN          ; Saves [2,4] cycles. Leaves aN with different value than expected
        # sub.s   (aN,dP.z),xM      sub.s   (aN),xN
        #                           sub.s   (aN),xM
        matchA = re.match(r'^(\s*)(sub|suba)\.([bwl])(\s+)\((%a[0-7]),(%d[0-7])(\.[bwl])?\),\s*(%[ad][0-7])', line_A)
        if matchA:
            s = matchA.group(3)
            aN = matchA.group(5)
            dP = matchA.group(6)
            xN = matchA.group(8)
            z = '' if matchA.group(7) is None else matchA.group(7)[1:]  # removes the .
            matchB = re.match(r'^\s*(sub|suba)\.([bwl])\s+\((%a[0-7]),(%d[0-7])(\.[bwl])?\),\s*(%[ad][0-7])', line_B)
            if matchB and s == matchB.group(2) and aN == matchB.group(3) and dP == matchB.group(4):
                if not is_reg_used_before_being_overwritten_or_cleared_afterwards(aN, i_line, lines, modified_lines):
                    xM = matchB.group(6)
                    optimized_lines = [
                        f'{matchA.group(1)}sub.{z}{matchA.group(4)}{dP},{aN}',
                        f'{matchA.group(1)}sub.{s}{matchA.group(4)}({aN}),{xN}',
                        f'{matchA.group(1)}sub.{s}{matchA.group(4)}({aN}),{xM}'
                    ]
                    return (optimized_lines, 2)

        # Addition using indexing modes
        # add.s   d(aN),dN   ->   move.s  d(aN),dP      ; Saves 4 cycles
        # add.s   d(aN),dM        add.s   dP,dN
        #                         add.s   dP,dM
        # Needs a free register dP
        # Note that gcc might put the displacement like next: (d,aN)
        add_disp_aN_into_dN_pattern = r'^(\s*)add\.([bwl])(\s+)(?:(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7])\)|\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?,(%a[0-7])\)),\s*(%d[0-7])'
        matchA = re.match(add_disp_aN_into_dN_pattern, line_A)
        if matchA:
            s = matchA.group(2)
            dN = matchA.group(8)
            aN = matchA.group(5) or matchA.group(7)
            matchB = re.match(add_disp_aN_into_dN_pattern, line_B)
            if matchB and s == matchB.group(2) and aN == (matchB.group(5) or matchB.group(7)):
                # Try first matching group: d(aN)
                dispA = 0 if matchA.group(4) is None else parseConstantSigned(matchA.group(4), 16)
                if dispA == 0:
                    # Try second matching group: (d,aN)
                    dispA = 0 if matchA.group(6) is None else parseConstantSigned(matchA.group(6), 16)
                # Try first matching group: d(aN)
                dispB = 0 if matchB.group(4) is None else parseConstantSigned(matchB.group(4), 16)
                if dispB == 0:
                    # Try second matching group: (d,aN)
                    dispB = 0 if matchB.group(6) is None else parseConstantSigned(matchB.group(6), 16)
                # Must have same displacement
                if dispA == dispB:
                    disp_str = '' if dispA == 0 else f'{dispA}'
                    dM = matchB.group(8)
                    dP = find_free_after_use_data_register([dN,dM], i_line, lines, modified_lines)[0]
                    if dP is None:
                        dP = find_unused_data_register([dN,dM], i_line, lines, modified_lines)[0]
                    if dP is not None:
                        if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dP], i_line, lines, modified_lines):
                            optimized_lines = [
                                f'{matchA.group(1)}move.{s}{matchA.group(3)}{disp_str}({aN}),{dP}',
                                f'{matchA.group(1)}add.{s} {matchA.group(3)}({dP}),{dN}',
                                f'{matchA.group(1)}add.{s} {matchA.group(3)}({dP}),{dM}'
                            ]
                            return (optimized_lines, 2)

        # Substraction using indexing modes
        # sub.s   d(aN),dN   ->   move.s  d(aN),dP      ; Saves 4 cycles
        # sub.s   d(aN),dM        sub.s   dP,dN
        #                         sub.s   dP,dM
        # Needs a free register dP
        # Note that gcc might put the displacement like next: (d,aN)
        sub_disp_aN_into_dN_pattern = r'^(\s*)sub\.([bwl])(\s+)(?:(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7])\)|\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?,(%a[0-7])\)),\s*(%d[0-7])'
        matchA = re.match(sub_disp_aN_into_dN_pattern, line_A)
        if matchA:
            s = matchA.group(2)
            dN = matchA.group(8)
            aN = matchA.group(5) or matchA.group(7)
            matchB = re.match(sub_disp_aN_into_dN_pattern, line_B)
            if matchB and s == matchB.group(2) and aN == (matchB.group(5) or matchB.group(7)):
                # Try first matching group: d(aN)
                dispA = 0 if matchA.group(4) is None else parseConstantSigned(matchA.group(4), 16)
                if dispA == 0:
                    # Try second matching group: (d,aN)
                    dispA = 0 if matchA.group(6) is None else parseConstantSigned(matchA.group(6), 16)
                # Try first matching group: d(aN)
                dispB = 0 if matchB.group(4) is None else parseConstantSigned(matchB.group(4), 16)
                if dispB == 0:
                    # Try second matching group: (d,aN)
                    dispB = 0 if matchB.group(6) is None else parseConstantSigned(matchB.group(6), 16)
                # Must have same displacement
                if dispA == dispB:
                    disp_str = '' if dispA == 0 else f'{dispA}'
                    dM = matchB.group(8)
                    dP = find_free_after_use_data_register([dN,dM], i_line, lines, modified_lines)[0]
                    if dP is None:
                        dP = find_unused_data_register([dN,dM], i_line, lines, modified_lines)[0]
                    if dP is not None:
                        if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dP], i_line, lines, modified_lines):
                            optimized_lines = [
                                f'{matchA.group(1)}move.{s}{matchA.group(3)}{disp_str}({aN}),{dP}',
                                f'{matchA.group(1)}sub.{s} {matchA.group(3)}({dP}),{dN}',
                                f'{matchA.group(1)}sub.{s} {matchA.group(3)}({dP}),{dM}'
                            ]
                            return (optimized_lines, 2)

        # Addition using indexing modes
        # add.s   d(aN),aM   ->   move.s  d(aN),aQ      ; Saves 4 cycles
        # add.s   d(aN),aP        add.s   aQ,aM
        #                         add.s   aQ,aP
        # Needs a free register aQ
        # Note that gcc might put the displacement like next: (d,aN)
        add_disp_aN_into_aM_pattern = r'^(\s*)(add|adda)\.([bwl])(\s+)(?:(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7])\)|\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?,(%a[0-7])\)),\s*(%d[0-7])'
        matchA = re.match(add_disp_aN_into_aM_pattern, line_A)
        if matchA:
            s = matchA.group(3)
            aN = matchA.group(6) or matchA.group(8)
            aM = matchA.group(9)
            matchB = re.match(add_disp_aN_into_aM_pattern, line_B)
            if matchB and s == matchB.group(3) and aN == (matchB.group(6) or matchB.group(8)):
                # Try first matching group: d(aN)
                dispA = 0 if matchA.group(5) is None else parseConstantSigned(matchA.group(5), 16)
                if dispA == 0:
                    # Try second matching group: (d,aN)
                    dispA = 0 if matchA.group(7) is None else parseConstantSigned(matchA.group(7), 16)
                # Try first matching group: d(aN)
                dispB = 0 if matchB.group(5) is None else parseConstantSigned(matchB.group(5), 16)
                if dispB == 0:
                    # Try second matching group: (d,aN)
                    dispB = 0 if matchB.group(7) is None else parseConstantSigned(matchB.group(7), 16)
                # Must have same displacement
                if dispA == dispB:
                    disp_str = '' if dispA == 0 else f'{dispA}'
                    aP = matchB.group(9)
                    aQ = find_free_after_use_addres_register([aM,aP], i_line, lines, modified_lines)[0]
                    if aQ is None:
                        aQ = find_unused_address_register([aM,aP], i_line, lines, modified_lines)[0]
                    if aQ is not None:
                        if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([aQ], i_line, lines, modified_lines):
                            optimized_lines = [
                                f'{matchA.group(1)}move.{s}{matchA.group(4)}{disp_str}({aN}),{aQ}',
                                f'{matchA.group(1)}add.{s} {matchA.group(4)}({aQ}),{aM}',
                                f'{matchA.group(1)}add.{s} {matchA.group(4)}({aQ}),{aP}'
                            ]
                            return (optimized_lines, 2)

        # Addition using indexing modes
        # sub.s   d(aN),aM   ->   move.s  d(aN),aQ      ; Saves 4 cycles
        # sub.s   d(aN),aP        sub.s   aQ,aM
        #                         sub.s   aQ,aP
        # Needs a free register aQ
        # Note that gcc might put the displacement like next: (d,aN)
        sub_disp_aN_into_aM_pattern = r'^(\s*)(sub|suba)\.([bwl])(\s+)(?:(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7])\)|\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?,(%a[0-7])\)),\s*(%d[0-7])'
        matchA = re.match(sub_disp_aN_into_aM_pattern, line_A)
        if matchA:
            s = matchA.group(3)
            aN = matchA.group(6) or matchA.group(8)
            aM = matchA.group(9)
            matchB = re.match(sub_disp_aN_into_aM_pattern, line_B)
            if matchB and s == matchB.group(3) and aN == (matchB.group(6) or matchB.group(8)):
                # Try first matching group: d(aN)
                dispA = 0 if matchA.group(5) is None else parseConstantSigned(matchA.group(5), 16)
                if dispA == 0:
                    # Try second matching group: (d,aN)
                    dispA = 0 if matchA.group(7) is None else parseConstantSigned(matchA.group(7), 16)
                # Try first matching group: d(aN)
                dispB = 0 if matchB.group(5) is None else parseConstantSigned(matchB.group(5), 16)
                if dispB == 0:
                    # Try second matching group: (d,aN)
                    dispB = 0 if matchB.group(7) is None else parseConstantSigned(matchB.group(7), 16)
                # Must have same displacement
                if dispA == dispB:
                    disp_str = '' if dispA == 0 else f'{dispA}'
                    aP = matchB.group(9)
                    aQ = find_free_after_use_addres_register([aM,aP], i_line, lines, modified_lines)[0]
                    if aQ is None:
                        aQ = find_unused_address_register([aM,aP], i_line, lines, modified_lines)[0]
                    if aQ is not None:
                        if add_regs_into_push_pop_if_not_scratch_or_in_interrupt([aQ], i_line, lines, modified_lines):
                            optimized_lines = [
                                f'{matchA.group(1)}move.{s}{matchA.group(4)}{disp_str}({aN}),{aQ}',
                                f'{matchA.group(1)}sub.{s} {matchA.group(4)}({aQ}),{aM}',
                                f'{matchA.group(1)}sub.{s} {matchA.group(4)}({aQ}),{aP}'
                            ]
                            return (optimized_lines, 2)

        # Push word constants into stack
        # move.w   #x,-(sp)   ->    move.l  #xy,-(sp)      ; Saves 4 cycles
        # move.w   #y,-(sp)
        # xy = (x << 16) | (y & 0xffff)
        push_constant_into_stack_pattern = r'^(\s*)move\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*-\(%sp\)'
        matchA = re.match(push_constant_into_stack_pattern, line_A)
        if matchA:
            matchB = re.match(push_constant_into_stack_pattern, line_B)
            if matchB:
                x = parseConstantUnsigned(matchA.group(3))
                y = parseConstantUnsigned(matchB.group(3))
                xy = ((x << 16) | (y & 0xffff)) & 0xffffffff
                optimized_lines = [
                    f'{matchA.group(1)}move.l{matchA.group(2)}#{xy},-(%sp)'
                ]
                return (optimized_lines, 2)

        # Move byte constants into consecutive memory
        # If mem1+1 == mem2
        # move.b   #x,mem1    ->    move.w  #xy,mem1       ; Saves 20 cycles
        # move.b   #y,mem2
        # xy = (x << 8) | (y & 0xff)
        move_constant_byte_to_mem_pattern = r'^(\s*)move\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+);?$'
        matchA = re.match(move_constant_byte_to_mem_pattern, line_A)
        if matchA:
            matchB = re.match(move_constant_byte_to_mem_pattern, line_B)
            if matchB:
                x = parseConstantUnsigned(matchA.group(3))
                y = parseConstantUnsigned(matchB.group(3))
                mem1 = parseConstantSigned(matchA.group(4), 32)
                mem2 = parseConstantSigned(matchB.group(4), 32)
                if mem1+1 == mem2:
                    # This optimization won't work if inside a sound related function
                    # since we can only send bytes to the Z80 ports
                    if not in_a_SGDK_sound_related_routine(modified_lines):
                        xy = ((x << 8) | (y & 0xff)) & 0xffff
                        optimized_lines = [
                            f'{matchA.group(1)}move.w{matchA.group(2)}#{xy},{mem1}'
                        ]
                        return (optimized_lines, 2)

        # Move word constants into consecutive memory
        # If mem1+2 == mem2
        # move.w   #x,mem1    ->    move.l  #xy,mem1       ; Saves 12 cycles
        # move.w   #y,mem2
        # xy = (x << 16) | (y & 0xffff)
        move_constant_word_to_mem_pattern = r'^(\s*)move\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+);?$'
        matchA = re.match(move_constant_word_to_mem_pattern, line_A)
        if matchA:
            matchB = re.match(move_constant_word_to_mem_pattern, line_B)
            if matchB:
                x = parseConstantUnsigned(matchA.group(3))
                y = parseConstantUnsigned(matchB.group(3))
                mem1 = parseConstantSigned(matchA.group(4), 32)
                mem2 = parseConstantSigned(matchB.group(4), 32)
                if mem1+2 == mem2:
                    xy = ((x << 16) | (y & 0xffff)) & 0xffffffff
                    optimized_lines = [
                        f'{matchA.group(1)}move.l{matchA.group(2)}#{xy},{mem1}'
                    ]
                    return (optimized_lines, 2)

        # Move byte constants into consecutive memory calculated from effective address
        # If d1+1 == d2
        # move.b   #x,d1(aN)  ->    move.w  #xy,d1(aN)     ; Saves 16 cycles
        # move.b   #y,d2(aN)
        # xy = (x << 8) | (y & 0xff)
        move_constant_byte_to_mem_ea_pattern = r'^(\s*)move\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7])\)'
        matchA = re.match(move_constant_byte_to_mem_ea_pattern, line_A)
        if matchA:
            matchB = re.match(move_constant_byte_to_mem_ea_pattern, line_B)
            if matchB:
                x = parseConstantUnsigned(matchA.group(3))
                y = parseConstantUnsigned(matchB.group(3))
                disp1 = 0 if matchA.group(4) is None else parseConstantSigned(matchA.group(4), 32)
                disp2 = 0 if matchB.group(4) is None else parseConstantSigned(matchB.group(4), 32)
                aN = matchA.group(5)
                if (disp1 % 2 == 0) and disp1+1 == disp2 and aN == matchB.group(5):
                    # This optimization won't work if inside a sound related function
                    # since we can only send bytes to the Z80 ports
                    if not in_a_SGDK_sound_related_routine(modified_lines):
                        xy = ((x << 8) | (y & 0xff)) & 0xffff
                        disp_str = '' if disp1 == 0 else f'{disp1}'
                        optimized_lines = [
                            f'{matchA.group(1)}move.w{matchA.group(2)}#{xy},{disp_str}({aN})'
                        ]
                        return (optimized_lines, 2)

        # Move byte constants into consecutive memory calculated from effective address
        # If d1+2 == d2
        # move.w   #x,d1(aN)  ->    move.l  #xy,d1(aN)     ; Saves 8 cycles
        # move.w   #y,d2(aN)
        # xy = (x << 16) | (y & 0xffff)
        move_constant_word_to_mem_ea_pattern = r'^(\s*)move\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7])\)'
        matchA = re.match(move_constant_word_to_mem_ea_pattern, line_A)
        if matchA:
            matchB = re.match(move_constant_word_to_mem_ea_pattern, line_B)
            if matchB:
                x = parseConstantUnsigned(matchA.group(3))
                y = parseConstantUnsigned(matchB.group(3))
                disp1 = 0 if matchA.group(4) is None else parseConstantSigned(matchA.group(4), 32)
                disp2 = 0 if matchB.group(4) is None else parseConstantSigned(matchB.group(4), 32)
                aN = matchA.group(5)
                if (disp1 % 2 == 0) and disp1+2 == disp2 and aN == matchB.group(5):
                    xy = ((x << 16) | (y & 0xffff)) & 0xffffffff
                    disp_str = '' if disp1 == 0 else f'{disp1}'
                    optimized_lines = [
                        f'{matchA.group(1)}move.l{matchA.group(2)}#{xy},{disp_str}({aN})'
                    ]
                    return (optimized_lines, 2)

        # Negate a dN and then add/sub into dM or same dN
        matchA = re.match(r'^(\s*)neg\.([bwl])(\s+)(%d[0-7])', line_A)
        if matchA:
            sA = matchA.group(2)
            dN = matchA.group(4)

            # neg.s    dN         ->    add.s   dN,dM       ; Saves 4 cycles. Leaves dN with different value than expected
            # sub.s    dN,dM
            matchB = re.match(r'^\s*sub\.([bwl])\s+(%d[0-7]),\s*(%d[0-7])', line_B)
            if matchB and sA == matchB.group(1) and dN == matchB.group(2):
                dM = matchB.group(3)
                if dM != dN:
                    optimized_lines = [
                        f'{matchA.group(1)}add.{sA}{matchA.group(3)}{dN},{dM}'
                    ]
                    return (optimized_lines, 2)

            # neg.s    dN         ->    eor.s   #val-1,dN   ; Saves 4 cycles
            # add.s    #val,dN
            # Where val is 2^m, dN < val
            matchB = re.match(r'^\s*(add|addq|addi)\.([bwl])\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_B)
            if matchB and sA == matchB.group(2) and dN == matchB.group(4):
                val = parseConstantSigned(matchB.group(3), 32)
                if sA == 'b':
                    val = parseConstantSigned(matchB.group(3), 8)
                elif sA == 'w':
                    val = parseConstantSigned(matchB.group(3), 16)
                # Check if val is a power of 2
                val_abs = abs(val)
                if val_abs > 0 and (val_abs & (val_abs - 1)) == 0:
                    optimized_lines = [
                        f'{matchA.group(1)}eor.{sA}{matchA.group(3)}#{val-1},{dN}'
                    ]
                    print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Next optimization might fail if dN >= val")
                    return (optimized_lines, 2)

            # neg.s    dN         ->    sub.s   dN,dM       ; Saves 4 cycles. Leaves dN with different value than expected
            # add.s    dN,dM
            matchB = re.match(r'^\s*add\.([bwl])\s+(%d[0-7]),\s*(%d[0-7])', line_B)
            if matchB and sA == matchB.group(1) and dN == matchB.group(2):
                dM = matchB.group(3)
                if dM != dN:
                    optimized_lines = [
                        f'{matchA.group(1)}sub.{sA}{matchA.group(3)}{dN},{dM}'
                    ]
                    return (optimized_lines, 2)

        # Clearing consecutive memory
        # No #symbolName neither symbolName are considered as memory operand
        # Note that gcc might use #-15673756 as memory operand
        clr_mem_no_symbol_pattern = r'^(\s*)clr\.([bw])(\s+)#?(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+);?$'
        matchA = re.match(clr_mem_no_symbol_pattern, line_A)
        if matchA:
            matchB = re.match(clr_mem_no_symbol_pattern, line_B)
            if matchB:

                # If mem1+1 == mem2
                # clr.b   mem1       ->    clr.w   mem1
                # clr.b   mem2
                if matchA.group(2) == 'b' and matchB.group(2) == 'b':
                    mem1 = parseConstantSigned(matchA.group(4), 32)
                    mem2 = parseConstantSigned(matchB.group(4), 32)
                    if mem1+1 == mem2:
                        optimized_lines = [
                            f'{matchA.group(1)}clr.w{matchA.group(3)}{mem1}'
                        ]
                        return (optimized_lines, 2)

                # If mem1+2 == mem2
                # clr.w   mem1       ->    clr.l   mem1
                # clr.w   mem2
                # Avoid #symbolName or symbolName as memory operand
                if matchA.group(2) == 'w' and matchB.group(2) == 'w':
                    mem1 = parseConstantSigned(matchA.group(4), 32)
                    mem2 = parseConstantSigned(matchB.group(4), 32)
                    if mem1+2 == mem2:
                        optimized_lines = [
                            f'{matchA.group(1)}clr.l{matchA.group(3)}{mem1}'
                        ]
                        return (optimized_lines, 2)

        # Clearing consecutive memory calculated from effective address
        clr_mem_ea_pattern = r'^(\s*)clr\.([bw])(\s+)(?:(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?\((%a[0-7])\)|\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)?,?(%a[0-7])\))'
        matchA = re.match(clr_mem_ea_pattern, line_A)
        if matchA:
            matchB = re.match(clr_mem_ea_pattern, line_B)
            if matchB:

                # If d1+1 == d2
                # clr.b   d1(aN)       ->    clr.w   d1(aN)
                # clr.b   d2(aN)
                # Note that gcc might put the displacement like next: (d,aN)
                if matchA.group(2) == 'b' and matchB.group(2) == 'b':
                    # Try first matching group: d1(aN)
                    disp1 = 0 if matchA.group(4) is None else parseConstantSigned(matchA.group(4), 16)
                    if disp1 == 0:
                        # Try second matching group: (d1,aN)
                        disp1 = 0 if matchA.group(6) is None else parseConstantSigned(matchA.group(6), 16)
                    # Try first matching group: d2(aN)
                    disp2 = 0 if matchB.group(4) is None else parseConstantSigned(matchB.group(4), 16)
                    if disp2 == 0:
                        # Try second matching group: (d2,aN)
                        disp2 = 0 if matchB.group(6) is None else parseConstantSigned(matchB.group(6), 16)

                    aN = matchA.group(5) or matchA.group(7)
                    if disp1+1 == disp2 and aN == (matchB.group(5) or matchB.group(7)):
                        disp_str = '' if disp1 == 0 else f'{disp1}'
                        optimized_lines = [
                            f'{matchA.group(1)}clr.w{matchA.group(3)}{disp_str}({aN})'
                        ]
                        return (optimized_lines, 2)

                # If d1+2 == d2
                # clr.w   d1(aN)       ->    clr.l   d1(aN)
                # clr.w   d2(aN)
                # Note that gcc might put the displacement like next: (d,aN)
                if matchA.group(2) == 'w' and matchB.group(2) == 'w':
                    # Try first matching group: d1(aN)
                    disp1 = 0 if matchA.group(4) is None else parseConstantSigned(matchA.group(4), 32)
                    if disp1 == 0:
                        # Try second matching group: (d1,aN)
                        disp1 = 0 if matchA.group(6) is None else parseConstantSigned(matchA.group(6), 32)
                    # Try first matching group: d2(aN)
                    disp2 = 0 if matchB.group(4) is None else parseConstantSigned(matchB.group(4), 32)
                    if disp2 == 0:
                        # Try second matching group: (d2,aN)
                        disp2 = 0 if matchB.group(6) is None else parseConstantSigned(matchB.group(6), 32)
                    
                    aN = matchA.group(5) or matchA.group(7)
                    if disp1+2 == disp2 and aN == (matchB.group(5) or matchB.group(7)):
                        disp_str = '' if disp1 == 0 else f'{disp1}'
                        optimized_lines = [
                            f'{matchA.group(1)}clr.l{matchA.group(3)}{disp_str}({aN})'
                        ]
                        return (optimized_lines, 2)

        if USE_AGGRESSIVE_COMPACT_TWO_WORDS_PUSH_INTO_STACK:

            # Push 2 words consecutively into the stack.
            # move.w  xN,-(sp)     ->    move.l  xN,sp     ; Saves 8 cycles
            # move.w  #0,-(sp)
            matchA = re.match(r'^(\s*)move\.w(\s+)(%[ad][0-7]),\s*-\(%sp\)', line_A)
            if matchA:
                xN = matchA.group(3)
                matchB = re.match(r'^\s*move\.w\s+#0,\s*-\(%sp\)', line_B)
                if matchB:
                    optimized_lines = [
                        f'{matchA.group(1)}move.l{matchA.group(2)}{xN},-(%sp)'
                    ]
                    return (optimized_lines, 2)

        if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION:

            # Clearing consecutively the stack by just offseting the sp.
            # clr.w  -(sp)     ->    subq  #4,sp     ; Saves 20 cycles
            # clr.w  -(sp)
            matchA = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line_A)
            if matchA:
                matchB = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_B)
                if matchB:
                    optimized_lines = [
                        f'{matchA.group(1)}subq{matchA.group(2)}#4,%sp'
                    ]
                    return (optimized_lines, 2)

            # Clearing consecutively the stack by just offseting the sp.
            # clr.l  -(sp)     ->    subq  #8,sp     ; Saves 36 cycles
            # clr.l  -(sp)
            # Also considers:  pea  0.w
            matchA_clr = re.match(r'^(\s*)clr\.l(\s+)-\(%sp\)', line_A)
            matchA_pea = re.match(r'^(\s*)pea(\s+)0.w', line_A)
            matchA = matchA_clr or matchA_pea
            if matchA:
                matchB_clr = re.match(r'^\s*clr\.l\s+-\(%sp\)', line_B)
                matchB_pea = re.match(r'^\s*pea\s+0.w', line_B)
                if matchB_clr or matchB_pea:
                    optimized_lines = [
                        f'{matchA.group(1)}subq{matchA.group(2)}#8,%sp'
                    ]
                    return (optimized_lines, 2)

        else:

            # Clearing consecutively the stack by pushing 0.
            # clr.w  -(sp)     ->    pea   0.w       ; Saves 12 cycles
            # clr.w  -(sp)
            matchA = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line_A)
            if matchA:
                matchB = re.match(r'^\s*clr\.w\s+-\(%sp\)', line_B)
                if matchB:
                    optimized_lines = [
                        f'{matchA.group(1)}pea{matchA.group(2)}0.w'
                    ]
                    return (optimized_lines, 2)

        # Clear higher byte of word with 0xFF (255)
        # move.w  xN,dN    ->   moveq   #0,dN   ; Saves 4 cycles
        # and.w   #255,dN       move.b  xN,dN
        matchA = re.match(r'^(\s*)move\.([bw])(\s+)(%[ad][0-7]),\s*(%d[0-7])', line_A)
        if matchA:
            xN = matchA.group(4)
            dN = matchA.group(5)
            matchB = re.match(r'^\s*(and|andi)\.w\s+#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?,\s*(%d[0-7])', line_B)
            if matchB and dN == matchB.group(4):
                val = parseConstantUnsigned(matchB.group(2))
                if val == 0xFF:
                    optimized_lines = [
                        f'{matchA.group(1)}moveq {matchA.group(3)}#0,{dN}',
                        f'{matchA.group(1)}move.b{matchA.group(3)}{xN},{dN}'
                    ]
                    return (optimized_lines, 2)

        if USE_AGGRESSIVE_AVOID_CLEAR_BEFORE_MOVE_WORD_INTO_DN:

            # Clean register dN before moving a word from memory into dN.
            # This pattern appears when dN is later used in an indirection (aN,dN.w).
            # but not when used in arithmetic or assignment for aN reg: add.l/sub.l/move.l dN,aN
            # moveq   #0,dN        ->   move.w  <ea>,dN     ; Saves 4 cycles
            # move.w  <ea>,dN
            # Displacement disp is optional
            matchA = re.match(r'^(\s*)(moveq|move)(\.l)?(\s+)#0,\s*(%d[0-7])', line_A)
            if matchA:
                dN = matchA.group(5)
                matchB = re.match(r'^\s*move\.w\s+([,^]),\s*(%d[0-7])', line_B)
                if matchB and dN == matchB.group(3):
                    ea = matchB.group(1)
                    # TODO: ensure dN is not immediately or nearby used by: add.l/sub.l/move.l dN,aN
                    optimized_lines = [
                        f'{matchA.group(1)}move.w{matchA.group(4)}{ea},{dN}'
                    ]
                    return (optimized_lines, 2)

        ############################################################################
        # Rotates Left
        ############################################################################

        if IS_MOVEQ_INSTRUCTION_REGEX.match(line_A) and IS_ROL_INSTRUCTION_REGEX.match(line_B):

            matchA = re.match(r'^(\s*)(moveq|move)\.?[bwl]?(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
            if matchA:
                dM = matchA.group(5)
                val = parseConstantSigned(matchA.group(4), 8)

                # 0 ≤ x ≤ 7
                # moveq    #8+x,dM    ->    ror.w  #8-x,dN      ; Saves 4+4*x cycles
                # rol.w    dM,dN
                matchB = re.match(r'^(\s*)(rol\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 0 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_line = f'{matchA.group(1)}ror.w{matchB.group(3)}#{8-x},{dN}'
                        return ([optimized_line], 2)

                # 1 ≤ x ≤ 7
                # moveq    #8+x,dM    ->    swap    dN           ; Saves 4*x cycles
                # rol.l    dM,dN            ror.l   #8-x,dN
                matchB = re.match(r'^(\s*)(rol\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 1 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}ror.l{matchB.group(3)}#{8-x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #16,dM     ->    swap    dN           ; Saves 40 cycles
                # rol.l    dM,dN
                matchB = re.match(r'^(\s*)(rol\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 16 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}swap{matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # 1 ≤ x ≤ 7
                # moveq    #16+x,dM   ->    swap    dN           ; Saves 32 cycles
                # rol.l    dM,dN            rol.l   #x,dN
                matchB = re.match(r'^(\s*)(rol\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 1 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}rol.l{matchB.group(3)}#{x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # 8 ≤ x ≤ 15
                # moveq    #16+x,dM   ->    ror.l   #16-x,dN     ; Saves 4+4*x cycles
                # rol.l    dM,dN
                matchB = re.match(r'^(\s*)(rol\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 8 <= x <= 15:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_line = f'{matchA.group(1)}ror.l{matchB.group(3)}#{16-x},{dN}'
                        return ([optimized_line], 2)

        ############################################################################
        # Rotates Right
        ############################################################################

        if IS_MOVEQ_INSTRUCTION_REGEX.match(line_A) and IS_ROR_INSTRUCTION_REGEX.match(line_B):

            matchA = re.match(r'^(\s*)(moveq|move)\.?[bwl]?(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
            if matchA:
                dM = matchA.group(5)
                val = parseConstantSigned(matchA.group(4), 8)

                # 0 ≤ x ≤ 7
                # moveq    #8+x,dM    ->    rol.w   #8-x,dN      ; Saves 4+4*x cycles
                # ror.w    dM,dN
                matchB = re.match(r'^(\s*)(ror\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 0 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_line = f'{matchA.group(1)}rol.w{matchB.group(3)}#{8-x},{dN}'
                        return ([optimized_line], 2)

                # 1 ≤ x ≤ 7
                # moveq    #8+x,dM    ->    swap    dN           ; Saves 4*x cycles
                # ror.l    dM,dN            rol.l   #8-x,dN
                matchB = re.match(r'^(\s*)(ror\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 1 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}rol.l{matchB.group(3)}#{8-x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #16,dM     ->    swap    dN           ; Saves 40 cycles
                # ror.l    dM,dN
                matchB = re.match(r'^(\s*)(ror\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 16 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}swap{matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # 1 ≤ x ≤ 7
                # moveq    #16+x,dM   ->    swap    dN           ; Saves 32 cycles
                # ror.l    dM,dN            ror.l   #x,dN
                matchB = re.match(r'^(\s*)(ror\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 1 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}ror.l{matchB.group(3)}#{x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # 8 ≤ x ≤ 15
                # moveq    #16+x,dM   ->    rol.l   #16-x,dN     ; Saves 4+4*x cycles
                # ror.l    dM,dN
                matchB = re.match(r'^(\s*)(ror\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 8 <= x <= 15:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_line = f'{matchA.group(1)}rol.l{matchB.group(3)}#{16-x},{dN}'
                        return ([optimized_line], 2)

        ############################################################################
        # Logical Shift Left and Arithmetic Shift Left
        # All lsl peephole optimizations also apply to asl
        ############################################################################

        if IS_MOVEQ_INSTRUCTION_REGEX.match(line_A) and (IS_LSL_INSTRUCTION_REGEX.match(line_B) or IS_ASL_INSTRUCTION_REGEX.match(line_B)):

            matchA = re.match(r'^(\s*)(moveq|move)\.?[bwl]?(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
            if matchA:
                dM = matchA.group(5)
                val = parseConstantSigned(matchA.group(4), 8)

                # 1 ≤ x ≤ 47
                # moveq    #8+x,dM    ->    clr.b    dN             ; Saves 18+2*x cycles
                # lsl.b    dM,dN
                matchB = re.match(r'^(\s*)(lsl\.b|asl\.b)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 1 <= x <= 47:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}clr.b{matchA.group(3)}{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #9,dM      ->    move.b   dN,-(sp)       ; Saves 4 cycles
                # lsl.w    dM,dN            move.w   (sp)+,dN
                #                           clr.b    dN
                #                           add.w    dN,dN
                matchB = re.match(r'^(\s*)(lsl\.w|asl\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 9 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}move.b{matchA.group(3)}{dN},-(%sp)',
                        f'{matchA.group(1)}move.w{matchA.group(3)}(%sp)+,{dN}',
                        f'{matchA.group(1)}clr.b {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}add.w {matchA.group(3)}{dN},{dN}'
                    ]
                    return (optimized_lines, 2)

                # 2 ≤ x ≤ 7
                # moveq    #8+x,dM    ->    ror.w    #8-x,dN        ; Saves 4*x-4 cycles
                # lsl.w    dM,dN            andi.w   #~((1<<(8+x))-1),dN
                matchB = re.match(r'^(\s*)(lsl\.w|asl\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 2 <= x <= 7:
                        dN = matchB.group(5)
                        mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}ror.w {matchA.group(3)}#{8-x},{dN}',
                            f'{matchA.group(1)}andi.w{matchA.group(3)}#{mask},{dN}'
                        ]
                        return (optimized_lines, 2)

                # 0 ≤ x ≤ 47
                # moveq    #16+x,dM   ->    clr.w    dN             ; Saves 38+2*x cycles
                # lsl.w    dM,dN
                matchB = re.match(r'^(\s*)(lsl\.w|asl\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 0 <= x <= 47:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}'
                        ]
                        return (optimized_lines, 2)

                # 3 ≤ x ≤ 7
                # moveq    #8+x,dM    ->    swap     dN             ; Saves 4*x-8 cycles
                # lsl.l    dM,dN            ror.l    #8-x,dN
                #                           andi.w   #~((1<<(8+x))-1),dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 3 <= x <= 7:
                        dN = matchB.group(5)
                        mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}ror.l {matchA.group(3)}#{8-x},{dN}',
                            f'{matchA.group(1)}andi.w{matchA.group(3)}#{mask},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #16,dM     ->    swap     dN             ; Saves 36 cycles
                # lsl.l    dM,dN            clr.w    dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 16 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # moveq    #17,dM     ->    add.w    dN,dN          ; Saves 34 cycles
                # lsl.l    dM,dN            swap     dN
                #                           clr.w    dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 17 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}add.w{matchA.group(3)}{dN},{dN}',
                        f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # moveq    #18,dM     ->    add.w    dN,dN          ; Saves 32 cycles
                # lsl.l    dM,dN            add.w    dN,dN
                #                           swap     dN
                #                           clr.w    dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 18 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}add.w{matchA.group(3)}{dN},{dN}',
                        f'{matchA.group(1)}add.w{matchA.group(3)}{dN},{dN}',
                        f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # 3 ≤ x ≤ 7
                # moveq    #16+x,dM   ->    lsl.w    #x,dN          ; Saves 30 cycles
                # lsl.l    dM,dN            swap     dN
                #                           clr.w    dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 3 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}lsl.w{matchA.group(3)}#{x},{dN}',
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #24,dM     ->    move.b   dN,-(sp)       ; Saves 32 cycles
                # lsl.l    dM,dN            move.w   (sp)+,dN
                #                           clr.b    dN
                #                           swap     dN
                #                           clr.w    dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 24 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}move.b{matchA.group(3)}{dN},-(%sp)',
                        f'{matchA.group(1)}move.w{matchA.group(3)}(%sp)+,{dN}',
                        f'{matchA.group(1)}clr.b {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}clr.w {matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # moveq    #25,dM     ->    move.b   dN,-(sp)       ; Saves 30 cycles
                # lsl.l    dM,dN            move.w   (sp)+,dN
                #                           clr.b    dN
                #                           add.w    dN,dN
                #                           swap     dN
                #                           clr.w    dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 25 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}move.b{matchA.group(3)}{dN},-(%sp)',
                        f'{matchA.group(1)}move.w{matchA.group(3)}(%sp)+,{dN}',
                        f'{matchA.group(1)}clr.b {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}add.w {matchA.group(3)}{dN},{dN}',
                        f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}clr.w {matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # 2 ≤ x ≤ 7
                # moveq    #24+x,dM   ->    ror.w    #8-x,dN        ; Saves 4*x+22 cycles
                # lsl.l    dM,dN            andi.w   #~((1<<(8+x))-1),dN
                #                           swap     dN
                #                           clr.w    dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 24
                    if 2 <= x <= 7:
                        dN = matchB.group(5)
                        mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}ror.w {matchA.group(3)}#{8-x},{dN}',
                            f'{matchA.group(1)}andi.w{matchA.group(3)}#{mask},{dN}',
                            f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}clr.w {matchA.group(3)}{dN}'
                        ]
                        return (optimized_lines, 2)

                # 0 ≤ x ≤ 31
                # moveq    #32+x,dM   ->    moveq    #0,dN          ; Saves 72+2*x cycles
                # lsl.l    dM,dN
                matchB = re.match(r'^(\s*)(lsl\.l|asl\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 32
                    if 0 <= x <= 31:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}moveq{matchA.group(3)}#0,{dN}'
                        ]
                        return (optimized_lines, 2)

        ############################################################################
        # Logical Shift Right
        ############################################################################

        if IS_MOVEQ_INSTRUCTION_REGEX.match(line_A) and IS_LSR_INSTRUCTION_REGEX.match(line_B):

            matchA = re.match(r'^(\s*)(moveq|move)\.?[bwl]?(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
            if matchA:
                dM = matchA.group(5)
                val = parseConstantSigned(matchA.group(4), 8)

                # 1 ≤ x ≤ 47
                # moveq    #8+x,dM    ->    clr.b    dN        ; Saves 18+2*x cycles
                # lsr.b    dM,dN
                matchB = re.match(r'^(\s*)(lsr\.b)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 1 <= x <= 47:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}clr.b{matchA.group(3)}{dN}'
                        ]
                        return (optimized_lines, 2)

                # 2 ≤ x ≤ 6
                # moveq    #8+x,dM    ->    andi.w   #~((1<<(8+x))-1),dN    ; Saves 4*x-4 cycles
                # lsr.w    dM,dN            rol.w    #8-x,dN
                matchB = re.match(r'^(\s*)(lsr\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 2 <= x <= 6:
                        dN = matchB.group(5)
                        mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}andi.w{matchA.group(3)}#{mask},{dN}',
                            f'{matchA.group(1)}rol.w {matchB.group(3)}#{8-x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #15,dM     ->    add.w    dN,dN     ; Saves 28 cycles
                # lsr.w    dM,dN            subx.w   dN,dN
                #                           neg.w    dN
                matchB = re.match(r'^(\s*)(lsr\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 15 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}add.w {matchA.group(3)}{dN},{dN}',
                        f'{matchA.group(1)}subx.w{matchA.group(3)}{dN},{dN}',
                        f'{matchA.group(1)}neg.w {matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # 0 ≤ x ≤ 47
                # moveq    #16+x,dM   ->    clr.w    dN        ; Saves 38+2*x cycles
                # lsr.w    dM,dN
                matchB = re.match(r'^(\s*)(lsr\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 0 <= x <= 47:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}'
                        ]
                        return (optimized_lines, 2)

                # 3 ≤ x ≤ 7
                # moveq    #8+x,dM    ->    andi.w   #~((1<<(8+x))-1),dN    ; Saves 4*x-8 cycles
                # lsr.l    dM,dN            swap     dN
                #                           rol.l    #8-x,dN
                matchB = re.match(r'^(\s*)(lsr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 3 <= x <= 7:
                        dN = matchB.group(5)
                        mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}andi.w{matchA.group(3)}#{mask},{dN}',
                            f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}rol.l {matchA.group(3)}#{8-x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #16,dM     ->    clr.w    dN        ; Saves 36 cycles
                # lsr.l    dM,dN            swap     dN
                matchB = re.match(r'^(\s*)(lsr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 16 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}',
                        f'{matchA.group(1)}swap {matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # 1 ≤ x ≤ 7
                # moveq    #16+x,dM   ->    clr.w    dN        ; Saves 30 cycles
                # lsr.l    dM,dN            swap     dN
                #                           lsr.w    #x,dN
                matchB = re.match(r'^(\s*)(lsr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 1 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}clr.w{matchA.group(3)}{dN}',
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}lsr.w{matchA.group(3)}#{x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #24,dM     ->    swap     dN        ; Saves 36 cycles
                # lsr.l    dM,dN            move.w   dN,-(sp)
                #                           moveq    #0,dN
                #                           move.b   (sp)+,dN
                matchB = re.match(r'^(\s*)(lsr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 24 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}move.w{matchA.group(3)}{dN},-(%sp)',
                        f'{matchA.group(1)}moveq {matchA.group(3)}#0,{dN}',
                        f'{matchA.group(1)}move.b{matchA.group(3)}(%sp)+,{dN}'
                    ]
                    return (optimized_lines, 2)

                # 1 ≤ x ≤ 6
                # moveq    #24+x,dM   ->    clr.w    dN        ; Saves 4*x+22 cycles
                # lsr.l    dM,dN            swap     dN
                #                           andi.w   #~((1<<(8+x))-1),dN
                #                           rol.w    #8-x,dN
                matchB = re.match(r'^(\s*)(lsr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 24
                    if 1 <= x <= 6:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                        optimized_lines = [
                            f'{matchA.group(1)}clr.w {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}andi.w{matchA.group(3)}#{mask},{dN}',
                            f'{matchA.group(1)}rol.w {matchA.group(3)}#{8-x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #31,dM     ->    add.l    dN,dN     ; Saves 58 cycles
                # lsr.l    dM,dN            moveq    #0,dN
                #                           addx.w   dN,dN
                matchB = re.match(r'^(\s*)(lsr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 31 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}add.l {matchA.group(3)}{dN},{dN}',
                        f'{matchA.group(1)}moveq {matchA.group(3)}#0,{dN}',
                        f'{matchA.group(1)}addx.w{matchA.group(3)}{dN},{dN}'
                    ]
                    return (optimized_lines, 2)

                # 0 ≤ x ≤ 31
                # moveq    #32+x,dM   ->    moveq    #0,dN     ; Saves 72+2*x cycles
                # lsr.l    dM,dN
                matchB = re.match(r'^(\s*)(lsr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 32
                    if 0 <= x <= 31:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}moveq{matchA.group(3)}#0,{dN}'
                        ]
                        return (optimized_lines, 2)

        ############################################################################
        # Arithmetic Shift Right
        ############################################################################

        if IS_MOVEQ_INSTRUCTION_REGEX.match(line_A) and IS_ASR_INSTRUCTION_REGEX.match(line_B):

            matchA = re.match(r'^(\s*)(moveq|move)\.?[bwl]?(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line_A)
            if matchA:
                dM = matchA.group(5)
                val = parseConstantSigned(matchA.group(4), 8)

                # 2 ≤ x ≤ 6
                # moveq    #8+x,dM    ->    ext.l  dN          ; Saves 4*x-6 cycles
                # asr.w    dM,dN            swap   dN
                #                           rol.l  #8-x,dN
                matchB = re.match(r'^(\s*)(asr\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 8
                    if 2 <= x <= 6:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}ext.l{matchA.group(3)}{dN}',
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}rol.l{matchB.group(3)}#{8-x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # 0 ≤ x ≤ 48
                # moveq    #15+x,dM   ->    add.w  dN,dN       ; Saves 32+2*x cycles
                # asr.w    dM,dM            subx.w dN,dN
                matchB = re.match(r'^(\s*)(asr\.w)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 15
                    if 0 <= x <= 48:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}add.w {matchA.group(3)}{dN},{dN}',
                            f'{matchA.group(1)}subx.w{matchB.group(3)}{dN},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #16,dM     ->    swap   dN          ; Saves 36 cycles
                # asr.l    dM,dN            ext.l  dN
                matchB = re.match(r'^(\s*)(asr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 16 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}ext.l{matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # 1 ≤ x ≤ 7
                # moveq    #16+x,dM   ->    swap   dN          ; Saves 30 cycles
                # asr.l    dM,dN            ext.l  dN
                #                           asr.w  #x,dN
                matchB = re.match(r'^(\s*)(asr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 16
                    if 1 <= x <= 7:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}ext.l{matchA.group(3)}{dN}',
                            f'{matchA.group(1)}asr.w{matchB.group(3)}#{x},{dN}'
                        ]
                        return (optimized_lines, 2)

                # moveq    #24,dM     ->    swap   dN          ; Saves 28 cycles
                # asr.l    dM,dN            ext.l  dN
                #                           move.w dN,-(sp)
                #                           move.b (sp)+,dN
                #                           ext.w  dN
                matchB = re.match(r'^(\s*)(asr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 24 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                    optimized_lines = [
                        f'{matchA.group(1)}swap  {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}ext.l {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}move.w{matchA.group(3)}{dN},-(%sp)',
                        f'{matchA.group(1)}move.b{matchA.group(3)}(%sp)+,{dN}',
                        f'{matchA.group(1)}ext.w {matchA.group(3)}{dN}'
                    ]
                    return (optimized_lines, 2)

                # moveq    #25,dM     ->    swap   dN          ; Saves 26 cycles
                # asr.l    dM,dN            ext.l  dN
                #                           moveq  #9,dM
                #                           asr.w  dM,dN
                matchB = re.match(r'^(\s*)(asr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if val == 25 and matchB and dM == matchB.group(4):
                    dN = matchB.group(5)
                    dM = matchB.group(4)
                    optimized_lines = [
                        f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                        f'{matchA.group(1)}ext.l{matchA.group(3)}{dN}',
                        f'{matchA.group(1)}moveq{matchA.group(3)}#9,{dM}',
                        f'{matchA.group(1)}asr.w{matchB.group(3)}{dM},{dN}'
                    ]
                    return (optimized_lines, 2)

                # 2 ≤ x ≤ 6
                # moveq    #24+x,dM   ->    swap   dN          ; Saves 20+4*x cycles
                # asr.l    dM,dN            ext.l  dN
                #                           swap   dN
                #                           rol.l  #8-x,dN
                #                           ext.l  dN
                matchB = re.match(r'^(\s*)(asr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 24
                    if 2 <= x <= 6:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}ext.l{matchA.group(3)}{dN}',
                            f'{matchA.group(1)}swap {matchA.group(3)}{dN}',
                            f'{matchA.group(1)}rol.l{matchB.group(3)}#{8-x},{dN}',
                            f'{matchA.group(1)}ext.l{matchA.group(3)}{dN}'
                        ]
                        return (optimized_lines, 2)

                # 0 ≤ x ≤ 32
                # moveq    #31+x,dM   ->    add.l  dN,dN       ; Saves 58+2*x cycles
                # asr.l    dM,dN            subx.l dN,dN
                matchB = re.match(r'^(\s*)(asr\.l)(\s+)(%d[0-7]),\s*(%d[0-7])', line_B)
                if matchB and dM == matchB.group(4):
                    x = val - 31
                    if 0 <= x <= 32:
                        dN = matchB.group(5)
                        if_reg_not_used_anymore_then_remove_from_push_pop(dM, i_line, lines, modified_lines, 2)
                        optimized_lines = [
                            f'{matchA.group(1)}add.l {matchA.group(3)}{dN},{dN}',
                            f'{matchA.group(1)}subx.l{matchB.group(3)}{dN},{dN}'
                        ]
                        return (optimized_lines, 2)

        # Add more multi-line patterns here for 2 lines

    return (None, 0)

indirection_0_pattern = re.compile(
    r'^\s*'
    r'([a-zA-Z]+)\.?([bwl])?\s+'    # instruction mnemonic with optional .[bwl]
    r'(\s+[^,]*,)?\s*'              # optional first operand including the comma
    r'(?:0\((%a[0-7]|%sp|%pc)\)|\(0,(%a[0-7]|%sp)\))'  # 0(aN) or (0,aN)
)

def optimizeSingleLine_Peepholes(line, i_line, lines, modified_lines):
    """
    Optimize a single line of assembly code.
    Returns a tuple of (optimized_lines, was_optimized) where:
    - optimized_lines: is a list of new lines optimized lines (empty list if not).
    - was_optimized: is a boolean indicating if optimization occurred.
    """

    if OPTIMIZE_INLINE_ASM_BLOCKS:
        # If line contains the flag that mandates to skip it from be optimized -> do nothing and return
        if line.endswith(SKIP_OPTIMIZATION_FLAG):
            return ([], False)

    ############################################################################
    # Miscellaneous
    ############################################################################

    # or.s   #val,dN    ->    bset.[bwl]  #b,dN      ; Saves [4,12] cycles
    # Where val = 2^b (only 1 bit set and is at position b)
    match = re.match(r'^(\s*)(or|ori)\.([bwl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line)
    if match:
        s = match.group(3)
        val = parseConstantUnsigned(match.group(5))
        dN = match.group(6)
        bit_to_set = find_bset_bit(val)
        if bit_to_set is not None:
            s_bset = 'l'
            if bit_to_set < 8:
                s_bset = 'b'
            # If s_bset is bigger than s then skip from optimize
            if not (s_bset == 'l' and (s == 'w' or s == 'b')):
                optimized_line = f'{match.group(1)}bset.{s_bset}{match.group(4)}#{bit_to_set},{dN}'
                return ([optimized_line], True)

    # eor.s  #-1,*      ->    not.s   *          ; Saves 4 cycles
    match = re.match(r'^(\s*)(eor|eori)\.([bwl])(\s+)#-1,\s*(.+)', line)
    if match:
        s = match.group(3)
        optimized_line = f'{match.group(1)}not.{s}{match.group(4)}{match.group(5)}'
        return ([optimized_line], True)

    # Remove 0 indirection
    # any_inst   *0(aN)*     ->    any_inst   *(aN)*     ; Saves 4 cycles
    # Note that gcc might put the displacement like next: (0,aN)
    match = indirection_0_pattern.match(line)
    if match:
        optimized_line = indirection_0_pattern.sub(
            lambda m: f"{m.group(1)}({m.group(2) or m.group(3)})",
            line
        )
        return ([optimized_line], True)

    ############################################################################
    # Comparison using constants
    ############################################################################

    # cmp.s  #0,dN     ->    tst.s    dN       ; Saves [4,10] cycles
    match = re.match(r'^(\s*)(cmp|cmpi)\.([bwl])(\s+)#0,\s*(%d[0-7])', line)
    if match:
        s = match.group(3)
        dN = match.group(5)
        optimized_line = f'{match.group(1)}tst.{s}{match.group(4)}{dN}'
        return ([optimized_line], True)

    # If -128 <= val <= 127
    # cmp.l  #val,dN   ->    moveq.l  #val,dM  ; Saves 4 cycles
    #                        cmp.l    dM,dN
    # Needs a free register dM
    match = re.match(r'^(\s*)(cmp|cmpi)\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantSigned(match.group(4), 8)
        if -128 <= val <= 127:
            dN = match.group(5)
            dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{match.group(1)}moveq{match.group(3)}#{val},{dM}',
                    f'{match.group(1)}cmp.l{match.group(3)}{dM},{dN}'
                ]
                return (optimized_lines, True)

    # cmp.s  #0,aN     ->    move.s   aN,dM    ; Saves [6,10] cycles
    # Needs a free register dM
    match = re.match(r'^(\s*)(cmp|cmpa)\.([bwl])(\s+)#0,\s*(%a[0-7]|%sp)', line)
    if match:
        dM = find_free_after_use_data_register([], i_line, lines, modified_lines)[0]
        if dM is None:
            dM = find_unused_data_register([], i_line, lines, modified_lines)[0]
        if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
            s = match.group(3)
            aN = match.group(5)
            optimized_line = f'{match.group(1)}move.{s}{match.group(4)}{aN},{dM}'
            return ([optimized_line], True)

    ############################################################################
    # Set constants
    ############################################################################

    match = re.match(r'^(\s*)move\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantSigned(match.group(3), 8)
        dN = match.group(4)

        # Move 0 to dN.
        # move.l  #0,dN    ->   moveq    #0,dN         ; Saves 8 cycles
        if val == 0:
            optimized_line = f'{match.group(1)}moveq{match.group(2)}#0,{dN}'
            return ([optimized_line], True)

        # Move -128 <= val <= 127
        # move.l  #val,dN  ->   moveq    #val,dN       ; Saves 8 cycles
        if -128 <= val <= 127:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}moveq{match.group(2)}#{val},{dN}'
            return ([optimized_line], True)

        val = parseConstantSigned(match.group(3), 16)

        # Move -136 ... -129 values.
        # move.l  #val,dN  ->   moveq    #-128,dN      ; Saves 0 cycles, but it's 2 bytes smaller
        #                       subq.l   #val+128,dN
        if -136 <= val <= -129:
            optimized_lines = [
                f'{match.group(1)}moveq{match.group(2)}#-128,{dN}',
                f'{match.group(1)}subq.l{match.group(2)}#{val+128},{dN}',
            ]
            return (optimized_lines, True)

        # Move 128 ... 255 values.
        # move.l  #val,dN  ->   moveq    #255-val,dN   ; Saves 4 cycles
        #                       not.b    dN
        if 128 <= val <= 255:
            optimized_lines = [
                f'{match.group(1)}moveq{match.group(2)}#{255-val},{dN}',
                f'{match.group(1)}not.b{match.group(2)}{dN}',
            ]
            return (optimized_lines, True)

        # Move (128 <= val <= 254) or (-256 <= val <= -130) where n is even
        if ((128 <= val <= 254) or (-256 <= val <= -130)) and (n % 2 == 0):
            optimized_lines = [
                f'{match.group(1)}moveq{match.group(2)}#{val/2},{dN}',
                f'{match.group(1)}add.b{match.group(2)}{dN},{dN}',
            ]
            return (optimized_lines, True)

        val = parseConstantSigned(match.group(3), 32)

        # Move 65534 <= val <= 65408 or -65409 <= val <= -65536 values.
        # move.l  #val,dN  ->   moveq    #65535-abs(val),dN   ; Saves 4 cycles
        #                       not.w    dN
        if (65534 <= val <= 65408) or (-65409 <= val <= -65536):
            optimized_lines = [
                f'{match.group(1)}moveq{match.group(2)}#{65535-abs(val)},{dN}',
                f'{match.group(1)}not.w{match.group(2)}{dN}',
            ]
            return (optimized_lines, True)

        # Move a specific signed 16bit value.
        # move.l  #val,dN  ->    moveq   #m,dN         ; Saves 0 cycles, but it's 2 bytes smaller
        #                        bchg.l  dN,dN
        m = getMForMovelOptimization(val)
        if m is not None:
            optimized_lines = [
                f'{match.group(1)}moveq {match.group(2)}#{m},{dN}',
                f'{match.group(1)}bchg.l{match.group(2)}{dN},{dN}',
            ]
            return (optimized_lines, True)

        # Move -8323073 <= val <= -65537 or 65536 <= val <= 8323072
        # If val = m*65536. Ie val is multiple of 65536.
        # move.l  #val,dN  ->   moveq    #m,dN
        #                       swap     dN
        if (-8323073 <= val <= -65537) or (65536 <= val <= 8323072):
            # is val multiple of 65536
            if val % 65536 == 0:
                m = val // 65536  # floor division
                optimized_lines = [
                    f'{match.group(1)}moveq{match.group(2)}#{m},{dN}',
                    f'{match.group(1)}swap {match.group(2)}{dN}',
                ]
                return (optimized_lines, True)

        # Move $FF81 ... $FFFF values and $FFFF0001 ... $FFFF0080 values.
        #       -127 ... -1                  -65535 ... -65408
        # MOVE.L #x,Dn   -> optimized as:
        #   - MOVEQ for 16-bit values where $FF81 <= x <= $FFFF
        #   and
        #   - MOVEQ+NEG.W for 32-bit values where $FFFF0001 <= x <= $FFFF0080
        # Explanation:
        #   - 16-bit values:  moveq #x,Dn   (with x=$81...$FF, sign extended becomes $FFFFFF81...$FFFFFFFF)
        #   and
        #   - 32-bit values:  moveq #-x,Dn  (with x=$01...$80, then -x=$FF...$80, sign extended becomes $FFFFFFFF...$FFFFFF80)
        #                     neg.w Dn      (leaves $0001..$0080 in lower word only)
        
        # Check for 16-bit values $FF81..$FFFF (-127 ... -1)
        if ((val & 0xFFFF0000) == 0) and (0xFF81 <= val <= 0xFFFF):
            val_adjusted = ((val & 0xFF) - 256)
            optimized_line = f'{match.group(1)}moveq{match.group(2)}#{val_adjusted},{dN}'
            return ([optimized_line], True)
        # Check for 32-bit values $FFFF0001..$FFFF0080 (-65535 ... -65408)
        if ((val & 0xFFFF0000) == 0xFFFF0000) and (0x0001 <= (val & 0xFFFF) <= 0x0080):
            val_adjusted = ((-val & 0xFF) - 256)
            optimized_lines = [
                f'{match.group(1)}moveq{match.group(2)}#{val_adjusted},{dN}',
                f'{match.group(1)}neg.w{match.group(2)}{dN}',
            ]
            return (optimized_lines, True)
        
        # Move $00010000 ... $007F0000 values. But keeping always low 0000.
        #          65536 ... 8323072
        # Move a constant value $N0000 (where $0001 <= N <= $007F) to a data register.
        #                                         1 <= N <= 127
        # The moveq instruction sign extends the last bit.
        # move.l  #$N0000,Dn   ->   moveq    #N,Dn
        #                           swap     Dn
        if (val & 0xffff) == 0x0000:
            n = val >> 16  # Python only has Arithmetic Shift Right
            if 0x0001 <= (n & 0xffff) <= 0x007f:
                optimized_lines = [
                    f'{match.group(1)}moveq{match.group(2)}#{n},{dN}',
                    f'{match.group(1)}swap {match.group(2)}{dN}'
                ]
                return (optimized_lines, True)

        # Move $FF80FFFF ... $FFFEFFFF values. But keeping always low FFFF.
        #       -8323073 ... -65537
        # Move a constant value $NFFFF (where $FF80 <= N <= $FFFF) to a data register.
        #                                      -128 <= N <= -2
        # The moveq instruction sign extends the last bit.
        # move.l  #$NFFFF,Dn   ->   moveq    #N,Dn
        #                           swap     Dn
        if (val & 0xffff) == 0xffff:
            n = val >> 16  # Python only has Arithmetic Shift Right
            if 0xff80 <= (n & 0xffff) <= 0xfffe:
                optimized_lines = [
                    f'{match.group(1)}moveq{match.group(2)}#{n},{dN}',
                    f'{match.group(1)}swap {match.group(2)}{dN}'
                ]
                return (optimized_lines, True)

    # move.b   #-1,dN      ->    st.b    dN        ; Saves 4 cycles
    match = re.match(r'^(\s*)move\.b(\s+)#-1,\s*(%d[0-7])', line)
    if match:
        dN = match.group(3)
        optimized_line = f'{match.group(1)}st.b{match.group(2)}{dN}'
        return ([optimized_line], True)

    # Move long val to aN when -32767 <= val <= 32767, but val != 0
    # move.l   #val,aN    ->   movea.w   #val,aN   ; Saves 4 cycles
    match = re.match(r'^(\s*)(move|movea)\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%a[0-7]|%sp)', line)
    if match:
        val = parseConstantUnsigned(match.group(4))
        if 0 < val <= 65535:
            val_str = match.group(4)
            aN = match.group(5)
            optimized_line = f'{match.group(1)}movea.w{match.group(3)}#{val_str},{aN}'
            return ([optimized_line], True)

    # Push constant val into sp
    # If -32767 <= val <= 32767, ie: val = 0x0000NNNN
    # move.l   #val,-(sp)   ->   pea   val.w     ; Saves 4 cycles
    match = re.match(r'^(\s*)move\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*-\((%sp)\)', line)
    if match:
        val = parseConstantUnsigned(match.group(3))
        if 0 <= val <= 65535:
            val_str = match.group(3)
            optimized_line = f'{match.group(1)}pea{match.group(2)}{val_str}.w'
            return ([optimized_line], True)

    # Push memory address into sp
    # move.l   #mem_addr,-(sp)   ->   pea   mem_addr   ; Saves 8 cycles
    # Egs for mem_addr: #-520158600[.bwl][+-*N], #0xFFFFFFFF[.bwl][+-*N], #symbolName[.bwl][+-*N]
    # NOTE: #symbolName is not being matched, don't know why. However, next reg expr pattern does it.
    match = re.match(r'^(\s*)move\.l(\s+)#([a-zA-Z_]\w*|-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?([\+\-\*]\d+)?(\.[bwl])?,\s*-\(%sp\)', line)
    if match:
        mem_address = ''.join(match.group(i) for i in range(3, 7) if match.group(i))
        optimized_line = f'{match.group(1)}pea{match.group(2)}{mem_address}'
        return ([optimized_line], True)

    # Push constant val into <ea>, where -128 <= val <= 127
    # move.l   #val,<ea>    ->   moveq   #val,dM      ; Saves 4 cycles
    #                            move.l  dM,<ea>
    # Needs a free register dM
    match = re.match(r'^(\s*)move\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(.+);?$', line)
    if match:
        val = parseConstantSigned(match.group(3), 32)
        if -128 <= val <= 127:
            dM = find_free_after_use_data_register([], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_data_register([], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                ea = match.group(4)
                if not ea.startswith(("%a", "%sp")):
                    optimized_lines = [
                        f'{match.group(1)}moveq{match.group(2)}#{val},{dM}',
                        f'{match.group(1)}move.l{match.group(2)}{dM},{ea}'
                    ]
                    return (optimized_lines, True)

    ############################################################################
    # Clear regs and Clearing mask over regs or memory
    ############################################################################

    match = re.match(r'^(\s*)(and|andi)\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantUnsigned(match.group(4))
        dN = match.group(5)

        # Keep lower byte with mask 0xFF (255)
        # and.l   #255,dN      ->     move.b  dN,dM    ; Saves 4 cycles
        #                             moveq   #0,dN
        #                             move.b  dM,dN
        # Needs a free register dM
        if val == 255:
            dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{match.group(1)}move.b{match.group(3)}{dN},{dM}',
                    f'{match.group(1)}moveq {match.group(3)}#0,{dN}',
                    f'{match.group(1)}move.b{match.group(3)}{dM},{dN}'
                ]
                return (optimized_lines, True)

        # Clear upper word with mask 0xFFFF (65535)
        # and.l   #65535,dN    ->     swap   dN    ; Saves 4 cycles
        #                             clr.w  dN
        #                             swap   dN
        if val == 65535:
            optimized_lines = [
                f'{match.group(1)}swap {match.group(3)}{dN}',
                f'{match.group(1)}clr.w{match.group(3)}{dN}',
                f'{match.group(1)}swap {match.group(3)}{dN}'
            ]
            return (optimized_lines, True)

        # Clear lower word with mask 0xFFFF0000 (-65536)
        # and.l   #-65536,dN   ->     clr.w  dN    ; Saves 12 cycles
        if val == 0xffff0000:  # use this due to unsigned parseing of val
            optimized_line = f'{match.group(1)}clr.w{match.group(3)}{dN}'
            return ([optimized_line], True)

    # Byte or Word constant mask
    # and.[bwl]  #val,dN   ->   bclr.[bwl]  #b,dN      ; Saves [2,4,12] cycles
    # Where not(val) = 2^b (only 1 bit set and is at position b)
    match = re.match(r'^(\s*)(andi|and)\.([bwl])(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        s = match.group(3)
        val = parseConstantUnsigned(match.group(5))
        dN = match.group(6)
        bit_to_clear = find_bclr_bit(val)
        if bit_to_clear is not None:
            s_bclr = 'l'
            if bit_to_clear < 8:
                s_bclr = 'b'
            # If s_bclr is bigger than s then skip from optimize
            if not (s_bclr == 'l' and (s == 'w' or s == 'b')):
                optimized_line = f'{match.group(1)}bclr.{s_bclr}{match.group(4)}#{bit_to_clear},{dN}'
                return ([optimized_line], True)

    # If val = 0x80 (128)
    # ori.b   #0x80,dN  ->   tas   dN          ; Saves 4 cycles. Status flags wrong
    match = re.match(r'^(\s*)(or|ori)\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantUnsigned(match.group(4))
        if val == 128:
            dN = match.group(5)
            optimized_line = f'{match.group(1)}tas{match.group(3)}{dN}'
            return ([optimized_line], True)

    # Optimizations using TAS instruction are only safe if used on regular RAM and not on memory-mapped I/O 
    # like VDP regs, YM2612 sound chip, Z80 bus, control ports. Hardware registers like (aN) is valid if 
    # pointing to RAM (not memory-mapped I/O).
    if USE_TAS_ON_MAPPED_IO_MEMORY_OPTIMIZATION:

        # bset.b  #7,mem   ->    tas   mem         ; Saves 4 cycles. Status flags wrong
        # mem must be address allowing read-modify-write transfer.
        # gcc might add +-*N[.bwl]. Ie: ammoInventory+2
        match = re.match(r'^(\s*)bset\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(#?[a-zA-Z_]\w*|-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?([\+\-\*]\d+)?(\.[bwl])?', line)
        if match:
            val = parseConstantUnsigned(match.group(3))
            if val == 7:
                mem_address = ''.join(match.group(i) for i in range(4, 8) if match.group(i))
                optimized_line = f'{match.group(1)}tas{match.group(2)}{mem_address}'
                return ([optimized_line], True)

    # bset.l  #7,dN    ->    tas   dN          ; Saves 4 cycles. Status flags wrong
    match = re.match(r'^(\s*)bset\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantUnsigned(match.group(3))
        if val == 7:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}tas{match.group(2)}{dN}'
            return ([optimized_line], True)

    # If 0 <= val <= 15
    # bset.l #val,dN   ->    or.w  #m,dN       ; Saves 4 cycles. Status flags wrong
    # m = 2^val
    match = re.match(r'^(\s*)bset\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantUnsigned(match.group(3))
        if 0 <= val <= 15:
            dN = match.group(4)
            m = 2**val
            if dM:
                optimized_line = f'{match.group(1)}ori.w{match.group(2)}#{m},{dN}'
                return ([optimized_line], True)

    # If 0 <= val <= 15
    # bclr.l #val,dN   ->    andi.w #m,dN      ; Saves 6 cycles. Status flags wrong
    # m = 65535-(2^val)
    match = re.match(r'^(\s*)bclr\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantUnsigned(match.group(3))
        if 0 <= val <= 15:
            dN = match.group(4)
            m = 65535-(2**val)
            if dM:
                optimized_line = f'{match.group(1)}andi.w{match.group(2)}#{m},{dN}'
                return ([optimized_line], True)

    # If 0 <= val <= 15
    # bchg.l #val,dN   ->    eor.w #m,dN       ; Saves 6 cycles. Status flags wrong
    # m = 65535-(2^val)
    match = re.match(r'^(\s*)bchg\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        val = parseConstantUnsigned(match.group(3))
        if 0 <= val <= 15:
            dN = match.group(4)
            m = 65535-(2**val)
            if dM:
                optimized_line = f'{match.group(1)}eor.w{match.group(2)}#{m},{dN}'
                return ([optimized_line], True)

    # move.b   #0,dN   ->    clr.b   dN        ; Saves 4 cycles
    match = re.match(r'^(\s*)move\.b(\s+)#0,\s*(%d[0-7])', line)
    if match:
        dN = match.group(3)
        optimized_line = f'{match.group(1)}clr.b{match.group(2)}{dN}'
        return ([optimized_line], True)

    # move.w   #0,dN   ->    clr.w   dN        ; Saves 4 cycles
    match = re.match(r'^(\s*)move\.w(\s+)#0,\s*(%d[0-7])', line)
    if match:
        dN = match.group(3)
        optimized_line = f'{match.group(1)}clr.w{match.group(2)}{dN}'
        return ([optimized_line], True)

    # movea.l  #0,An   ->    sub.l   An,An     ; Saves 4 cycles
    match = re.match(r'^(\s*)(movea|move)\.l(\s+)#0,\s*(%a[0-7]|%sp)', line)
    if match:
        a_reg = match.group(4)
        optimized_line = f'{match.group(1)}sub.l{match.group(3)}{a_reg},{a_reg}'
        return ([optimized_line], True)

    if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION:

        # clr.w   -(sp)     ->    subq    #2,sp     ; Saves 6 cycles
        match = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line)
        if match:
            optimized_line = f'{match.group(1)}subq{match.group(2)}#2,%sp'
            print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Next optimization may introduce unexpected behavior. Test thoroughly")
            return ([optimized_line], True)

        # clr.l   -(sp)     ->    subq    #4,sp     ; Saves 14 cycles
        match = re.match(r'^(\s*)clr\.l(\s+)-\(%sp\)', line)
        if match:
            optimized_line = f'{match.group(1)}subq{match.group(2)}#4,%sp'
            print(f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} Next optimization may introduce unexpected behavior. Test thoroughly")
            return ([optimized_line], True)
    else:

        # clr.w   -(sp)     ->    move.w  #0,-(sp)  ; Saves 2 cycles. But now time is multiple of 4. Status flags wrong.
        match = re.match(r'^(\s*)clr\.w(\s+)-\(%sp\)', line)
        if match:
            optimized_line = f'{match.group(1)}move.w{match.group(2)}#0,-(%sp)'
            return ([optimized_line], True)

        # clr.l   -(sp)     ->    pea     0.w       ; Saves 6 cycles. Status flags wrong.
        match = re.match(r'^(\s*)clr\.l(\s+)-\(%sp\)', line)
        if match:
            optimized_line = f'{match.group(1)}pea{match.group(2)}0.w'
            return ([optimized_line], True)

    # clr.l    dN      ->    moveq  #0,dN      ; Saves 2 cycles
    match = re.match(r'^(\s*)clr\.l(\s+)(%d[0-7])', line)
    if match:
        dN = match.group(3)
        optimized_line = f'{match.group(1)}moveq{match.group(2)}#0,{dN}'
        return ([optimized_line], True)

    ############################################################################
    # Add/Sub on Data register
    ############################################################################

    # add*.s  #0,dN       ->   tst.s  dN          ; Saves 0 to 16 cycles
    match = re.match(r'^(\s*)(add|addi|addq)\.([bwl])(\s+)#0,\s*(%d[0-7])', line)
    if match:
        s = match.group(3)
        dN = match.group(5)
        optimized_line = f'{match.group(1)}tst.{s}{match.group(4)}{dN}'
        return ([optimized_line], True)

    # sub*.s  #0,dN       ->   tst.s  dN          ; Saves 0 to 16 cycles
    match = re.match(r'^(\s*)(sub|subi|subq)\.([bwl])(\s+)#0,\s*(%d[0-7])', line)
    if match:
        s = match.group(3)
        dN = match.group(5)
        optimized_line = f'{match.group(1)}tst.{s}{match.group(4)}{dN}'
        return ([optimized_line], True)

    # If -32768 <= val <= 32767.
    # add*.l   #val,dN    ->   add.w   #val,dN    ; Saves 8 cycles
    match = re.match(r'^(\s*)(add|addi|addq)\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        dN = match.group(5)
        val = parseConstantSigned(match.group(4), 16)
        if is_reg_used_as_word_or_byte_afterwards(dN, i_line, lines, modified_lines):
            if 1 <= val <= 8:
                optimized_line = f'{match.group(1)}addq.w{match.group(3)}#{val},{dN}'
                return ([optimized_line], True)
            if -8 <= val <= -1:
                optimized_line = f'{match.group(1)}subq.w{match.group(3)}#{-val},{dN}'
                return ([optimized_line], True)
            if -32768 <= val <= 32767:
                optimized_line = f'{match.group(1)}addi.w{match.group(3)}#{val},{dN}'
                return ([optimized_line], True)

    # Add immediate word to dN.
    # If 1 <= val <= 8:
    # addi.w  #val,dN     ->   addq.w   #val,dN    ; Saves 4 cycles
    # If -8 <= val <= -1:
    # addi.w  #val,dN     ->   subq.w   #-val,dN   ; Saves 4 cycles
    match = re.match(r'^(\s*)(add|addi)\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        dN = match.group(5)
        val = parseConstantSigned(match.group(4), 8)
        if 1 <= val <= 8:
            optimized_line = f'{match.group(1)}addq.w{match.group(3)}#{val},{dN}'
            return ([optimized_line], True)
        if -8 <= val <= -1:
            optimized_line = f'{match.group(1)}subq.w{match.group(3)}#{-val},{dN}'
            return ([optimized_line], True)

    # If -32767 <= val <= 32767.
    # sub*.l  #val,dN     ->   sub.w   #val,dN    ; Saves 8 cycles
    match = re.match(r'^(\s*)(sub|subi|subq)\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        dN = match.group(5)
        val = parseConstantSigned(match.group(4), 16)
        if is_reg_used_as_word_or_byte_afterwards(dN, i_line, lines, modified_lines):
            if 1 <= val <= 8:
                optimized_line = f'{match.group(1)}subq.w{match.group(3)}#{val},{dN}'
                return ([optimized_line], True)
            if -8 <= val <= -1:
                optimized_line = f'{match.group(1)}addq.w{match.group(3)}#{-val},{dN}'
                return ([optimized_line], True)
            if -32767 <= val <= 32767:
                optimized_line = f'{match.group(1)}subi.w{match.group(3)}#{val},{dN}'
                return ([optimized_line], True)

    # Sub immediate word to dN.
    # If 1 <= val <= 8:
    # subi.w  #val,dN     ->   subq.w   #val,dN    ; Saves 4 cycles
    # If -8 <= val <= -1:
    # subi.w  #val,dN     ->   addq.w   #-val,dN   ; Saves 4 cycles
    match = re.match(r'^(\s*)(sub|subi)\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%d[0-7])', line)
    if match:
        dN = match.group(5)
        val = parseConstantSigned(match.group(4), 8)
        if 1 <= val <= 8:
            optimized_line = f'{match.group(1)}subq.w{match.group(3)}#{val},{dN}'
            return ([optimized_line], True)
        if -8 <= val <= -1:
            optimized_line = f'{match.group(1)}addq.w{match.group(3)}#{-val},{dN}'
            return ([optimized_line], True)

    ############################################################################
    # Add/Sub/Lea on Address register
    ############################################################################

    # TODO: create method to check if we are inside a loop and find which reg is the counter, so next condition can be removed
    if USE_ADDQL_SUBQL_BY_ADDQW_SUBQW_OPTIMIZATION:

        # addq.l  #val,aN     ->   addq.w   #val,aN    ; Saves 4 cycles
        # Only if you know before hand the upper word won't be affected, which is true for loops.
        match = re.match(r'^(\s*)addq\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%a[0-7]|%sp)', line)
        if match:
            optimized_line = f'{match.group(1)}addq.w{match.group(2)}#{match.group(3)},{match.group(4)}'
            return ([optimized_line], True)

        # subq.l  #val,aN     ->   subq.w   #val,aN    ; Saves 4 cycles
        # Only if you know before hand the upper word won't be affected, which is true for loops.
        match = re.match(r'^(\s*)subq\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%a[0-7]|%sp)', line)
        if match:
            optimized_line = f'{match.group(1)}subq.w{match.group(2)}#{match.group(3)},{match.group(4)}'
            return ([optimized_line], True)

    # If -32767 <= val <= 32767.
    # adda.l  #val,An     ->   adda.w   #val,An    ; Saves 4 cycles
    match = re.match(r'^(\s*)(adda|add)\.l(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%a[0-7]|%sp)', line)
    if match:
        aN = match.group(5)
        val = parseConstantSigned(match.group(4), 16)
        if 1 <= val <= 8:
            optimized_line = f'{match.group(1)}addq.w{match.group(3)}#{val},{aN}'
            return ([optimized_line], True)
        if -8 <= val <= -1:
            optimized_line = f'{match.group(1)}subq.w{match.group(3)}#{-val},{aN}'
            return ([optimized_line], True)
        if -32768 <= val <= 32767:
            optimized_line = f'{match.group(1)}adda.w{match.group(3)}#{val},{aN}'
            return ([optimized_line], True)

    # Add immediate word to An.
    # If when 1 <= val <= 8:
    # adda.w  #val,An     ->   addq.w   #val,An       ; Saves 4 cycles
    # If -8 <= val <= -1:
    # adda.w  #val,An     ->   subq.w   #-val,An      ; Saves 4 cycles
    # If (-32768 <= val <= -9) or (9 <= #val <= 32767):
    # adda.w  #val,An     ->   lea      val(An),An    ; Saves 4 cycles
    match = re.match(r'^(\s*)(adda|add)\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%a[0-7]|%sp)', line)
    if match:
        aN = match.group(5)
        val = parseConstantSigned(match.group(4), 16)
        if 1 <= val <= 8:
            optimized_line = f'{match.group(1)}addq.w{match.group(3)}#{val},{aN}'
            return ([optimized_line], True)
        if -8 <= val <= -1:
            optimized_line = f'{match.group(1)}subq.w{match.group(3)}#{-val},{aN}'
            return ([optimized_line], True)
        if (-32768 <= val <= -9) or (9 <= val <= 32767):
            optimized_line = f'{match.group(1)}lea{match.group(3)}{val}({aN}),{aN}'
            return ([optimized_line], True)

    # Sub immediate word to An.
    # If 1 <= val <= 8:
    # suba.w  #val,An     ->   subq.w   #val,An       ; Saves 4 cycles
    # If -8 <= val <= -1:
    # suba.w  #val,An     ->   addq.w   #-val,An      ; Saves 4 cycles
    # If (-32767 <= val <= -9) or (9 <= val <= 32767):
    # suba.w  #val,An     ->   lea      -val(An),An   ; Saves 4 cycles
    match = re.match(r'^(\s*)(suba|sub)\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(?:\.[bwl])?,\s*(%a[0-7]|%sp)', line)
    if match:
        aN = match.group(5)
        val = parseConstantSigned(match.group(4), 16)
        if 1 <= val <= 8:
            optimized_line = f'{match.group(1)}subq.w{match.group(3)}#{val},{aN}'
            return ([optimized_line], True)
        if -8 <= val <= -1:
            optimized_line = f'{match.group(1)}addq.w{match.group(3)}#{-val},{aN}'
            return ([optimized_line], True)
        if (-32767 <= val <= -9) or (9 <= val <= 32767):
            optimized_line = f'{match.group(1)}lea{match.group(3)}{-val}({aN}),{aN}'
            return ([optimized_line], True)

    # lea     (aN),aN     ->    remove line        ; Saves 4 cycles
    match = re.match(r'^\s*lea\s+\((%a[0-7]|%sp)\),\s*(%a[0-7]|%sp)', line)
    if match and match.group(1) == match.group(2):
        return ([], True)

    # lea     0(aN),aN    ->    remove line        ; Saves 4 cycles
    match = re.match(r'^\s*lea\s+0\((%a[0-7]|%sp)\),\s*(%a[0-7]|%sp)', line)
    if match and match.group(1) == match.group(2):
        return ([], True)

    # lea     (0,aN),aN   ->    remove line        ; Saves 4 cycles
    match = re.match(r'^\s*lea\s+\(0,(%a[0-7]|%sp)\),\s*(%a[0-7]|%sp)', line)
    if match and match.group(1) == match.group(2):
        return ([], True)

    # lea     0[.bwl],aN  ->    sub.l  aN,aN       ; Saves 4 cycles
    match = re.match(r'^(\s*)lea(\s+)0(\.[bwl])?,\s*(%a[0-7]|%sp)', line)
    if match:
        aN =  match.group(4)
        optimized_line = f'{match.group(1)}sub.l{match.group(2)}{aN},{aN}'
        return ([optimized_line], True)

    # lea     val[.bwl],aN   ->   movea.w  #val,aN     ; Saves 4 cycles
    # If 0 < unsigned(val) <= 65535
    match = re.match(r'^(\s*)lea(\s+)(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)(\.[bwl])?,\s*(%a[0-7]|%sp)', line)
    if match:
        aN =  match.group(5)
        val = parseConstantUnsigned(match.group(3))
        if 0 < val <= 65535:
            if match.group(4) is None or match.group(4) != '.w':
                val_str = match.group(3)
                optimized_line = f'{match.group(1)}movea.w{match.group(2)}#{val_str},{aN}'
                return ([optimized_line], True)

    # If 1 <= val <= 8
    # lea     val(aN),aN     ->   addq.w #val,aN       ; Saves 0 cycles? But instruction is 2 bytes smaller and CCR flags changed
    # If -8 <= val <= -1
    # lea     val(aN),aN     ->   subq.w #-val,aN      ; Saves 0 cycles? But instruction is 2 bytes smaller and CCR flags changed
    # Note that gcc might put the displacement like next: (val,aN)
    match1 = re.match(r'^(\s*)lea(\s+)(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+)\((%a[0-7]|%sp)\),\s*(%a[0-7]|%sp)', line)
    match2 = re.match(r'^(\s*)lea(\s+)\((-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),(%a[0-7]|%sp)\),\s*(%a[0-7]|%sp)', line)
    match = match1 or match2
    if match:
        aN = match.group(4)
        if aN == match.group(5):
            val = parseConstantSigned(match.group(3), 8)
            if 1 <= val <= 8:
                optimized_line = f'{match.group(1)}addq.w{match.group(2)}#{val},{aN}'
                return ([optimized_line], True)
            if -8 <= val <= -1:
                optimized_line = f'{match.group(1)}subq.w{match.group(2)}#{-val},{aN}'
                return ([optimized_line], True)

    ############################################################################
    # Rotates
    ############################################################################

    if IS_ROL_INSTRUCTION_REGEX.match(line) or IS_ROR_INSTRUCTION_REGEX.match(line) or IS_ROXL_INSTRUCTION_REGEX.match(line):

        # If 1 ≤ x ≤ 3
        # rol.b   #4+x,dN   ->   ror.b   #4-x,dN   ; Saves 4*x cycles
        match = re.match(r'^(\s*)rol\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line)
        if match:
            val_str = match.group(3)
            n = parseConstantUnsigned(val_str)
            x = n - 4
            if 1 <= x <= 3:
                new_x = 4 - x
                dN = match.group(4)
                optimized_line = f'{match.group(1)}ror.b{match.group(2)}#{new_x},{dN}'
                return ([optimized_line], True)

        # If 1 ≤ x ≤ 3
        # ror.b   #4+x,dN   ->   rol.b   #4-x,dN   ; Saves 4*x cycles
        match = re.match(r'^(\s*)ror\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line)
        if match:
            val_str = match.group(3)
            n = parseConstantUnsigned(val_str)
            x = n - 4
            if 1 <= x <= 3:
                new_x = 4 - x
                dN = match.group(4)
                optimized_line = f'{match.group(1)}rol.b{match.group(2)}#{new_x},{dN}'
                return ([optimized_line], True)

        # roxl.b  #1,dN     ->   addx.b  dN,dN     ; Saves 4 cycles
        match = re.match(r'^(\s*)roxl\.b(\s+)#1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_line = f'{match.group(1)}addx.b{match.group(2)}{dN},{dN}'
            return ([optimized_line], True)

        # roxl.b  #2,dN     ->   addx.b  dN,dN     ; Saves 2 cycles
        #                        addx.b  dN,dN
        match = re.match(r'^(\s*)roxl\.b(\s+)#2,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_lines = [
                f'{match.group(1)}addx.b{match.group(2)}{dN},{dN}',
                f'{match.group(1)}addx.b{match.group(2)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # roxl.w  #1,dN     ->   addx.w  dN,dN     ; Saves 4 cycles
        match = re.match(r'^(\s*)roxl\.w(\s+)#1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_line = f'{match.group(1)}addx.w{match.group(2)}{dN},{dN}'
            return ([optimized_line], True)

        # roxl.w  #2,dN     ->   addx.w  dN,dN     ; Saves 2 cycles
        #                        addx.w  dN,dN
        match = re.match(r'^(\s*)roxl\.w(\s+)#2,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_lines = [
                f'{match.group(1)}addx.w{match.group(2)}{dN},{dN}',
                f'{match.group(1)}addx.w{match.group(2)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # roxl.l  #1,dN     ->   addx.l  dN,dN     ; Saves 2 cycles
        match = re.match(r'^(\s*)roxl\.l(\s+)#1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_line = f'{match.group(1)}addx.l{match.group(2)}{dN},{dN}'
            return ([optimized_line], True)

    ############################################################################
    # Logical Shift Left and Arithmetic Shift Left
    # All lsl peephole optimizations also apply to asl
    ############################################################################

    if IS_LSL_INSTRUCTION_REGEX.match(line) or IS_ASL_INSTRUCTION_REGEX.match(line):

        # lsl.b/asl.b   #1,dN   ->   add.b   dN,dN       ; Saves 4 cycles
        match = re.match(r'^(\s*)(lsl|asl)\.b(\s+)#1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}add.b{match.group(3)}{dN},{dN}'
            return ([optimized_line], True)

        # lsl.b/asl.b   #2,dN   ->   add.b   dN,dN       ; Saves 2 cycles
        #                            add.b   dN,dN
        match = re.match(r'^(\s*)(lsl|asl)\.b(\s+)#2,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_lines = [
                f'{match.group(1)}add.b{match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.b{match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # lsl.b/asl.b   #7,dN   ->   ror.b   #1,dN       ; Saves 4 cycles
        #                            andi.b  #0x80,dN
        match = re.match(r'^(\s*)(lsl|asl)\.b(\s+)#7,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_lines = [
                f'{match.group(1)}ror.b {match.group(3)}#1,{dN}',
                f'{match.group(1)}andi.b{match.group(3)}#128,{dN}'
            ]
            return (optimized_lines, True)

        # lsl.b/asl.b   #8,dN   ->   clr.b   dN          ; Saves 18 cycles
        match = re.match(r'^(\s*)(lsl|asl)\.b(\s+)#8,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}clr.b{match.group(3)}{dN}'
            return ([optimized_line], True)

        # lsl.w/asl.w   #1,dN   ->   add.w   dN,dN       ; Saves 4 cycles
        match = re.match(r'^(\s*)(lsl|asl)\.w(\s+)#1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}add.w{match.group(3)}{dN},{dN}'
            return ([optimized_line], True)

        # lsl.w/asl.w   #2,dN   ->   add.w    dN,dN      ; Saves 2 cycles
        #                            add.w    dN,dN
        match = re.match(r'^(\s*)(lsl|asl)\.w(\s+)#2,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_lines = [
                f'{match.group(1)}add.w{match.group(3)}{dN},{dN}',
                f'{match.group(1)}add.w{match.group(3)}{dN},{dN}'
            ]
            return (optimized_lines, True)

        # lsl.w/asl.w   #8,dN   ->   move.b   dN,-(sp)   ; Saves 2 cycles
        #                            move.w   (sp)+,dN
        #                            clr.b    dN
        match = re.match(r'^(\s*)(lsl|asl)\.w(\s+)#8,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_lines = [
                f'{match.group(1)}move.b{match.group(3)}{dN},-(%sp)',
                f'{match.group(1)}move.w{match.group(3)}(%sp)+,{dN}',
                f'{match.group(1)}clr.b {match.group(3)}{dN}'
            ]
            return (optimized_lines, True)

        # lsl.l/asl.l   #1,dN   ->   add.l    dN,dN      ; Saves 4 cycles
        match = re.match(r'^(\s*)(lsl|asl)\.l(\s+)#1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}add.l{match.group(3)}{dN},{dN}'
            return ([optimized_line], True)

    ############################################################################
    # Logical Shift Right
    ############################################################################

    if IS_LSR_INSTRUCTION_REGEX.match(line):

        # lsr.b   #7,dN   ->   add.b    dN,dN      ; Saves 8 cycles
        #                      subx.b   dN,dN
        #                      neg.b    dN
        match = re.match(r'^(\s*)lsr\.b(\s+)#7,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_lines = [
                f'{match.group(1)}add.b {match.group(2)}{dN},{dN}',
                f'{match.group(1)}subx.b{match.group(2)}{dN},{dN}',
                f'{match.group(1)}neg.b {match.group(2)}{dN}'
            ]
            return (optimized_lines, True)

        # lsr.b   #8,dN   ->   clr.b    dN         ; Saves 18 cycles
        match = re.match(r'^(\s*)lsr\.b(\s+)#8,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_line = f'{match.group(1)}clr.b{match.group(2)}{dN}'
            return ([optimized_line], True)

        # lsr.w   #8,dN   ->   move.w   dN,-(sp)   ; Saves 2 cycles
        #                      clr.w    dN
        #                      move.b   (sp)+,dN
        match = re.match(r'^(\s*)lsr\.w(\s+)#8,\s*(%d[0-7])', line)
        if match:
            dN = match.group(3)
            optimized_lines = [
                f'{match.group(1)}move.w{match.group(2)}{dN},-(%sp)',
                f'{match.group(1)}clr.w {match.group(2)}{dN}',
                f'{match.group(1)}move.b{match.group(2)}(%sp)+,{dN}'
            ]
            return (optimized_lines, True)

    ############################################################################
    # Arithmetic Shift Right
    ############################################################################

    if IS_ASR_INSTRUCTION_REGEX.match(line):

        # If 0 ≤ x ≤ 1
        # asr.b   #7+x,dN  ->   add.b    dN,dN     ; Saves 12+2*x cycles
        #                       subx.b   dN,dN
        match = re.match(r'^(\s*)asr\.b(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line)
        if match:
            val_str = match.group(3)
            n = parseConstantUnsigned(val_str)
            x = n - 7
            if 0 <= x <= 1:
                dN = match.group(4)
                optimized_lines = [
                    f'{match.group(1)}add.b {match.group(2)}{dN},{dN}',
                    f'{match.group(1)}subx.b{match.group(2)}{dN},{dN}',
                ]
                return (optimized_lines, True)

        # asr.w   #8,dN    ->   move.w   dN,-(sp)  ; Saves 12+2*x cycles
        #                       move.b   (sp)+,dN
        #                       ext.w    dN
        match = re.match(r'^(\s*)asr\.w(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line)
        if match:
            val_str = match.group(3)
            n = parseConstantUnsigned(val_str)
            if n == 8:
                dN = match.group(4)
                optimized_lines = [
                    f'{match.group(1)}move.w{match.group(2)}{dN},-(%sp)',
                    f'{match.group(1)}move.b{match.group(2)}(%sp)+,{dN}',
                    f'{match.group(1)}ext.w {match.group(2)}{dN}',
                ]
                return (optimized_lines, True)

    ############################################################################
    # Multiplication by constant
    # High word of the result is important
    ############################################################################

    if OPTIMIZE_MULTIPLICATION_HIGH_WORD_IMPORTANT and IS_MUL_INSTRUCTION_REGEX.match(line):

        if IS_MULS_INSTRUCTION_REGEX.match(line):

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

        # High word of result is important
        if IS_MULU_INSTRUCTION_REGEX.match(line):

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

    ############################################################################
    # Multiplication by constant
    # High word of the result is NOT important
    ############################################################################

    if OPTIMIZE_MULTIPLICATION_HIGH_WORD_NOT_IMPORTANT and IS_MUL_INSTRUCTION_REGEX.match(line):

        if IS_MULS_INSTRUCTION_REGEX.match(line):

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

        # High word of result is NOT important
        if IS_MULU_INSTRUCTION_REGEX.match(line):

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

    ############################################################################
    # Division by constant
    # If the remainder (high word) is not needed
    ############################################################################
        
    if OPTIMIZE_DIVISION_HIGH_WORD_NOT_IMPORTANT and IS_DIV_INSTRUCTION_REGEX.match(line):

        # Signed Division by -1
        # divs[.w]  #-1,dN    ->   neg.w  dN         ; Saves [70,130]? cycles
        match = re.match(r'^(\s*)divs(\.w)?(\s+)#-1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}neg.w{match.group(3)}{dN}'
            return ([optimized_line], True)

        # Signed Division by 1
        # divs[.w]  #1,dN     ->   tst.w  dN         ; Saves [72,132]? cycles
        match = re.match(r'^(\s*)divs(\.w)?(\s+)#1,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_line = f'{match.group(1)}tst.w{match.group(3)}{dN}'
            return ([optimized_line], True)

        # Unsigned Division by 1
        # divu[.w]  #1,dN     ->   remove line       ; Saves [76,136] cycles
        match = re.match(r'^(\s*)divu(\.w)?(\s+)#1,\s*(%d[0-7])', line)
        if match:
            return ([], True)

        # Division by 12: mul by 85 and div by 1024
        # divu[.w]  #12,dN    ->   move.w  dN,dM     ; Saves [12,72]? cycles
        #                          add.w   dM,dM
        #                          add.w   dM,dM
        #                          add.w   dM,dN     ; Dn = Dn * 5
        #                          move.w  dN,dM
        #                          lsl.w   #4,dM
        #                          add.w   dM,dN     ; Dn = Dn * (5 + 5 * 16) = Dn * 85
        #                          andi.w  #~((1<<(8+x))-1),dN   ; x=2
        #                          rol.w   #8-x,dN   ; Dn = (Dn * 85) / 1024
        # Needs a free register dM
        match = re.match(r'^(\s*)divu(\.w)?(\s+)#12,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                x = 2
                mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                optimized_lines = [
                    f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                    f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                    f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                    f'{match.group(1)}add.w {match.group(3)}{dM},{dN}',
                    f'{match.group(1)}move.w{match.group(3)}{dN},{dM}',
                    f'{match.group(1)}lsl.w {match.group(3)}#4,{dM}',
                    f'{match.group(1)}add.w {match.group(3)}{dM},{dM}',
                    f'{match.group(1)}add.w {match.group(3)}#{mask},{dN}',
                    f'{match.group(1)}rol.w {match.group(3)}#8-x,{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # If 1 ≤ x ≤ 8
        # divu[.w]  #1<<x,dN  ->   lsr.l  #x,dN      ; Saves [66,126]-2*x cycles
        match = re.match(r'^(\s*)divu(\.w)?(\s+)#(\d+),\s*(%d[0-7])', line)
        if match:
            power_of_2 = [2,4,8,16,32,64,128,256]
            n = parseConstantUnsigned(match.group(4))
            if n in power_of_2:
                x = 0
                while (1 << x) < n:
                    x += 1
                if (1 << x) == n and 1 <= x <= 8:
                    dN = match.group(5)
                    optimized_line = f'{match.group(1)}lsr.l{match.group(3)}#{x},{dN}'
                    return ([optimized_line], True)

        # divu[.w]  #1<<9,dN  ->   moveq   #9,dM     ; Saves [46,106]
        #                          lsr.l   dM,dN
        # Needs a free register dM
        match = re.match(r'^(\s*)divu(\.w)?(\s+)#512,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{match.group(1)}moveq{match.group(3)}#9,{dM}',
                    f'{match.group(1)}lsr.l{match.group(3)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # divu[.w]  #1<<10,dN  ->   moveq   #10,dM   ; Saves [44,104], but needs a free register
        #                           lsr.l   dM,dN
        # Needs a free register dM
        match = re.match(r'^(\s*)divu(\.w)?(\s+)#1024,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            dM = find_free_after_use_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is None:
                dM = find_unused_data_register([dN], i_line, lines, modified_lines)[0]
            if dM is not None and add_regs_into_push_pop_if_not_scratch_or_in_interrupt([dM], i_line, lines, modified_lines):
                optimized_lines = [
                    f'{match.group(1)}moveq{match.group(3)}#9,{dM}',
                    f'{match.group(1)}lsr.l{match.group(3)}{dM},{dN}'
                ]
                return (optimized_lines, True)
            return ([], False)  # no free register -> not available optimization

        # If 3 ≤ x ≤ 7
        # divu[.w]  #1<<(8+x),dN  ->  andi.w  #~((1<<(8+x))-1),dN    ; Saves [40,90]+2*x cycles
        #                             swap    dN
        #                             rol.l   #8-x,dN
        match = re.match(r'^(\s*)divu(\.w)?(\s+)#(-?\d+|(?:0[xX]|\$)[0-9a-fA-F]+),\s*(%d[0-7])', line)
        if match:
            power_of_2 = [2048,4096,8192,16384,32768]
            n = parseConstantUnsigned(match.group(4))
            if n in power_of_2:
                x = 0
                while (1 << (8 + x)) < n:
                    x += 1
                if (1 << (8 + x)) == n and 0 <= x <= 7:  # x can be 0 for 256 (1<<8)
                    dN = match.group(5)
                    mask = ~((1<<(8+x))-1) & 0xFFFF  # Ensure 16-bit mask
                    optimized_lines = [
                        f'{match.group(1)}andi.w{match.group(3)}#{mask},{dN}',
                        f'{match.group(1)}swap  {match.group(3)}{dN}',
                        f'{match.group(1)}rol.l {match.group(3)}#{8-x},{dN}'
                    ]
                    return (optimized_lines, True)

        # divu[.w]  #1<<16,dN  ->   clr.w   dN       ; Saves [68,128] cycles
        #                           swap    dN
        match = re.match(r'^(\s*)divu(\.w)?(\s+)#65536,\s*(%d[0-7])', line)
        if match:
            dN = match.group(4)
            optimized_lines = [
                f'{match.group(1)}clr.w{match.group(3)}{dN}',
                f'{match.group(1)}swap {match.group(3)}{dN}'
            ]
            return (optimized_lines, True)

        # Optimize div by shifting to higher word
        # divs/divu[.w]  #val,dN    ->   muls/mulu  #m,dN
        #                                clr.w      dN
        #                                swap       dN
        # This comes from:
        #   floor(dN/val) = (dN * m) >> 16
        #   where m = ceil(2^16 / val)
        # It's an approximation, and is only exact when 65536/val is exact, otherwise error is [-1,1).
        match = re.match(r'^(\s*)(divs|divu)(\.w)?(\s+)#([^,]+),\s*(%d[0-7])', line)
        if match:
            mul = 'muls'
            val = parseConstantSigned(match.group(5), 16)
            val_sign = -1 if match.group(5).startswith('-') else 1
            if match.group(2) == 'divu':
                mul = 'mulu'
                val = parseConstantUnsigned(match.group(5))
            abs_val = abs(val)
            m = (65536 + abs_val - 1) // abs_val  # ceil(65536/abs_val)
            dN = match.group(6)
            optimized_lines = [
                f'{match.group(1)}{mul}.w{match.group(4)}#{val_sign*m},{dN}',
                f'{match.group(1)}clr.w {match.group(4)}{dN}',
                f'{match.group(1)}swap  {match.group(4)}{dN}'
            ]
            return (optimized_lines, True)
            
    # No optimization was applied
    return ([], False)

def optimizeSingleLine_MovemWithSingleRegister(line, i_line, lines, modified_lines):

    if OPTIMIZE_INLINE_ASM_BLOCKS:
        # If line contains the flag that mandates to skip it from be optimized -> do nothing and return
        if line.endswith(SKIP_OPTIMIZATION_FLAG):
            return ([], False)

    # movem.w *,dN     ->    move.w  *,dN        ; Saves 4 cycles
    #                        ext.l   dN
    # movem does sign extension so we need to add ext.l instruction
    match = re.match(r'^(\s*)movem\.w(\s+)([^,]+),\s*(%d[0-7]);?$', line)
    if match:
        src = match.group(3)
        dN = match.group(4)
        optimized_lines = [
            f'{match.group(1)}move.w{match.group(2)}{src},{dN}',
            f'{match.group(1)}ext.l {match.group(2)}{dN}'
        ]
        return (optimized_lines, True)

    # movem.l (sp)+,<2 regs>  ->   move.l  (sp)+,<reg1>     ; Saves 4 cycles
    #                              move.l  (sp)+,<reg2>
    match = re.match(r'^(\s*)movem\.l(\s+)\(sp\)\+,\s*(%[ad][0-7])([\-/])(%[ad][0-7]);?$', line)
    if match:
        _, _, reg1, sep, reg2, = match.groups()
        optimized_lines = [
            f'{match.group(1)}move.l{match.group(2)}(%sp)+,{reg1}',
            f'{match.group(1)}move.l{match.group(2)}(%sp)+,{reg2}'
        ]
        return (optimized_lines, True)

    # movem.s *,xN     ->    move.s  *,xN        ; Saves [4,8] cycles
    # Where xN = a single register, but not (xN=dN & s=w) at the same time
    match = re.match(r'^(\s*)movem\.([wl])(\s+)([^,]+),\s*(%[ad][0-7]|%sp);?$', line)
    if match:
        s = match.group(2)
        src = match.group(4)
        xN = match.group(5)
        if not (s == 'w' and xN.startswith("%d")):
            optimized_line = f'{match.group(1)}move.{s}{match.group(3)}{src},{xN}'
            return ([optimized_line], True)

    # movem.s xN,*     ->    move.s  xN,*        ; Saves 4 cycles. Status flags wrong
    # Where xN = a single register
    match = re.match(r'^(\s*)movem\.([wl])(\s+)(%[ad][0-7]|%sp),\s*(.+)', line)
    if match:
        s = match.group(2)
        xN = match.group(4)
        dest = match.group(5)
        optimized_line = f'{match.group(1)}move.{s}{match.group(3)}{xN},{dest}'
        return ([optimized_line], True)

    # No optimization was applied
    return ([], False)

# Adding (?![^;#\n]*[-+]) at the end which is a negative lookahead that ensures the target label is 
# not followed by any characters (except ';', '#', 'newlines') containing - or +.
shorten_branches_pattern = re.compile(
    r'^(\s*)(bcc|bcs|beq|bge|bgt|bhi|bhs|ble|blo|bls|blt|bmi|bne|bpl|bra|bsr|bvc|bvs|jsr|jcc|jcs|jeq|jge|jgt|jhi|jhs|jle|jlo|jls|jlt|jmi|jne|jpl|jra|jvc|jvs)(\.[sbw])?'
    r'(\s+)([0-9a-zA-Z_\.]+)(?![^;#\n]*[-+])'
)

def optimizeSingleLine_ShortenBranches(line, i_line, lines, modified_lines):
    """
    Optimize branch instructions by using short branch suffix ".s" if the target label is in the range of [-126,128] bytes.
    Returns a tuple of (optimized_lines, was_optimized) where:
    - optimized_lines is a list of new lines optimized lines (empty list if not).
    - was_optimized is a boolean indicating if optimization occurred.
    """

    if OPTIMIZE_INLINE_ASM_BLOCKS:
        # If line contains the flag that mandates to skip it from be optimized -> do nothing and return
        if line.endswith(SKIP_OPTIMIZATION_FLAG):
            return ([], False)

    # Use short branch suffix if the label is in the range of [-126,128] bytes.
    #    bls  label    ->    bls.s label      ; Saves 4 cycles if the branch is not taken
    #	 ...
    # label:
    #    ...
    match = shorten_branches_pattern.match(line)
    if match:
        branch_instr = match.group(2)
        branch_s = match.group(3)
        if branch_s is None or branch_s == '.w':
            label = match.group(5)
            if is_label_within_8_bytes_range(label, i_line, lines, modified_lines):
                # Replace jsr by bsr
                if branch_instr == 'jsr':
                    branch_instr = 'bsr'
                # Normalize the instruction to the M68000 set
                elif branch_instr[0] == 'j':
                    branch_instr = 'b' + branch_instr[1:]
                optimized_line = f'{match.group(1)}{branch_instr}.s{match.group(4)}{label}'
                return ([optimized_line], True)

    # No optimization was applied
    return ([], False)

def optimize_asm(lines, num_pass):
    """
    Perform multi and single line optimzations
    """

    # Keep track of total number of updated lines and patterns
    num_updated_lines_found = 0
    num_patterns_found = 0

    # Create a mapping dictionary to track original line numbers
    line_number_map = {}

    # Keep track of inline assembly blocks: #APP and #NO_APP
    inside_inline_asm_block = False
    print_start_asm_block = False
    print_end_asm_block = False

    # Phase 1: Optimze multiple lines first
    print(f'[OPT_LOG] Multi line patterns')

    modified_multi_lines = []
    for i_line in range(0, len(lines)):
        line = lines[i_line]

        # Remove leading whitespaces for next checks. Trailing whitespaces were removed in an earlier stage
        stripped = line.lstrip()

        # Track inline assembly blocks
        if stripped.startswith("#APP"):
            inside_inline_asm_block = True
            if OPTIMIZE_INLINE_ASM_BLOCKS:
                print_start_asm_block = True
                print_end_asm_block = False
        elif stripped.startswith("#NO_APP"):
            if OPTIMIZE_INLINE_ASM_BLOCKS and inside_inline_asm_block:
                if print_end_asm_block:
                    print(f'[OPT_LOG] <-- End inline asm block')
            print_start_asm_block = False
            print_end_asm_block = False
            inside_inline_asm_block = False

        # Skip empty lines and comments and alike
        if not stripped or (stripped and stripped[0] in COMMENT_PREFIX_CHAR):
            # '#APP' and '#NO_APP' are the only one comments starting with '#' added by gcc to discern 
            # between inline asm blocks added by the user
            if not stripped.startswith(('#APP','#NO_APP')):
                # Continue with next line
                continue

        # Add the original line first
        modified_multi_lines.append(line)
        # Map the position in modified_multi_lines to original line number
        line_number_map[len(modified_multi_lines) - 1] = i_line

        # Check for compiler info and directive entries first
        if containsCompilerInfo(line) or containsCompilerDirective(line):
            # line was already added previously, so we can safely skip it from any processing
            continue

        # Skip inline assembly blocks?
        if not OPTIMIZE_INLINE_ASM_BLOCKS and inside_inline_asm_block:
            # line was already added previously, so we can safely skip it from any processing
            continue

        # Check for multi-line optimizations over the recently added lines.
        # Min lenght required to start analyzing multiple lines. 
        # Otherwise minor optimizations might be applied first causing a miss of opportunities for broader optimizations.
        if len(modified_multi_lines) >= MULTIPLE_LINES_OPTIMIZATION_LIMIT:

            # Range: from MULTIPLE_LINES_OPTIMIZATION_MAX_LIMIT lines down to 2 lines
            for multi_span_size in range(MULTIPLE_LINES_OPTIMIZATION_LIMIT, 2 - 1, -1):

                # Find optimizations spanning multiple lines
                optimized_multilines, lines_to_remove = optimizeMultipleLines(multi_span_size, i_line, lines, modified_multi_lines)

                if optimized_multilines is not None:
                    # Update counter
                    num_updated_lines_found += lines_to_remove
                    num_patterns_found += 1

                    # Get the lines being replaced
                    original_lines = modified_multi_lines[-lines_to_remove:] if lines_to_remove <= len(modified_multi_lines) else []
                    
                    # Calculate original line number for the first line being optimized
                    first_modified_line_pos = len(modified_multi_lines) - lines_to_remove
                    original_line_num = line_number_map.get(first_modified_line_pos, first_modified_line_pos)
                    
                    # Remove the lines we're replacing from modified_multi_lines
                    for _ in range(lines_to_remove):
                        if modified_multi_lines:
                            modified_multi_lines.pop()
                    modified_multi_lines.extend(optimized_multilines)
                    # Update the line number mapping for the new lines
                    for i, _ in enumerate(optimized_multilines):
                        line_number_map[len(modified_multi_lines) - len(optimized_multilines) + i] = original_line_num

                    # Print findings?
                    if PRINT_OPTIMIZATION_LOG:
                        # Print starting or ending an inline asm block
                        if print_start_asm_block:
                            print(f'[OPT_LOG] --> Start inline asm block')
                            print_start_asm_block = False
                            print_end_asm_block = True
                        # Print optimization log
                        print_optimized_diff(original_lines, i_line-(lines_to_remove-1), optimized_multilines)

    # NOTE: At this point we know that modified_multi_lines lines have not trealing whitespace

    def process_single_lines_helper(input_lines, optimization_func, phase_name):        
        
        # Keep track of inline assembly blocks: #APP and #NO_APP
        inside_inline_asm_block = False
        print_start_asm_block = False
        print_end_asm_block = False

        modified_lines = []
        num_updates = 0  # Counts how many single patterns were applied, which is the same than single lines updated

        print(f'[OPT_LOG] {phase_name}')

        for i_line, line in enumerate(input_lines):
            # Track inline assembly blocks
            if line.startswith("#APP"):
                inside_inline_asm_block = True
                if OPTIMIZE_INLINE_ASM_BLOCKS:
                    print_start_asm_block = True
                    print_end_asm_block = False
                modified_lines.append(line)
                continue
            elif line.startswith("#NO_APP"):
                if OPTIMIZE_INLINE_ASM_BLOCKS and inside_inline_asm_block:
                    if print_end_asm_block:
                        print(f'[OPT_LOG] <-- End inline asm block')
                print_start_asm_block = False
                print_end_asm_block = False
                inside_inline_asm_block = False
                modified_lines.append(line)
                continue

            # Check for compiler info or directive entries first
            if containsCompilerInfo(line) or containsCompilerDirective(line):
                modified_lines.append(line)
                continue

            # Skip inline assembly blocks?
            if not OPTIMIZE_INLINE_ASM_BLOCKS and inside_inline_asm_block:
                modified_lines.append(line)
                continue

            # Find single line optimizations
            optimized_lines, was_optimized = optimization_func(line, i_line, input_lines, modified_lines)

            if was_optimized:
                # Update counter
                num_updates += 1
                # Print findings?
                if PRINT_OPTIMIZATION_LOG:
                    # Get the original line number from the map
                    original_line_num = line_number_map.get(i_line, i_line)
                    # Print starting or ending an inline asm block
                    if print_start_asm_block:
                        print(f'[OPT_LOG] --> Start inline asm block')
                        print_start_asm_block = False
                        print_end_asm_block = True
                    # Print optimization log
                    print_optimized_diff([line], original_line_num, optimized_lines)
                # Save the optimized lines
                modified_lines.extend(optimized_lines)
            else:
                # Not optimized -> add the original line
                modified_lines.append(line)

        return modified_lines, num_updates

    # Phase 2: Single line patterns
    modified_single_lines_phase_2, num_updates_2 = process_single_lines_helper(
        modified_multi_lines, 
        optimizeSingleLine_Peepholes, 
        "Single line patterns (common peepholes)"
    )
    num_updated_lines_found += num_updates_2
    num_patterns_found += num_updates_2

    # Phase 3: Movem on one single register (only on second pass)
    modified_single_lines_phase_3, num_updates_3 = process_single_lines_helper(
        modified_single_lines_phase_2, 
        optimizeSingleLine_MovemWithSingleRegister, 
        "Single line patterns (movem on one single register)"
    )
    num_updated_lines_found += num_updates_3
    num_patterns_found += num_updates_3

    # Phase 4: Shorten branch instructions
    # Only if running 2nd pass
    modified_single_lines_phase_4 = modified_single_lines_phase_3
    if num_pass == 2:
        modified_single_lines_phase_4, num_updates_4 = process_single_lines_helper(
            modified_single_lines_phase_3, 
            optimizeSingleLine_ShortenBranches, 
            "Single line patterns (shorten branch instructions)"
        )
        num_updated_lines_found += num_updates_4
        num_patterns_found += num_updates_4

    return (modified_single_lines_phase_4, num_updated_lines_found, num_patterns_found)

# Reg expr to match the pattern %pc@(disp,%xN:s)
gcc_indirection_style_pattern = re.compile(r'%pc@\((-?\d+),%([ad])([0-7]):([bwl])\)')

def convert_from_gcc_indirection_style(line):
    """
    Convert operand from %pc@(disp,%xN:s) format to disp(%pc,%xN.s) format
    """
    return gcc_indirection_style_pattern.sub(lambda m: f"{m.group(1)}(%pc,%{m.group(2)}{m.group(3)}.{m.group(4)})", line)

# Reg expr to match any of: (aN/sp/pc,%dN.l) or disp(aN/sp/pc,%dN.l) or (disp,aN/sp/pc,%dN.l)
gcc_indirection_with_long_dn_access_pattern = re.compile(
    r'(?:'
    r'(?:\((%a[0-7]|%sp|%pc),(%d[0-7])\.l\))'  # (aN/sp/pc,%dN.l)
    r'|'
    r'(?:([0-9a-zA-Z_\.]+|-?\d+(?:[\-\+\*]\d+)?)\((%a[0-7]|%sp|%pc),(%d[0-7])\.l\))'  # label_or_disp[+-*N](aN/sp/pc,%dN.l)
    r'|'
    r'(?:\(([0-9a-zA-Z_\.]+|-?\d+(?:[\-\+\*]\d+)?),(%a[0-7]|%sp|%pc),(%d[0-7])\.l\))'  # (label_or_disp[+-*N],aN/sp/pc,%dN.l)
    r')'
)

def replace_gcc_dn_long_indirection_by_word(line):
    """
    Replaces dN.l by dN.w in patterns: (aN/sp/pc,%dN.l) or disp(aN/sp/pc,%dN.l) or (disp,aN/sp/pc,%dN.l)
    """
    if not USE_AGGRESSIVE_REPLACE_LONG_INDIRECT_ADDRESSING_BY_WORD:
        # TODO: in some cases when replacing dN.l by dN.w glitches appear in Blastem
        return line

    def replace_match(match):
        if match.group(1) and match.group(2):
            return f'({match.group(1)},{match.group(2)}.w)'
        elif match.group(3) and match.group(4) and match.group(5):
            return f'{match.group(3)}({match.group(4)},{match.group(5)}.w)'
        elif match.group(6) and match.group(7) and match.group(8):
            return f'({match.group(6)},{match.group(7)},{match.group(8)}.w)'
        # Fallback: return original
        return match.group(0)
    
    return gcc_indirection_with_long_dn_access_pattern.sub(replace_match, line)

def convert_from_gcc_fp_style(line):
    """
    Convert operand from %fp to %a6
    """
    return line.replace('%fp', '%a6')

def convert_gcc_movem_encoded_regs(line):
    """
    Gcc writes the list of registers in an encoded format. This method replace it by a human readable format.
    """
    match_push = PUSH_REGS_INTO_STACK_REGEX.match(line)
    match_pop = POP_REGS_FROM_STACK_REGEX.match(line)
    if match := match_push or match_pop:
        if match.group(1) == 'movem':
            regs_str = match.group(3)
            regs_list = extract_registers(regs_str, PUSH_OP) if match_push else extract_registers(regs_str, POP_OP)
            sortedRegs = sort_regs(regs_list)
            # Rebuild register list using '/' as separator
            # Reverse the list of regs if is a push match
            newRegs_str = '/'.join(sortedRegs[::-1] if match_push else sortedRegs)
            return line.replace(regs_str, newRegs_str)

    return line

symbolName_or_imm_dereference_pattern = re.compile(
    r'\('                            # Matches '('
    r'(?!%[ad][0-7]|%sp|%pc)'        # Negative lookahead: avoid dN, aN, sp, pc
    r'([0-9a-zA-Z_\.]+(?:\.[wl])?)'  # symbolName[.wl]
    r'\)'                            # Matches ')'
)

def remove_gcc_dereference_symbolName_or_immediate(line):
    """
    Remove chars '(' and ')' containing a symbolName or an immediate value.
    """
    return symbolName_or_imm_dereference_pattern.sub(r'\1', line)

def applyGccConversions(lines):
    """
    Convert some gcc idioms, indirections, dereferences, and regs encodings for easy reading.
    """
    modified_lines = []
    for i_line in range(0, len(lines)):
        line = lines[i_line]
        # Rewrite the line without any trailing whitespace. The content of lines will be used in other methods
        line = line.rstrip()

        # Skip empty lines and comments and alike
        stripped = line.lstrip()
        if not stripped or (stripped and stripped[0] in COMMENT_PREFIX_CHAR):
            # '#APP' and '#NO_APP' are the only one comments starting with '#' added by gcc to discern 
            # between inline asm blocks added by the user
            if not stripped.startswith(('#APP','#NO_APP')):
                # Continue with next line
                continue

        # Replace gcc indirection style on certain instructions
        line = convert_from_gcc_indirection_style(line)
        # Replace %fp by %a6
        line = convert_from_gcc_fp_style(line)
        # Replace dN.l by dN.w in indirection accesses
        line = replace_gcc_dn_long_indirection_by_word(line)
        # Replace gcc encoded list of regs by a human readable format
        line = convert_gcc_movem_encoded_regs(line)
        # Remove dereference over symbol names, like: lea (PAL_setPalette.constprop.0),%a3
        line = remove_gcc_dereference_symbolName_or_immediate(line)

        modified_lines.append(line)

    return modified_lines

# move.l symbolName[.wl],aN
# move.l #symbolName[.wl],aN
move_symbolName_into_an_pattern = re.compile(
    r'^\s*move\.l\s+'
    r'#?([0-9a-zA-Z_\.]+)(\.[wl])?'
    r',\s*(%a[0-7]);?$'
)
# lea symbolName[.wl],aN
lea_symbolName_into_an_pattern = re.compile(
    r'^\s*lea\s+'
    r'([0-9a-zA-Z_\.]+)(\.[wl])?'
    r',\s*(%a[0-7]);?$'
)

def search_backwards_for_lea_or_move_symbolName_into_aN(aN, lines, i_start, i_end):
    # Search backwards for lea [(]symbolName[)],aN or move.l [#(]symbolName[)],aN and assign symbolName to func_name
    for k in range(i_start, i_end - 1, -1):
        prev_line = lines[k]
        # Break conditions
        if FUNCTION_DECLARATION_REGEX.match(prev_line):
            break
        # Is moving a symbolName name into aN?
        if match := move_symbolName_into_an_pattern.match(prev_line) or lea_symbolName_into_an_pattern.match(prev_line):
            if aN == match.group(3):
                return match.group(1)
    return ''

move_into_SGDK_table_vector_pattern = re.compile(
    r'^\s*move\.[wl]\s+'
    r'#([0-9a-zA-Z_\.]+)(\.[wl])?'
    r',\s*(vintCB|hintCaller|eintCB|intCB|vblankCB|busErrorCB|addressErrorCB|illegalInstCB|zeroDivideCB|chkInstCB|trapvInstCB|privilegeViolationCB|traceCB|line1x1xCB|errorExceptionCB)(\.[wl])?([\-\+\*]\d+)?(\.[bwl])?;?$'
)

global_routine_pattern = re.compile(
    r'^\s*'
    r'\.globl\s+'          # .globl followed by at least one whitespace
    r'('                   # Start capturing group for function name
    r'[a-zA-Z_]'           # First character must be a letter or underscore
    r'[0-9a-zA-Z_\.]+'     # Anything left
    r')'
)

def non_used_functions(lines):

    # Phase 1:
    # Get all the routines declared by FUNCTION_DECLARATION_REGEX
    declared_functions_set = set()
    for i_line in range(0, len(lines)):
        line = lines[i_line]
        # Is a function declaration?
        if match := FUNCTION_DECLARATION_REGEX.match(line):
            declared_functions_set.add(match.group(1))

    # Phase 2:
    # Get all the routines declared as global that are also declared functions
    global_functions_set = set()
    for i_line in range(0, len(lines)):
        line = lines[i_line]
        # Is a function declaration?
        if match := global_routine_pattern.match(line):
            func_name = match.group(1)
            if func_name in declared_functions_set:
                global_functions_set.add(func_name)

    # Phase 3:
    # For each call to a function save it into a set of called functions so we can later know which
    # declared functions are not being called.
    calling_functions_set = set()
    for i in range(0, len(lines)):
        line = lines[i]

        # Is calling one of the declared functions?
        if uncond_match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            func_name = uncond_match.group(3)
            # Consider cases like jsr (%a5)
            if func_name.startswith('%a'):
                aN = func_name
                func_name = search_backwards_for_lea_or_move_symbolName_into_aN(aN, lines, i-1, 0)
            if func_name in declared_functions_set:
                calling_functions_set.add(func_name)
        # Check if a function is moved into a SGDK table vector
        elif match := move_into_SGDK_table_vector_pattern.match(line):
            func_name = match.group(1)
            if func_name in declared_functions_set:
                calling_functions_set.add(func_name)

    # Phase 4:
    # Remove the called functions and global functions from the declared functions.
    # If the result is not empty then we can remove the code of those declared functions
    unused_funcs = declared_functions_set - calling_functions_set  # set_a - set_b = Elements in set_a but not in set_b
    unused_funcs = unused_funcs - global_functions_set
    print('[OPT_LOG] Non used functions:', sorted(unused_funcs))
    
    # TODO: replace non used functions lines by empty line

add_sub_sp_pattern = re.compile(
    r'^\s*(add|sub)\S*\s+#(\d+|0[xX][0-9a-fA-F]+),\s*%sp;?$'
)

move_into_disp_sp_pattern = re.compile(
    r'^(\s*)(move|movea)\.([wl])(\s+)'  # move.[w/l] or movea.[w/l]
    r'(?:'                              # Non-capturing group
    r'(%[ad][0-7])'                     # xN
    r'|'
    r'(-?\(%a[0-7]\)\+?)'               # (aN) or -(aN) or (aN)+
    r'|'
    r'(#?-?\d+|#?0[xX][0-9a-fA-F]+|#?[0-9a-zA-Z_\.]+)(\.[bwl])?([\-\+\*]\d+)?(\.[bwl])?'  # #val or #symbolName or symbolName, with [.bwl][+-*N][.bwl]
    r')'                                # End non-capturing group
    r',\s*(-?\d+)?\(%sp\)'              # disp(sp)
)

move_disp_sp_into_xn_pattern = re.compile(
    r'^(\s*)(move|movea)\.([wl])(\s+)'  # move.[w/l] or movea.[w/l]
    r'(-?\d+)?\(%sp\)'                  # disp(sp)
    r',\s*(?:.+);?$'
)

@dataclass
class ABIFunctionData:
    args: []
    total_sp_adjustment: int

def remove_simple_abi(lines):
    """
    When possible, remove ABI in callers and callees:
    - Avoid pushing args into stack before calling the function.
    - Avoid popping args from stack when on function prologue and keep using the args the caller used before calling the function.
    - Avoid saving args into stack now that they are not trashed but directly used from the caller context.
    - Avoid restoring args from stack.
    """

    # How many lines to re trace to search for arguments
    previous_N_lines_for_args = 12

    # Phase 1:
    # Get all the routines declared by FUNCTION_DECLARATION_REGEX
    declared_functions_set = set()
    for i_line in range(0, len(lines)):  # forwards
        line = lines[i_line]
        # Is a function declaration?
        if match := FUNCTION_DECLARATION_REGEX.match(line):
            declared_functions_set.add(match.group(1))

    # Phase 2:
    # For each call to a function we create a list of the arguments (reg or memory or symbol) being pushed into 
    # the stack, including total size. Every time we found that a function is already in the map we must ensure 
    # they match with those in the existing list (in name, type, and order). Otherwise it means different calls 
    # actually don't use same sources as arguments.
    args_pushed_per_function = {}
    for i in range(0, len(lines)):  # forwards
        line = lines[i]

        # Is calling one of the declared functions?
        if uncond_match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            func_name = uncond_match.group(3)
            # Consider cases like jsr (%a5)
            if func_name.startswith('%a'):
                aN = func_name
                func_name = search_backwards_for_lea_or_move_symbolName_into_aN(aN, lines, i-1, 0)
            if func_name in declared_functions_set:
                # Collect the arguments being pushed into the stack along with the total sp adjustment.
                # Visit up to N previous lines going backwards.
                args = []
                total_sp_adjustment = 0
                for k in range(i-1, max(0, i - previous_N_lines_for_args) - 1, -1):  # backwards
                    prev_line = lines[k]
                    # Break conditions
                    if FUNCTION_DECLARATION_REGEX.match(prev_line) or FUNCTION_EXIT_REGEX.match(prev_line) or CONDITIONAL_CONTROL_FLOW_REGEX.match(prev_line) or UNCONDITIONAL_CONTROL_FLOW_REGEX.match(prev_line):
                        break
                    # Consider only single register push with move, not movem
                    if push_match := PUSH_REGS_INTO_STACK_REGEX.match(prev_line):
                        if push_match.group(1) == 'move':
                            arg = push_match.group(3)
                            arg_size = push_match.group(2)
                            if arg_size == 'w':
                                total_sp_adjustment += 2
                            elif arg_size == 'l':
                                total_sp_adjustment += 4
                            args.append(f'{arg}.{arg_size}')
                    # Consider pea <value|symbolName>[.wl][+-*N][.bwl]
                    elif pea_match := PEA_REGEX.match(prev_line):
                        groups = pea_match.groups()
                        # Skip the first .s after the argument (if any)
                        arg = ''.join(groups[i] for i in [0, 2, 3] if groups[i])
                        arg_size = 'l' if pea_match.group(2) is None else pea_match.group(2)[1:]  # remove initial '.'
                        if arg_size == 'w':
                            total_sp_adjustment += 2
                        elif arg_size == 'l':
                            total_sp_adjustment += 4
                        args.append(f'{arg}.{arg_size}')
                    # Consider pushing a symbol or an immediate value
                    elif push_other_match := PUSH_OTHER_INTO_STACK_REGEX.match(prev_line):
                        groups = push_other_match.groups()
                        # Skip the first .s after the argument (if any)
                        arg = ''.join(groups[i] for i in [1, 3, 4] if groups[i])
                        arg_size = push_match.group(1)
                        if arg_size == 'w':
                            total_sp_adjustment += 2
                        elif arg_size == 'l':
                            total_sp_adjustment += 4
                        args.append(f'{arg}.{arg_size}')

                # Reverse the list so the arguments are in the order they are popped from stack in the target function
                #args[::-1]
                # Get existing arguments (if the they were saved in an earlier function call)
                func_called = args_pushed_per_function.get(func_name)
                if func_called is None:
                    args_pushed_per_function[func_name] = ABIFunctionData(args, total_sp_adjustment)
                else:
                    # If not exact match then remove func_name from declared_functions_set, and the entry in the dictionary too
                    if not (args == func_called):
                        declared_functions_set.discard(func_name)
                        del args_pushed_per_function[func_name]

    # Remove functions without pushed arguments (empty list in the 'args' field)
    args_pushed_per_function = {k: v for k, v in args_pushed_per_function.items() if len(v.args) > 0}

    # TODO: remove this after testing
    for key, value in args_pushed_per_function.items():
        print(f'{key} => total_sp_adjustment: {value.total_sp_adjustment} bytes, args: {value.args}')
    return lines

    # Phase 3: for those functions in args_pushed_per_function map:
    # - when calling to a function: remove the push into sp instructions and adjust the subsequent uses of sp.
    # - when at the function declaration: replace the pop from stack by the assigment of the argument, or
    #   remove it if the poping reg is the same than the argument reg. Apply adjustments over subsequent uses of sp.
    modified_lines_no_abi = []
    i = 0
    rem_end = len(lines)
    while i < rem_end:  # forwards
        line = lines[i]
        i += 1
        modified_lines_no_abi.append(line)

        # Is calling one of the collected functions?
        if uncond_match := UNCONDITIONAL_CONTROL_FLOW_REGEX.match(line):
            func_name = uncond_match.group(3)
            # Consider cases like jsr (%a5)
            if func_name.startswith('%a'):
                aN = func_name
                func_name = search_backwards_for_lea_or_move_symbolName_into_aN(aN, modified_lines_no_abi, i-1, 0)
            if func_name in args_pushed_per_function:
                # Go backwards until we reach the end of arguments range
                line_end_of_args_range = (i-1) - 1
                for k in range((i-1) - 1, max(0, (i-1) - previous_N_lines_for_args) - 1, -1):  # backwards
                    prev_line = modified_lines_no_abi[k]
                    if FUNCTION_DECLARATION_REGEX.match(prev_line) or FUNCTION_EXIT_REGEX.match(prev_line) or CONDITIONAL_CONTROL_FLOW_REGEX.match(prev_line) or UNCONDITIONAL_CONTROL_FLOW_REGEX.match(prev_line):
                        line_end_of_args_range = k + 1
                # Remove the push into sp instructions while going forward up to the call of the function
                accum_sp_adjustment = 0
                for k in range(line_end_of_args_range, i):  # forwards
                    next_line = modified_lines_no_abi[k]
                    # Consider only single register push with move, not movem
                    if push_match := PUSH_REGS_INTO_STACK_REGEX.match(next_line):
                        if push_match.group(1) == 'move':
                            arg_size = push_match.group(2)
                            if arg_size == 'w':
                                accum_sp_adjustment += 2
                            elif arg_size == 'l':
                                accum_sp_adjustment += 4
                            modified_lines_no_abi[k] = ''  # This way we keep the original line numbering for following analysis
                    # Consider pea <value|symbolName>[.wl][+-*N][.bwl]
                    elif pea_match := PEA_REGEX.match(next_line):
                        arg_size = 'l' if pea_match.group(2) is None else pea_match.group(2)[1:]  # remove initial '.'
                        if arg_size == 'w':
                            accum_sp_adjustment += 2
                        elif arg_size == 'l':
                            accum_sp_adjustment += 4
                        modified_lines_no_abi[k] = ''  # This way we keep the original line numbering for following analysis
                    # Consider pushing a symbol or an immediate value
                    elif push_other_match := PUSH_OTHER_INTO_STACK_REGEX.match(next_line):
                        arg_size = push_match.group(1)
                        if arg_size == 'w':
                            accum_sp_adjustment += 2
                        elif arg_size == 'l':
                            accum_sp_adjustment += 4
                        modified_lines_no_abi[k] = ''  # This way we keep the original line numbering for following analysis
                    # Adjust uses of sp between the arguments we have removed
                    elif accum_sp_adjustment > 0:
                        # add*/sub* over sp
                        if match := add_sub_sp_pattern.match(next_line):
                            val = parseConstantUnsigned(match.group(2))
                            # Add the adjustment in order to compensate the removal of -(sp) instruction/s
                            val += accum_sp_adjustment
                            modified_lines_no_abi[k] = next_line.replace(match.group(2), val, 1)
                        # load xN into disp(sp)
                        elif match := move_into_disp_sp_pattern.match(next_line):
                            val = 0
                            if match.group(11):
                                val = parseConstantSigned(match.group(11), 16)
                            # Add the adjustment in order to compensate the removal of -(sp) instruction/s
                            val += accum_sp_adjustment
                            val_str = '' if val == 0 else str(val)
                            src = ''.join(match.group(i) for i in range(5, 11) if match.group(i))
                            r = f'{match.group(1)}{match.group(2)}.{match.group(3)}{match.group(4)}{src},{val_str}(%sp)'
                            modified_lines_no_abi[k] = r
                        # load disp(sp) into xN
                        elif match := move_disp_sp_into_xn_pattern.match(next_line):
                            val = 0
                            if match.group(5):
                                val = parseConstantSigned(match.group(5), 16)
                            # Add the adjustment in order to compensate the removal of -(sp) instruction/s
                            val += accum_sp_adjustment
                            val_str = '' if val == 0 else str(val)
                            r = f'{match.group(1)}{match.group(2)}.{match.group(3)}{match.group(4)}{val_str}(%sp),{match.group(6)}'
                            modified_lines_no_abi[k] = r

                if accum_sp_adjustment > 0:
                    # Adjust the subsequent uses of sp
                    # TODO: see TODO.txt
                    pass

        # Is one of our collected functions?
        elif match := FUNCTION_DECLARATION_REGEX.match(line):
            func_name = match.group(1)
            if func_name in args_pushed_per_function:
                args = args_pushed_per_function[func_name].args
                total_sp_adjustment = args_pushed_per_function[func_name].total_sp_adjustment
                # Replace the pop from stack by the assigment of the argument, 
                # or remove it if the poping reg is the same than the argument reg
                # TODO: see raycasting asm routine DMA_doDmaFast.constprop.0

    return modified_lines_no_abi


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python optimize_lst.py <file.ext> <file.opt.ext>")
        sys.exit(1)

    input_filename = sys.argv[1]
    print(f'[OPT_LOG] Optimizing {input_filename}')

    with open(input_filename, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()

    # Convert some gcc idioms, indirections, dereferences, and regs encodings for easy reading
    modified_lines = applyGccConversions(lines)

    # Print non used functions
    non_used_functions(modified_lines)

    # Remove ABI when possible
    #print(f'[OPT_LOG] Simple ABI removal pass:')
    #modified_lines = remove_simple_abi(modified_lines)

    # 1st pass
    print(f'[OPT_LOG] FIRST pass:')
    modified_lines, num_updated_lines_found, num_patterns_found = optimize_asm(modified_lines, 1)

    # 2nd pass: catch new opportunities and optimize branches
    print(f'[OPT_LOG] SECOND pass: (opt line numbers will point to result from first pass and not to original lines):')
    modified_lines, num_updated_lines_found_2nd_pass, num_patterns_found_2nd_pass = optimize_asm(modified_lines, 2)
    num_updated_lines_found += num_updated_lines_found_2nd_pass
    num_patterns_found += num_patterns_found_2nd_pass

    patterns_label = "pattern" if num_patterns_found == 1 else "patterns"
    if not SAVE_OPTIMIZATIONS:
        candidates_label = "candidate" if num_patterns_found == 1 else "candidates"
        print(f'[OPT_LOG] TOTAL: {num_patterns_found} {patterns_label}')
    else:
        print(f'[OPT_LOG] TOTAL: {num_patterns_found} {patterns_label}')

    lines_label = "line" if num_updated_lines_found == 1 else "lines"
    if not SAVE_OPTIMIZATIONS:
        candidates_label = "candidate" if num_updated_lines_found == 1 else "candidates"
        print(f'[OPT_LOG] TOTAL: {num_updated_lines_found} {lines_label} found as {candidates_label}')
    else:
        print(f'[OPT_LOG] TOTAL: {num_updated_lines_found} {lines_label} were updated')

    if not SAVE_OPTIMIZATIONS:
        print('[OPT_LOG] CHANGES NOT PERSISTED, as per SAVE_OPTIMIZATIONS = False')
        with open(input_filename, 'r', encoding='utf-8') as infile:
            modified_lines = infile.readlines()
        
    output_filename = sys.argv[2]
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        for line in modified_lines:
            outfile.write(line + '\n')
