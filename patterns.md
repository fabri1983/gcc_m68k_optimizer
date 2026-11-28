## Index

| Function | Documented patterns |
|---|---|
| [`reduce_canonical_address_using_sign_extension`](#reduce_canonical_address_using_sign_extension) | 10 |
| [`optimizeSingleLine_ShortenBranches`](#optimizesingleline_shortenbranches) | 1 |
| [`optimizeSingleLine_MovemWithSingleRegister`](#optimizesingleline_movemwithsingleregister) | 4 |
| [`optimizeSingleLine_Peepholes`](#optimizesingleline_peepholes) | 101 |
| [`optimizeMultiLines_SymbolOrMemByOffset`](#optimizemultilines_symbolormembyoffset) | 1 |
| [`optimizeMultiLines_2`](#optimizemultilines_2) | 150 |
| [`optimizeMultiLines_3`](#optimizemultilines_3) | 37 |
| [`optimizeMultiLines_4`](#optimizemultilines_4) | 41 |
| [`optimizeMultiLines_5`](#optimizemultilines_5) | 23 |
| [`optimizeMultiLines_6`](#optimizemultilines_6) | 16 |
| [`optimizeMultiLines_7`](#optimizemultilines_7) | 9 |
| [`optimizeMultiLines_8`](#optimizemultilines_8) | 5 |
| [`muls_high_word_important`](#muls_high_word_important) | 35 |
| [`mulu_high_word_important`](#mulu_high_word_important) | 26 |
| [`muls_high_word_not_important`](#muls_high_word_not_important) | 46 |
| [`mulu_high_word_not_important`](#mulu_high_word_not_important) | 48 |
| **Total** | **553** |

---

## `reduce_canonical_address_using_sign_extension`

```text
We can take advantage of the sign extension nature of lea/movea/jmp/jsr instructions over the high word of 
the canonical address to reduce its size:
- If higher word is 0x0000 (SGDK's ROM start) and lower word <= 0x7fff (SGDK_LOW_ROM_END) -> 
	we can use .w and let the sign extension fills the higher word with 0s.
- If higher word is 0xE0FF (SGDK's RAM start) and lower word >= 0x8000 (high half RAM) ->
	we can use .w and let the sign extension fills the higher word with 1s, given that the m68k cpu only cares the first 24 bits.
	NOTE: when dealing with memory values, not symbols, on higher RAM the optimization fails unless SGDK_HIGH_RAM_START is 0xFFFF8000.
Currently:
	SGDK_LOW_ROM_END    = 0x00007FFF
	SGDK_HIGH_RAM_START = 0xE0FF8000
```

```asm
move.s  #symbolName,aN    ->   move.s  #symbol_or_mem.w,aN      ; Saves 4 cycles
clr.s   symbolName        ->   clr.s   symbol_or_mem.w          ; Saves 4 cycles
```

```asm
move.s  #mem_address,aN   ->   move.s  #mem_address.w,aN        ; Saves 4 cycles
clr.s   mem_address       ->   clr.s   mem_address.w            ; Saves 4 cycles
```

```asm
lea     symbolName,aN     ->   lea     symbol_or_mem.w,aN       ; Saves 4 cycles
pea     symbolName        ->   pea     symbol_or_mem.w          ; Saves 4 cycles
```

```asm
lea     mem_address,aN    ->   lea     mem_address.w,aN         ; Saves 4 cycles
pea     mem_address       ->   pea     mem_address.w            ; Saves 4 cycles
```

```asm
add*/sub*.s   symbolName,aN   ->   add*/sub*.s   symbol_or_mem.w,aN     ; Saves 4 cycles
Only for add/adda/addq and sub/suba/subq
cmp*.s   symbolName,<ea>      ->   cmp*.s   symbol_or_mem.w,<ea>        ; Saves 4 cycles
Only for cmp/cmpa
```

```asm
add*/sub*.s   mem_address,aN   ->   add*/sub*.s   mem_address.w,aN      ; Saves 4 cycles
Only for add/adda/addq and sub/suba/subq
cmp*.s   mem_address,<ea>      ->   cmp*.s   symbol_or_mem.w,<ea>       ; Saves 4 cycles
Only for cmp/cmpa
```

```asm
cmpi.s   #value,symbolName   ->   cmpi.s   symbol_or_mem.w,aN      ; Saves 4 cycles
andi.s   #value,symbolName   ->   andi.s   symbol_or_mem.w,aN      ; Saves 4 cycles
```

```asm
cmpi.s   #value,mem_address   ->   cmpi.s   mem_address.w,aN       ; Saves 4 cycles
andi.s   #value,mem_address   ->   andi.s   mem_address.w,aN       ; Saves 4 cycles
```

```asm
jmp     symbolName     ->   jmp     symbolName.w               ; Saves 2 cycles
jsr     symbolName     ->   jsr     symbolName.w               ; Saves 2 cycles
```

```asm
jmp     mem_address    ->   jmp     mem_address.w              ; Saves 2 cycles
jsr     mem_address    ->   jsr     mem_address.w              ; Saves 2 cycles
```


## `optimizeSingleLine_ShortenBranches`

```text
Optimize branch instructions by using short branch suffix ".s" if the target label is in the range of [-126,128] bytes.
Returns a tuple of (optimized_lines, was_optimized) where:
- optimized_lines is a list of new lines optimized lines (empty list if not).
- was_optimized is a boolean indicating if optimization occurred.
```

```asm
Use short branch suffix if the label is in the range of [-127,128] bytes.
   bCC[.w]  label    ->    bCC.s label      ; Saves 4 cycles if the branch is not taken.
	 ...
label:
   ...
```


## `optimizeSingleLine_MovemWithSingleRegister`

```asm
movem.w *,dN     ->    move.w  *,dN        ; Saves 4 cycles.
                       ext.l   dN
movem does sign extension so we need to add ext.l instruction.
```

```asm
movem.l (sp)+,<2 regs>  ->   move.l  (sp)+,<reg1>     ; Saves 4 cycles.
                             move.l  (sp)+,<reg2>
```

```asm
movem.s *,xN     ->    move.s  *,xN        ; Saves [4,8] cycles.
Where xN = a single register, but not (xN=dN & s=w) at the same time.
```

```asm
movem.s xN,*     ->    move.s  xN,*        ; Saves 4 cycles. Status flags wrong.
Where xN = a single register.
```


## `optimizeSingleLine_Peepholes`

```text
Optimize a single line of assembly code.
Returns a tuple of (optimized_lines, was_optimized) where:
- optimized_lines: is a list of new lines optimized lines (empty list if not).
- was_optimized: is a boolean indicating if optimization occurred.
```

```asm
Where 0 < val <= 0xFFFF (65535)
or.l   #val,dN    ->    or.w   #val,dN         ; Saves 8 cycles.
or
eor.l  #val,dN    ->    eor.w  #val,dN         ; Saves 8 cycles.
```

```asm
Where val = 2^b (only 1 bit set and is at position b)
or.s   #val,dN    ->    bset.[bwl]  #b,dN      ; Saves [4,12] cycles.
```

```asm
If val = 0x80 (128)
or.b    #0x80,dN   ->   tas   dN          ; Saves 4 cycles. Status flags wrong.
```

```asm
eor.s  #-1,<ea>   ->    not.s   <ea>           ; Saves 4 cycles.
Consider 0xFF, 0xFFFF, and 0xFFFFFFFF as equivalences to -1.
```

```asm
Where -128 <= val <= 127.
or.l   #val,<ea>   ->   moveq  #val,dM         ; Saves 4 cycles.
                        or.l   dM,<ea>
or
eor.l  #val,<ea>   ->   moveq  #val,dM         ; Saves 4 cycles.
                        eor.l  dM,<ea>
Needs a free data register dM.
```

```asm
Remove 0 indirection
<any_instr>  *0(aN)*     ->    <any_instr>  *(aN)*     ; Saves 4 cycles.
```

```asm
cmp.s  #0,dN     ->    tst.s    dN        ; Saves [4,10] cycles.
```

```asm
If 1 <= abs(val) <= 8
cmp.s  #val,dN   ->    subq/addq.s   #abs(val),dN      ; Saves [4,6] cycles. Leaves dN different.
                       (subq if val > 0, addq if val < 0)
Ensure dN is not used anymore or cleared/overwritten before use.
```

```asm
cmp.[wl]  #0,aN     ->    move.s   aN,dM        ; Saves [6,10] cycles.
Needs a free data register dM.
```

```asm
If -128 <= val <= 127
cmp.l  #val,<ea>   ->    moveq    #val,dM       ; Saves 4 cycles.
                         cmp.l    dM,<ea>
Needs a free data register dM.
```

```asm
If 1 <= abs(val) <= 8
cmp.s  #val,aN   ->    subq/addq.s   #abs(val),aN      ; Saves [4,6] cycles. Leaves aN different.
                       (subq if val > 0, addq if val < 0)
Only if aN is not used anymore until is overwritten or cleared.
```

```asm
Move 0 to dN.
move.l  #0,dN    ->   moveq    #0,dN         ; Saves 8 cycles.
```

```asm
Move -128 <= val <= 127
move.l  #val,dN  ->   moveq    #val,dN       ; Saves 8 cycles.
```

```asm
Move -136 ... -129 values.
move.l  #val,dN  ->   moveq    #-128,dN      ; Saves 0 cycles, but it's 2 bytes smaller.
                      subq.l   #val+128,dN
```

```asm
Move 128 ... 255 values.
move.l  #val,dN  ->   moveq    #255-val,dN   ; Saves 4 cycles.
                      not.b    dN
```

```asm
Move (128 <= val <= 254) or (-256 <= val <= -130) where n is even
move.l  #val,dN  ->   moveq    #val/2,dN     ; Saves 4 cycles.
                      add.b    dN,dN
```

```asm
Move 65534 <= val <= 65408 or -65409 <= val <= -65536 values.
move.l  #val,dN  ->   moveq    #65535-abs(val),dN      ; Saves 4 cycles.
                      not.w    dN
```

```asm
Move -8323073 <= val <= -65537 or 65536 <= val <= 8323072
If val = m*65536. Ie val is multiple of 65536.
move.l  #val,dN  ->   moveq    #m,dN         ; Saves 4 cycles.
                      swap     dN
```

```asm
Move $FF81 ... $FFFF values and $FFFF0001 ... $FFFF0080 values.
      -127 ... -1                  -65535 ... -65408
MOVE.L #x,Dn   -> optimized as:
  - MOVEQ for 16-bit values where $FF81 <= x <= $FFFF (Saves 8 cycles)
  and
  - MOVEQ+NEG.W for 32-bit values where $FFFF0001 <= x <= $FFFF0080 (Saves 4 cycles)
Explanation:
  - 16-bit values:  moveq #x,Dn   (with x=$81...$FF, sign extended becomes $FFFFFF81...$FFFFFFFF)
  and
  - 32-bit values:  moveq #-x,Dn  (with x=$01...$80, then -x=$FF...$80, sign extended becomes $FFFFFFFF...$FFFFFF80)
                    neg.w Dn      (leaves $0001..$0080 in lower word only)
```

```asm
Move $00010000 ... $007F0000 values. But keeping always low 0000.
         65536 ... 8323072
Move a constant value $N0000 (where $0001 <= N <= $007F) to a data register.
                                        1 <= N <= 127
The moveq instruction sign extends the last bit.
move.l  #$N0000,Dn   ->   moveq    #N,Dn     ; Saves 4 cycles.
                          swap     Dn
```

```asm
Move $FF80FFFF ... $FFFEFFFF values. But keeping always low FFFF.
      -8323073 ... -65537
Move a constant value $NFFFF (where $FF80 <= N <= $FFFF) to a data register.
                                     -128 <= N <= -2
The moveq instruction sign extends the last bit.
move.l  #$NFFFF,Dn   ->   moveq    #N,Dn     ; Saves 4 cycles.
                          swap     Dn
```

```asm
Move a specific signed 16bit value.
move.l  #val,dN  ->    moveq   #m,dN         ; Saves 0 cycles, but it's 2 bytes smaller.
                       bchg.l  dN,dN
```

```asm
move.b   #-1,dN     ->   st.b    dN          ; Saves 4 cycles.
```

```asm
Move long val to aN when -32767 <= val <= 32767, but val != 0.
move.l   #val,aN    ->   movea.w   #val,aN   ; Saves 4 cycles.
```

```asm
Push constant val into sp.
If -32767 <= val <= 32767, ie: val = 0x0000NNNN
move.l   #val,-(sp)   ->   pea   val.w       ; Saves 4 cycles.
```

```asm
Push memory address into sp.
move.l   #symbol_or_mem,-(sp)   ->   pea   symbol_or_mem   ; Saves 8 cycles.
Examples for symbol_or_mem: #-520158600[.bwl][+-N], #0xE0FF8002[.bwl][+-N], #symbolName[.bwl][+-N]
```

```asm
If -128 <= val <= 127
move.l  #val,<ea>   ->    moveq    #val,dM       ; Saves 4 cycles.
                          move.l   dM,<ea>
Needs a free data register dM.
Only if NOT in the last pass: if val == 0 and <ea> is a register then skip it so we can leave the moveq #0,dM for other patterns.
```

```asm
Clearing memory using existent xN already holding 0 value.
clr.s   -(aN)      ->    move.s  xN,-(aN)        ; Saves [6,10] cycles.
```

```asm
Clearing memory using existent xN already holding 0 value.
clr.s   (aN)+      ->    move.s  xN,(aN)+        ; Saves [4,8] cycles.
```

```asm
Clearing memory using existent xN already holding 0 value.
clr.s   disp(aN)   ->    move.s  xN,disp(aN)     ; Saves [4,8] cycles.
disp is optional.
```

```asm
Clearing memory using existent xN already holding 0 value.
clr.s   disp(aN,xM.[wl])   ->    move.s  xN,disp(aN,xM.[wl])       ; Saves [4,8] cycles.
disp is optional.
```

```asm
Keep lower byte with mask 0xFF (255).
and.l   #255,dN      ->     moveq   #0,dM      ; Saves 4 cycles.
                            move.b  dN,dM
                            move.l  dM,dN
Needs a free data register dM.
```

```asm
Clear upper word with mask 0xFFFF (65535).
and.l   #65535,dN    ->     swap   dN          ; Saves 4 cycles.
                            clr.w  dN
                            swap   dN
```

```asm
Clear lower word with mask 0xFFFF0000 (-65536)
and.l   #-65536,dN   ->     clr.w  dN          ; Saves 12 cycles
```

```asm
If -128 <= val <= 127
and.l  #val,<ea>   ->    moveq    #val,dM      ; Saves 4 cycles.
                         and.l    dM,<ea>
Needs a free data register dM.
```

```asm
Masking bits where in reality it clears one bit.
and.[bwl]  #val,dN   ->   bclr.[bl]  #b,dN         ; Saves [2,4,12] cycles.
Where not(val) = 2^b (only 1 bit set and is at position b).
bclr bit position is 0 based.
```

```asm
bset[.bl]  #7,symbol_or_mem     ->    tas   symbol_or_mem         ; Saves 4 cycles. Status flags wrong.
symbol_or_mem must be address allowing read-modify-write transfer.
Gcc might add [+-N][.bwl]. Ie: ammoInventory+2
```

```asm
bset[.bl]  #7,dN     ->    tas   dN          ; Saves 8 cycles. Status flags wrong.
```

```asm
If 0 <= val <= 15
bset[.bl]  #val,dN   ->    or.w  #m,dN       ; Saves 4 cycles. Status flags wrong.
m = 2^val
```

```asm
If 0 <= val <= 15
bclr[.bl]  #val,dN   ->    andi.w #m,dN      ; Saves 6 cycles. Status flags wrong.
m = 65535-(2^val)
```

```asm
If 0 <= val <= 15
bchg[.bl]  #val,dN   ->    eor.w #m,dN       ; Saves 6 cycles. Status flags wrong.
m = 65535-(2^val)
```

```asm
move.b   #0,dN   ->    clr.b   dN         ; Saves 4 cycles.
```

```asm
move.w   #0,dN   ->    clr.w   dN         ; Saves 4 cycles.
```

```asm
move.l  #0,aN    ->    sub.l   aN,aN      ; Saves 4 cycles.
```

```asm
clr.w   -(sp)     ->    subq.l  #2,sp     ; Saves [4,6] cycles.
Also considers: move.w #0,-(sp)
Only if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
clr.l   -(sp)     ->    subq.l  #4,sp     ; Saves [8,14] cycles.
Also considers: pea  0[.wl]
Only if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
clr.w   -(sp)     ->    move.w  #0,-(sp)    ; Saves 2 cycles. But now time is multiple of 4. Status flags wrong.
```

```asm
clr.l   -(sp)     ->    pea  0.w            ; Saves 6 cycles. Status flags wrong.
```

```asm
clr.l  dN      ->    moveq  #0,dN      ; Saves 2 cycles. But now time is multiple of 4.
```

```asm
add*.s  #0,dN       ->   tst.s  dN          ; Saves [0,4,12] cycles.
```

```asm
sub*.s  #0,dN       ->   tst.s  dN          ; Saves [0,4,12] cycles.
```

```asm
If -32768 <= val <= 32767.
add*.l   #val,dN    ->   add*/sub*.[wl]   #val,dN       ; Saves [8,12] cycles.
```

```asm
If -128 <= val <= 127.
add*.l   #val,dN    ->   moveq     #val,dM       ; Saves [4,8] cycles.
                         add.[wl]  dM,dN
Needs a free data register dM.
```

```asm
Add immediate word to dN.
If 1 <= val <= 8:
addi.w  #val,dN     ->   addq.w   #val,dN    ; Saves 4 cycles.
If -8 <= val <= -1:
addi.w  #val,dN     ->   subq.w   #-val,dN   ; Saves 4 cycles.
```

```asm
If -32767 <= val <= 32767.
sub*.l  #val,dN     ->   sub*/add*.[wl]   #val,dN    ; Saves [8,12] cycles.
```

```asm
If -128 <= val <= 127.
sub*.l   #val,dN    ->   moveq     #val,dM    ; Saves [4,8] cycles.
                         sub.[wl]  dM,dN
Needs a free data register dM.
```

```asm
Sub immediate word to dN.
If 1 <= val <= 8:
subi.w  #val,dN     ->   subq.w   #val,dN    ; Saves 4 cycles.
If -8 <= val <= -1:
subi.w  #val,dN     ->   addq.w   #-val,dN   ; Saves 4 cycles.
```

```asm
addq.l  #val,aN     ->   addq.w   #val,aN    ; Saves 4 cycles.
Only if you know before hand the upper word won't be affected, which is true for loops.
Only if USE_REPLACE_ADDQL_SUBQL_BY_ADDQW_SUBQW_OPTIMIZATION is on.
```

```asm
subq.l  #val,aN     ->   subq.w   #val,aN    ; Saves 4 cycles.
Only if you know before hand the upper word won't be affected, which is true for loops.
Only if USE_REPLACE_ADDQL_SUBQL_BY_ADDQW_SUBQW_OPTIMIZATION is on.
```

```asm
If -32768 <= val <= 32767.
adda.l  #val,An     ->   adda.w   #val,An       ; Saves [4,8] cycles.
Take advantage of sign extension of the source. The final operation over An is always long.
```

```asm
If -128 <= val <= 127.
adda.l   #val,aN    ->   moveq     #val,dM      ; Saves 4 cycles.
                         adda.l    dM,aN
Needs a free data register dM.
```

```asm
Add immediate word to An.
If when 1 <= val <= 8:
adda.w  #val,An     ->   addq.w   #val,An       ; Saves 4 cycles.
If -8 <= val <= -1:
adda.w  #val,An     ->   subq.w   #-val,An      ; Saves 4 cycles.
If (-32768 <= val <= -9) or (9 <= #val <= 32767):
adda.w  #val,An     ->   lea      val(An),An    ; Saves 4 cycles.
```

```asm
If -32768 <= val <= 32767.
suba.l  #val,An     ->   suba.w   #val,An       ; Saves [4,8] cycles.
Take advantage of sign extension of the source. The final operation over An is always long.
```

```asm
If -128 <= val <= 127.
suba.l   #val,aN    ->   moveq     #val,dM      ; Saves 4 cycles.
                         suba.l    dM,aN
Needs a free data register dM.
```

```asm
Sub immediate word to An.
If 1 <= val <= 8:
suba.w  #val,An     ->   subq.w   #val,An       ; Saves 4 cycles.
If -8 <= val <= -1:
suba.w  #val,An     ->   addq.w   #-val,An      ; Saves 4 cycles.
If (-32767 <= val <= -9) or (9 <= val <= 32767):
suba.w  #val,An     ->   lea      -val(An),An   ; Saves 4 cycles.
```

```asm
lea     (aN),aN     ->    remove line        ; Saves 4 cycles.
```

```asm
lea     0(aN),aN    ->    remove line        ; Saves 4 cycles.
```

```asm
lea     (0,aN),aN   ->    remove line        ; Saves 4 cycles.
```

```asm
lea     0[.bwl],aN  ->    sub.l  aN,aN       ; Saves 4 cycles.
```

```asm
lea     val[.bwl],aN   ->   movea.w  #val,aN     ; Saves 4 cycles.
If 0 < unsigned(val) <= 65535.
```

```asm
If 1 <= val <= 8
lea     val(aN),aN     ->   addq.w #val,aN       ; Saves 0 cycles. Instruction is 2 bytes smaller.
If -8 <= val <= -1
lea     val(aN),aN     ->   subq.w #-val,aN      ; Saves 0 cycles. Instruction is 2 bytes smaller.
```

```asm
If 1 <= x <= 3
rol.b   #4+x,dN   ->   ror.b   #4-x,dN   ; Saves 4*x cycles. Wrong flags
```

```asm
If 1 <= x <= 3
ror.b   #4+x,dN   ->   rol.b   #4-x,dN   ; Saves 4*x cycles. Wrong flags
```

```asm
roxl.b  #1,dN     ->   addx.b  dN,dN     ; Saves 4 cycles. Wrong flags
```

```asm
roxl.b  #2,dN     ->   addx.b  dN,dN     ; Saves 2 cycles. Wrong flags
                       addx.b  dN,dN
```

```asm
roxl.w  #1,dN     ->   addx.w  dN,dN     ; Saves 4 cycles. Wrong flags
```

```asm
roxl.w  #2,dN     ->   addx.w  dN,dN     ; Saves 2 cycles. Wrong flags
                       addx.w  dN,dN
```

```asm
roxl.l  #1,dN     ->   addx.l  dN,dN     ; Saves 2 cycles. Wrong flags
```

```asm
lsl.b/asl.b   #1,dN   ->   add.b   dN,dN       ; Saves 4 cycles
```

```asm
lsl.b/asl.b   #2,dN   ->   add.b   dN,dN       ; Saves 2 cycles
                           add.b   dN,dN
```

```asm
lsl.b/asl.b   #7,dN   ->   ror.b   #1,dN       ; Saves 4 cycles. Wrong flags
                           andi.b  #0x80,dN
```

```asm
lsl.b/asl.b   #8,dN   ->   clr.b   dN          ; Saves 18 cycles. Wrong flags
```

```asm
lsl.w/asl.w   #1,dN   ->   add.w   dN,dN       ; Saves 4 cycles
```

```asm
lsl.w/asl.w   #2,dN   ->   add.w    dN,dN      ; Saves 2 cycles
                           add.w    dN,dN
```

```asm
lsl.w/asl.w   #8,dN   ->   move.b   dN,-(sp)   ; Saves 2 cycles. Wrong flags
                           move.w   (sp)+,dN
                           clr.b    dN
```

```asm
lsl.l/asl.l   #1,dN   ->   add.l    dN,dN      ; Saves 4 cycles
```

```asm
lsr.b   #7,dN   ->   add.b    dN,dN      ; Saves 8 cycles. Wrong flags
                     subx.b   dN,dN
                     neg.b    dN
```

```asm
lsr.b   #8,dN   ->   clr.b    dN         ; Saves 18 cycles. Wrong flags
```

```asm
lsr.w   #8,dN   ->   move.w   dN,-(sp)   ; Saves 2 cycles. Wrong flags
                     clr.w    dN
                     move.b   (sp)+,dN
```

```asm
If 0 <= x <= 1
asr.b   #7+x,dN  ->   add.b    dN,dN     ; Saves 12+2*x cycles. Wrong flags
                      subx.b   dN,dN
```

```asm
asr.w   #8,dN    ->   move.w   dN,-(sp)  ; Saves 12+2*x cycles. Wrong flags
                      move.b   (sp)+,dN
                      ext.w    dN
```

```asm
Signed Division by -1
divs[.w]  #-1,dN    ->   neg.w  dN         ; Saves [70,130]? cycles.
```

```asm
Signed Division by 1
divs[.w]  #1,dN     ->   tst.w  dN         ; Saves [72,132]? cycles.
```

```asm
Unsigned Division by 1
divu[.w]  #1,dN     ->   remove line       ; Saves [76,136] cycles.
```

```asm
Division by 12: mul by 85 and div by 1024
divu[.w]  #12,dN    ->   move.w  dN,dM     ; Saves [12,72]? cycles.
                         add.w   dM,dM
                         add.w   dM,dM
                         add.w   dM,dN     ; Dn = Dn * 5
                         move.w  dN,dM
                         lsl.w   #4,dM
                         add.w   dM,dN     ; Dn = Dn * (5 + 5 * 16) = Dn * 85
                         andi.w  #~((1<<(8+x))-1),dN   ; x=2
                         rol.w   #8-x,dN   ; Dn = (Dn * 85) / 1024
Needs a free data register dM.
```

```asm
If 1 <= x <= 8
divu[.w]  #1<<x,dN  ->   lsr.l  #x,dN      ; Saves [66,126]-2*x cycles.
```

```asm
divu[.w]  #1<<9,dN  ->   moveq   #9,dM     ; Saves [46,106], but needs a free register.
                         lsr.l   dM,dN
Needs a free data register dM.
```

```asm
divu[.w]  #1<<10,dN  ->   moveq   #10,dM   ; Saves [44,104], but needs a free register.
                          lsr.l   dM,dN
Needs a free data register dM.
```

```asm
If 3 <= x <= 7
divu[.w]  #1<<(8+x),dN  ->  andi.w  #~((1<<(8+x))-1),dN    ; Saves [40,90]+2*x cycles.
                            swap    dN
                            rol.l   #8-x,dN
```

```asm
divu[.w]  #1<<16,dN  ->   clr.w   dN       ; Saves [68,128] cycles.
                          swap    dN
```

```asm
Optimize div by shifting to higher word.
divs/divu[.w]  #val,dN    ->   muls/mulu  #m,dN
                               clr.w      dN
                               swap       dN
This comes from:
  floor(dN/val) = (dN * m) >> 16
  where m = ceil(2^16 / val)
It's an approximation, and is only exact when 65536/val is exact, otherwise error is [-1,1).
```


## `optimizeMultiLines_SymbolOrMemByOffset`

```text
Iterates over increasing batches of multiple lines and try to exploit the offset between symbols loaded into aN.
```

```asm
Loading a symbol or mem by an offset of a previous loaded symbol or mem
lea  symbol_or_mem_1,aN    ->    lea  symbol_or_mem_1,aN             ; Saves [4,8] cycles
... N instructions ...           ... N instructions ...
lea  symbol_or_mem_2,aM          lea  symbol_or_mem_2-symbol_or_mem_1(aN),aM
Where aN can be aM.
The lea instr can be:  move.[wl] #symbol_or_mem,aN
Only if -32768 <= (symbol_or_mem_1 - symbol_or_mem_2) <= 32767.
Only if N inner instructions do not branch, nor function exit, nor overriding aN.
```


## `optimizeMultiLines_2`

```asm
Sign extension on long word unnecessary if then it's save as word.
This pattern is the outcome of GCC optimization for ASR.l #16,dN which adds EXT.l dN
ext.l   dN       ->    move.w  dN,<ea>      ; Saves 4 cycles
move.w  dN,<ea>
Ensure dN is not used anymore before is cleared or overwritten, or used as word or byte before is overwritten or cleared.
```

```asm
Unnecessary sign extension if dN is then used as word or byte.
Particularly added by FF32_toInt() which does >> 16, but gcc also adds an extra ext.l.
swap[.w]  dN     ->    swap   dN            ; Saves 4 cycles
ext.l     dN
Ensure dN is used as word or byte afterwards before is overwritten or cleared.
```

```asm
Fast sign-extend bytes into words, and words into longs, when the sign bit is at position N.
lsl.w/l  #val,dN     ->   move.w/l  #mask,dM     ; Saves ?? cycles as long as N decreases.
asr.w/l  #val,dN          add.w/l   dM,dN
                          eor.w/l   dM,dN
Where val=16-N for bytes, val=32-N for words. mask=-(2^(N-1)).
Needs a free data register dM.
```

```asm
Clear register except lower byte and then shift left val positions, where 1 <= val <= 8.
and.l  #255,dN    ->    and.l  #255,dN           ; Saves 2 cycles
lsl.l  #val,dN          lsl.w  #val,dN
```

```asm
Test bit #7 (8th position) on byte size.
btst[.bl]  #7,<ea>    ->    tst.b   <ea>        ; Saves 4 cycles. Status flags wrong.
beq        label            bpl     label
Not valid for: dN, d16(PC), d8(PC,Xn.s) dest address modes.
<ea>: effective address valid for this tst optimization:
  dN   (aN)   (aN)+   -(aN)   d(aN)   d(aN,xN.s)   ABS.w   ABS.l
Note that gcc might put a symbol name instead of ABS.w or ABS.l: symbolName or #symbolName
```

```asm
Test bit #7 (8th position) on byte size.
btst[.bl]  #7,<ea>    ->    tst.b   <ea>        ; Saves 4 cycles. Status flags wrong.
bne        label            bmi     label
Not valid for: dN, d16(PC), d8(PC,Xn.s) dest address modes.
<ea>: effective address valid for this tst optimization:
  dN   (aN)   (aN)+   -(aN)   d(aN)   d(aN,xN.s)   ABS.w   ABS.l
Note that gcc might put a symbol name instead of ABS.w or ABS.l: symbolName or #symbolName
```

```asm
Test bit #7,15,31 (8th, 16th, 31th position) on long size.
If val in [7, 15, 31]
btst[.bl]  #val,dN    ->    tst.s   dN          ; Saves 4 cycles. Status flags wrong.
beq        label            bpl     label
s = b|w|l for 7|15|31
```

```asm
Test bit #7,15,31 (8th, 16th, 31th position) on long size.
If val in [7, 15, 31]
btst[.bl]  #val,dN    ->    tst.s   dN          ; Saves 4 cycles. Status flags wrong.
bne        label            bmi     label
s = b|w|l for 7|15|31
```

```asm
bset[.bl]  #7,symbol_or_mem   ->   tas  symbol_or_mem      ; Saves 4 cycles. Status flags wrong.
beq        label                   bpl  label
symbol_or_mem must be address allowing read-modify-write transfer.
gcc might add +N or -N. Ie: ammoInventory+2.
```

```asm
bset[.bl]  #7,symbol_or_mem   ->   tas  symbol_or_mem      ; Saves 4 cycles. Status flags wrong.
bne        label                   bmi  label
symbol_or_mem must be address allowing read-modify-write transfer.
gcc might add +-N. Ie: ammoInventory+2.
```

```asm
Use tas instruction to set bit 7th.
bset[.bl]  #7,dN     ->    tas   dN          ; Saves 4 cycles. Status flags wrong.
beq        label           bpl   label
```

```asm
Use tas instruction to set bit 7th.
bset[.bl]  #7,dN     ->    tas   dN          ; Saves 4 cycles. Status flags wrong.
bne        label           bmi   label
```

```asm
tst.s  dN        ->    dbf    dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
bne    label
```

```asm
tst.s  dN        ->    dbne   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
beq    label
```

```asm
tst.s  dN        ->    dbmi   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
bpl    label
```

```asm
tst.s  dN        ->    dbpl   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
bmi    label
```

```asm
tst.s  dN        ->    dbmi   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
bge    label
```

```asm
tst.s  dN        ->    dbpl   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
blt    label
```

```asm
tst.s  dN        ->    dbeq   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
bhi    label
```

```asm
tst.s  dN        ->    dbne   dN,label    ; Saves [2,4] cycles. Leaves dN with different value than expected. Wrong flags.
bls    label
```

```asm
Tail recursion. Replace BSR+RTS by BRA
bsr subr         ->    bra   subr         ; Saves 24 cycles. Different stack depth.
rts
```

```asm
Tail recursion. Replace JSR+RTS by JMP
jsr subr         ->    jmp   subr         ; Saves 24 cycles. Different stack depth.
rts
```

```asm
lea     subr,aN    ->   jsr  subr            ; Saves 8 cycles. Leaves aN unused.
jsr     (aN)
Optimization pays off only up to 3 replacements. More than 3 is better to keep using jsr (aN).
```

```asm
move.l  #subr,aN   ->   jsr  subr            ; Saves 8 cycles. Leaves aN unused.
jsr     (aN)
Optimization pays off only up to 3 replacements. More than 3 is better to keep using jsr (aN).
```

```asm
move.l  disp(aN),aM   ->   jmp  disp(aN)     ; Saves 14 cycles. Leaves aM unused.
jmp     (aM)
aN can be pc.
```

```asm
move.l  disp(aN,dN.s),aM   ->   jmp  disp(aN,dN.s)    ; Saves 12 cycles. Leaves aM unused.
jmp     (aM)
aN can be pc.
```

```asm
lea     label_or_val(aN),aM   ->   jmp  label_or_val(aN)    ; Saves 6 cycles. Leaves aM unused.
jmp     (aM)
aN can be pc.
```

```asm
lea     label_or_val(aN,dN.s),aM   ->   jmp  label_or_val(aN,dN.s)    ; Saves 6 cycles. Leaves aM unused.
jmp     (aM)
```

```asm
Apply a mask where -128 <= mask <= 127
move.s   <ea>,dN    ->    moveq   #mask,dN           ; Saves 4 cycles. Top bits of dN different.
and.s    #mask,dN         and.s   <ea>,dN
<ea>: effective address valid for AND instruction:
  dN   (aN)   (aN)+   -(aN)   d(aN)   d(aN,xN.s)   ABS.w   ABS.l   d(PC)   d(PC,xN.s)   imm
Where s in xN.s is: b,w,l
Note that gcc might put a symbol name instead of ABS.w or ABS.l: symbolName or #symbolName
```

```asm
Word packing. Setting upper word only.
If val = m*65536. Ie val is multiple of 65536.
Where -8323073 <= val <= -65537 or 65536 <= val <= 8323072.
and.l  #0xFFFF,dN       ->    swap    dN             ; Saves 16 cycles.
or.l   #0xNNNN0000,dN         move.w  #m,dN
                              swap    dN
```

```asm
move.l  aN,sp      ->    unlk    aN       ; Saves 4 cycles.
move.l  (sp)+,aN
```

```asm
Push aN into sp and then add/sub constant into sp.
move.[wl]  aN,-(sp)   ->    pea   val(aN)            ; Saves [4,8] cycles.
add*.[wl]  #val,(sp)
```

```asm
Push aN into sp and then add/sub constant into sp.
move.[wl]  aN,-(sp)   ->    pea   -val(aN)           ; Saves [4,8] cycles.
sub*.[wl]  #val,(sp)
```

```asm
Increment by 1 byte after reading 1 byte from memory.
move.b   (aN),xN      ->    move.b   (aN)+,xN        ; Saves 8 cycles.
add*     #1,aN
Here aN can't be sp because it doesn't support increment by 1 byte.
```

```asm
Decrement by 1 byte before reading 1 byte from memory.
sub*     #1,aN        ->    move.b   -(aN),xN        ; Saves 6 cycles.
move.b   (aN),xN
Here aN can't be sp because it doesn't support increment by 1 byte.
```

```asm
Increment by 2 bytes after reading 1 word from memory.
move.w   (aN),xN      ->    move.w   (aN)+,xN        ; Saves 8 cycles.
add*     #2,aN
```

```asm
Decrement by 2 bytes before reading 1 word from memory.
sub*     #2,aN        ->    move.w   -(aN),xN        ; Saves 6 cycles.
move.w   (aN),xN
```

```asm
Increment by 4 bytes after reading 1 long from memory.
move.l   (aN),xN      ->    move.l   (aN)+,xN        ; Saves 8 cycles.
add*     #4,aN
```

```asm
Decrement by 4 bytes before reading 1 long from memory.
sub*     #4,aN        ->    move.l   -(aN),xN        ; Saves 6 cycles.
move.l   (aN),xN
```

```asm
Calculates offset indexes for accessing arrays.
lea     symbol_or_mem,aN    ->   move.l  *,aN                      ; Saves [6,8] cycles.
add.l   *,aN                     lea     symbol_or_mem(aN),aN
```

```asm
Load a memory value with an offset into a data register.
lea     symbol_or_mem,aN       ->   lea     symbol_or_mem,aN       ; Saves 4 cycles.
move.s  symbol_or_mem[+-]N,dN       move.s  N(aN),dN
```

```asm
Use of unnecessary additional register.
lea        disp(aN),aM    ->    move.[wl]       aN,dN              ; Saves [4,8] cycles. Leaves aM free.
move.[wl]  aM,dN                addq/subq.[wl]  #abs(disp),dN
                                (addq if val > 0, subq if val < 0)
Where 1 <= abs(disp) <= 8.
Leaves aM free.
Ensure aM is not used anymore or cleared/overwritten before use.
```

```asm
This pattern comes up after applying optimization for lsl.w #8,dN.
clr.b   dN            ->   move.b  dM,dN             ; Saves 4 cycles.
move.b  dM,dN
```

```asm
Redundant load of immediate word value into an address register that is not used anymore.
move.w     #imm,aN    ->    add/sub.l   #imm,dN      ; Saves 4 cycles. Leaves aN different.
add/sub.l  aN,dN
Leaves aN different.
Ensure aN is not used anymore or cleared/overwritten before use.
```

```asm
Move xN into dM and then add/sub a constant into dM.
If -128 <= val <= 127
move.[wl]       xN,dM      ->    moveq         #val,dM        ; Saves 8 cycles.
add*/sub*.[wl]  #val,dM          add/sub.[wl]  xN,dM
```

```asm
Calculating effective address between address registers and a constant.
If -32767 <= val <= 32767
move.[wl]  aN,aM      ->    lea   val(aN),aM         ; Saves [8,12] cycles.
add.[wl]   #val,aM
```

```asm
Calculating effective address between address registers and a constant.
If -32768 <= val <= 32767
move.[wl]  aN,aM      ->    lea   -val(aN),aM        ; Saves [8,12] cycles.
sub.[wl]   #val,aM
```

```asm
Reduce addition and move into memory with only one move instruction.
add.[wl]   xN,aN     ->    move.[wl] (aN,xN.w),aM    ; Saves 2 cycles.
move.[wl]  (aN),aM
aM can be aN.
```

```asm
Calculating effective address involving a value and registers xN and aN.
If -32768 <= val <= 32767
move.[wl]  #val,aN   ->    move.[wl]  xN,aN          ; Saves 4 cycles.
add.[wl]   xN,aN           lea        val(aN),aN
```

```asm
Twice addition of same data reg as equivalence of multiplication by 4.
add.l   dN,dN     ->    lsl.l  #2,dN       ; Saves 4 cycles. Wrong overflow V flag if the addition was intended to be signed.
add.l   dN,dN
```

```asm
Calculating effective address involving a value and registers xN and aN.
If -128 <= val <= 127
add.[wl]  #val,aN    ->    lea  val(aN,xN.s),aN      ; Saves 8 cycles.
add.[wl]  xN,aN
```

```asm
Calculating effective address involving a value and registers xN and aN.
If -128 <= val <= 127
add.[wl]  xN,aN      ->    lea  val(aN,xN.s),aN      ; Saves 8 cycles.
add.[wl]  #val,aN
```

```asm
Calculating effective address involving a value and registers xN and aN.
If -127 <= val <= 128
sub.[wl]  #val,aN    ->    lea  -val(aN,xN.s),aN     ; Saves 8 cycles
add.[wl]  xN,aN
```

```asm
Calculating effective address involving a value and registers xN and aN.
If -128 <= val <= 127
add.[wl]  xN,aN      ->    lea  -val(aN,xN.s),aN     ; Saves 8 cycles.
sub.[wl]  #val,aN
```

```asm
Addition using indexing modes
add.s   (aN,dP.z),xN    ->  adda.z  dP,aN            ; Saves [2,4] cycles. Leaves aN with different value than expected.
add.s   (aN,dP.z),xM        add.s   (aN),xN
                            add.s   (aN),xM
Make sure aN is not used before is cleared/overwitten.
```

```asm
Subtraction using indexing modes.
sub.s   (aN,dP.z),xN    ->  suba.z  dP,aN            ; Saves [2,4] cycles. Leaves aN different.
sub.s   (aN,dP.z),xM        sub.s   (aN),xN
                            sub.s   (aN),xM
Make sure aN is not used before is cleared/overwitten.
```

```asm
Addition into data regs using indexing modes.
add.s   disp(aN),dN    ->   move.s  disp(aN),dP      ; Saves 4 cycles.
add.s   disp(aN),dM         add.s   dP,dN
                            add.s   dP,dM
Needs a free data register dP.
```

```asm
Subtraction into data regs using indexing modes.
sub.s   disp(aN),dN    ->   move.s  disp(aN),dP      ; Saves 4 cycles.
sub.s   disp(aN),dM         sub.s   dP,dN
                            sub.s   dP,dM
Needs a free data register dP.
```

```asm
Addition into address regs using indexing modes.
add.s   disp(aN),aM    ->   move.s  disp(aN),aQ      ; Saves 4 cycles.
add.s   disp(aN),aP         adda.s  aQ,aM
                            adda.s  aQ,aP
Where s: w|l
Needs a free address register aQ.
aQ can be aN.
```

```asm
Subtraction into address regs using indexing modes.
sub.s   disp(aN),aM    ->   move.s  disp(aN),aQ      ; Saves 4 cycles.
sub.s   disp(aN),aP         suba.s  aQ,aM
                            suba.s  aQ,aP
Where s: w|l
Needs a free address register aQ.
aQ can be aN.
```

```asm
Push word constants into stack.
move.w   #x,-(sp)   ->    move.l  #xy,-(sp)      ; Saves 4 cycles.
move.w   #y,-(sp)
xy = (x << 16) | (y & 0xffff)
```

```asm
Move byte constants into consecutive memory.
If mem1+1 == mem2
move.b   #x,mem1    ->    move.w  #xy,mem1       ; Saves 20 cycles.
move.b   #y,mem2
xy = (x << 8) | (y & 0xff)
mem1 must be an even address
```

```asm
Move byte constants into consecutive memory.
If mem1-1 == mem2
move.b   #x,mem1    ->    move.w  #yx,mem2       ; Saves 20 cycles.
move.b   #y,mem2
yx = (y << 8) | (x & 0xff)
mem2 must be an even address
```

```asm
Move word constants into consecutive memory.
If mem1+2 == mem2
move.w   #x,mem1    ->    move.l  #xy,mem1       ; Saves 12 cycles.
move.w   #y,mem2
xy = (x << 16) | (y & 0xffff)
```

```asm
Move word constants into consecutive memory.
If mem1-2 == mem2
move.w   #x,mem1    ->    move.l  #yx,mem2       ; Saves 12 cycles.
move.w   #y,mem2
yx = (y << 16) | (x & 0xffff)
```

```asm
Move byte constants into consecutive memory calculated from effective address.
If disp1+1 == disp2
move.b   #x,disp1(aN)   ->   move.w  #xy,disp1(aN)     ; Saves 16 cycles.
move.b   #y,disp2(aN)
xy = (x << 8) | (y & 0xff)
disp1 must be an even number
```

```asm
Move byte constants into consecutive memory calculated from effective address.
If disp1-1 == disp2
move.b   #x,disp1(aN)   ->   move.w  #yx,disp2(aN)     ; Saves 16 cycles.
move.b   #y,disp2(aN)
yx = (y << 8) | (x & 0xff)
disp2 must be an even number
```

```asm
Move byte constants into consecutive symbols.
If symbolName+P + 1 = symbolName+Q
move.b   #x,symbolName+P   ->   move.w  #xy,symbolName+P     ; Saves 8 cycles.
move.b   #y,symbolName+Q
xy = (x << 8) | (y & 0xff)
+P must be an even number
```

```asm
Move byte constants into consecutive symbols.
If symbolName+P - 1 = symbolName+Q
move.b   #x,symbolName+P   ->   move.w  #yx,symbolName+Q     ; Saves 8 cycles.
move.b   #y,symbolName+Q
yx = (y << 8) | (x & 0xff)
+Q must be an even number
```

```asm
Move word constants into consecutive memory calculated from effective address.
If disp1+2 == disp2
move.w   #x,disp1(aN)   ->   move.l  #xy,disp1(aN)     ; Saves 8 cycles.
move.w   #y,disp2(aN)
xy = (x << 16) | (y & 0xffff)
```

```asm
Move word constants into consecutive memory calculated from effective address.
If disp1-2 == disp2
move.w   #x,disp1(aN)   ->   move.l  #yx,disp2(aN)     ; Saves 8 cycles.
move.w   #y,disp2(aN)
yx = (y << 16) | (x & 0xffff)
```

```asm
Move word constants into consecutive symbols.
If symbolName+P + 2 = symbolName+Q
move.w   #x,symbolName+P   ->   move.l  #xy,symbolName+P     ; Saves 8 cycles.
move.w   #y,symbolName+Q
xy = (x << 16) | (y & 0xffff)
```

```asm
Move word constants into consecutive symbols.
If symbolName+P - 2 = symbolName+Q
move.w   #x,symbolName+P   ->   move.l  #yx,symbolName+Q     ; Saves 8 cycles.
move.w   #y,symbolName+Q
yx = (y << 16) | (x & 0xffff)
```

```asm
Writing multiple values from random memory or regs to sequential memory.
Where symbolName+P = symbolName+Q +/- 1/2/4
move.s  <ea_1>,symbolName+P     ->    lea symbolName+offset,aN          ; Saves 4 cycles.
move.s  <ea_2>,symbolName+Q           move.s  <ea_1>,(aN)[+]
                                      move.s  <ea_2>,[-](aN)
Needs a free aN address register.
Ensure aN is not used in the <ea>.
```

```asm
Keep memory operands in registers.
add/sub.s   symbol_or_mem,dN    ->    move.s     symbol_or_mem,dP      ; Saves 8 cycles.
add/sub.s   symbol_or_mem,dM          add/sub.s  dP,dN
                                      add/sub.s  dP,dM
Needs free data register dP.
```

```asm
Move 2 consecutive word values from indirect memory to 2 consecutive indirect memory addresses.
move.w   disp1(aN),disp3(aM)    ->   move.l  disp1(aN),disp3(aM)       ; Saves 8 cycles.
move.w   disp2(aN),disp4(aM)
Displacements can be optional.
disp1+2 = disp2
disp3+2 = disp4
```

```asm
Move value from memory to memory.
move.s  symbolName1+off1,dN     ->    move.s  symbolName1+off1,symbolName2+off2     ; Saves 4 cycles. Leaves dN free.
move.s  dN,symbolName2+off2
symbolName1 can be symbolName2.
off1 and off2 can be omitted or 0.
Leaves dN free.
Ensure dN is not used afterwards before cleared or overwritten.
```

```asm
Memory to memory with both auto increment pointers.
move.s  (aN)+,dN        ->    move.s  (aN)+,(aM)+          ; Saves 4 cycles. Leaves dN free.
move.s  dN,(aM)+
Leaves dN free.
Ensure dN is not used anymore or cleared/overwritten before use.
```

```asm
Memory to memory with both auto decrement pointers.
move.s  -(aN),dN        ->    move.s  -(aN),-(aM)          ; Saves 4 cycles. Leaves dN free.
move.s  dN,-(aM)
Leaves dN free.
Ensure dN is not used anymore or cleared/overwritten before use.
```

```asm
Negate a dN and then add/sub into dM or same dN.
neg.s    dN         ->    add.s   dN,dM       ; Saves 4 cycles. Leaves dN different.
sub.s    dN,dM
Leaves dN with different value than expected.
Ensure dN is not used before is overwritten or cleared.
```

```asm
Negate a dN and then add/sub into dM or same dN.
neg.s    dN         ->    eor.s   #val-1,dN   ; Saves 4 cycles.
add.s    #val,dN
Where val is 2^m, dN < val
```

```asm
Negate a dN and then add/sub into dM or same dN.
neg.s    dN         ->    sub.s   dN,dM       ; Saves 4 cycles. Leaves dN different.
add.s    dN,dM
Leaves dN with different value than expected.
Ensure dN is not used before is overwritten or cleared.
```

```asm
Clearing consecutive memory from same symbolName.
If clearing symbolName and symbolName+1.
clr.b   symbolName       ->    clr.w   symbolName      ; Saves 20 cycles.
clr.b   symbolName+1
Offset (if any) from 1st instruction must be even.
```

```asm
Clearing consecutive memory from same symbolName.
If clearing symbolName and symbolName-1.
clr.b   symbolName       ->    clr.w   symbolName-1    ; Saves 20 cycles.
clr.b   symbolName-1
Offset (if any) from 2nd instruction must be even.
```

```asm
Clearing consecutive memory from same symbolName.
If clearing symbolName and symbolName+2.
clr.w   symbolName       ->    clr.l   symbolName      ; Saves 12 cycles.
clr.w   symbolName+2
```

```asm
Clearing consecutive memory from same symbolName.
If clearing symbolName and symbolName-2.
clr.w   symbolName       ->    clr.l   symbolName-2    ; Saves 12 cycles.
clr.w   symbolName-2
```

```asm
Clearing consecutive memory from same symbolName.
If clearing symbolName and symbolName +/- 4.
clr.l   symbolName       ->    moveq    #0,xN           ; Saves [16,20,24] cycles.
clr.l   symbolName+/-4         move.l   xN,xM
                               movem.l  xN/xM,symbolName+offset
Needs xN/xM free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutive memory from same symbolName.
If clearing symbolName and symbolName +/- 2/4. Different size accesor.
clr.[wl]   symbolName         ->    moveq    #0,xN           ; Saves [8,12,16,20] cycles.
clr.[wl]   symbolName +/- 2/4       move.l   xN,xM
                                    move.l   xN,xP
                                    movem.w  xN/xM/xP,symbolName+offset
Needs xN/xM/xP free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutive memory.
If mem1+1 == mem2
clr.b   mem1       ->    clr.w   mem1        ; Saves 20 cycles.
clr.b   mem2
mem1 address must be even.
```

```asm
Clearing consecutive memory.
If mem1-1 == mem2
clr.b   mem1       ->    clr.w   mem2        ; Saves 20 cycles.
clr.b   mem2
mem2 address must be even.
```

```asm
Clearing consecutive memory.
If mem1+2 == mem2
clr.w   mem1       ->    clr.l   mem1        ; Saves 12 cycles.
clr.w   mem2
```

```asm
Clearing consecutive memory.
If mem1-2 == mem2
clr.w   mem1       ->    clr.l   mem2        ; Saves 12 cycles.
clr.w   mem2
```

```asm
Clearing consecutive memory.
If clearing memory and memory +/- 4.
clr.l   mem1       ->    moveq    #0,xN           ; Saves [16,20,24] cycles.
clr.l   mem2             move.l   xN,xM
                         movem.l  xN/xM,mem+offset
Needs xN/xM free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutive memory.
If clearing memory and memory +/- 2/4. Different size accesor.
clr.[wl]   mem1    ->    moveq    #0,xN           ; Saves [8,12,16,20] cycles.
clr.[wl]   mem2          move.l   xN,xM
                         move.l   xN,xP
                         movem.w  xN/xM/xP,mem+offset
Needs xN/xM/xP free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutive memory calculated from effective address.
If disp1+1 == disp2
clr.b   disp1(aN)      ->    clr.w   disp1(aN)       ; Saves 16 cycles.
clr.b   disp2(aN)
Displacement (if any) from 1st instruction must be even.
```

```asm
Clearing consecutive memory calculated from effective address.
If disp1-1 == disp2
clr.b   disp1(aN)      ->    clr.w   disp2(aN)       ; Saves 16 cycles.
clr.b   disp2(aN)
Displacement (if any) from 2nd instruction must be even.
```

```asm
Clearing consecutive memory calculated from effective address.
If disp1+2 == disp2
clr.w   disp1(aN)      ->    clr.l   disp1(aN)       ; Saves 8 cycles.
clr.w   disp2(aN)
```

```asm
Clearing consecutive memory calculated from effective address.
If disp1-2 == disp2
clr.w   disp1(aN)      ->    clr.l   disp2(aN)       ; Saves 8 cycles.
clr.w   disp2(aN)
```

```asm
Clear higher byte of lower word with 0xFF (255).
move.w  <ea>,dN    ->   moveq   #0,dN       ; Saves 4 cycles. Top bits of dN different.
and.w   #255,dN         move.b  <ea>,dN
Only if dN is then used with .w or .b accessor before is overwritten/cleared.
```

```asm
Redundant clear of size s when consecutively writting a value in same size s.
This looks like a gcc wrong implementation from its m68k backend.
clr.s   dN         ->    move.s  <ea>,dN         ; Saves 4 cycles
move.s  <ea>,dN
```

```asm
Clean register dN before moving a word into dN.
This pattern appears when dN is later used in an indirection (aN,dN.w).
but not when used in arithmetic or assignment for aN reg: add.l/sub.l/move.l dN,aN
moveq   #0,dN      ->    move.s  <ea>,dN         ; Saves 4 cycles.
move.s  <ea>,dN
```

```asm
Push zero and other word as a long word into the stack.
Here we make a leap of faith assuming high word of xN is already 0.
move.w  xN,-(sp)     ->    move.l  xN,-(sp)      ; Saves 8 cycles.
move.w  #0,-(sp)
TODO: ensure xN is already 0 in the higher word.
This pattern only applied if USE_AGGRESSIVE_COMPACT_ZERO_AND_WORD_INTO_LONG_TO_PUSH_INTO_STACK is on.
```

```asm
Push zero and other word as a long word into the stack.
NOTE: In this case we search for a reg that is already 0.
move.w  xN,-(sp)     ->    move.w  xN,-(sp)      ; Saves 4 cycles.
move.w  #0,-(sp)           move.w  xM,-(sp)
```

```asm
Clearing consecutively the stack by just offseting the sp.
clr.w  -(sp)     ->    subq.l  #4,sp     ; Saves 20 cycles.
clr.w  -(sp)
Also considers: move.w #0,-(sp)
This pattern only applied if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
Clearing consecutively the stack by just offseting the sp.
clr.l  -(sp)     ->    subq.l  #8,sp     ; Saves 36 cycles.
clr.l  -(sp)
Also considers:  pea  0[.wl]
This pattern only applied if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
Clearing consecutively the stack by pushing 0.
clr.l  -(sp)     ->    moveq   #0,xN         ; Saves [16,20] cycles.
clr.l  -(sp)           move.l  xN,-(sp)
                       move.l  xN,-(sp)
Also considers:  pea  0[.wl]
Needs xN free register, or a reg already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutively the stack by pushing 0.
NOTE: This is the old alternative for previous pattern.
clr.w  -(sp)     ->    pea   0.w       ; Saves 12 cycles.
clr.w  -(sp)
Also considers: move.w #0,-(sp)
```

```asm
0 <= x <= 7
moveq    #8+x,dM    ->    ror.w   #8-x,dN      ; Saves 4+4*x cycles. Wrong flags, dM different
rol.w    dM,dN
```

```asm
1 <= x <= 7
moveq    #8+x,dM    ->    swap    dN           ; Saves 4*x cycles. Wrong flags, dM different
rol.l    dM,dN            ror.l   #8-x,dN
```

```asm
moveq    #16,dM     ->    swap    dN           ; Saves 40 cycles. Wrong flags, dM different
rol.l    dM,dN
```

```asm
1 <= x <= 7
moveq    #16+x,dM   ->    swap    dN           ; Saves 32 cycles. Wrong flags, dM different
rol.l    dM,dN            rol.l   #x,dN
```

```asm
8 <= x <= 15
moveq    #16+x,dM   ->    ror.l   #16-x,dN     ; Saves 4+4*x cycles. Wrong flags, dM different
rol.l    dM,dN
```

```asm
0 <= x <= 7
moveq    #8+x,dM    ->    rol.w   #8-x,dN      ; Saves 4+4*x cycles. Wrong flags, dM different
ror.w    dM,dN
```

```asm
1 <= x <= 7
moveq    #8+x,dM    ->    swap    dN           ; Saves 4*x cycles. Wrong flags, dM different
ror.l    dM,dN            rol.l   #8-x,dN
```

```asm
moveq    #16,dM     ->    swap    dN           ; Saves 40 cycles. Wrong flags, dM different
ror.l    dM,dN
```

```asm
1 <= x <= 7
moveq    #16+x,dM   ->    swap    dN           ; Saves 32 cycles. Wrong flags, dM different
ror.l    dM,dN            ror.l   #x,dN
```

```asm
8 <= x <= 15
moveq    #16+x,dM   ->    rol.l   #16-x,dN     ; Saves 4+4*x cycles. Wrong flags, dM different
ror.l    dM,dN
```

```asm
1 <= x <= 47
moveq    #8+x,dM    ->    clr.b    dN             ; Saves 18+2*x cycles. Wrong flags, dM different
lsl.b    dM,dN
```

```asm
moveq    #9,dM      ->    move.b   dN,-(sp)       ; Saves 4 cycles. Wrong flags, dM different
lsl.w    dM,dN            move.w   (sp)+,dN
                          clr.b    dN
                          add.w    dN,dN
```

```asm
2 <= x <= 7
moveq    #8+x,dM    ->    ror.w    #8-x,dN        ; Saves 4*x-4 cycles. Wrong flags, dM different
lsl.w    dM,dN            andi.w   #~((1<<(8+x))-1),dN
```

```asm
0 <= x <= 47
moveq    #16+x,dM   ->    clr.w    dN             ; Saves 38+2*x cycles. Wrong flags, dM different
lsl.w    dM,dN
```

```asm
3 <= x <= 7
moveq    #8+x,dM    ->    swap     dN             ; Saves 4*x-8 cycles. Wrong flags, dM different
lsl.l    dM,dN            ror.l    #8-x,dN
                          andi.w   #~((1<<(8+x))-1),dN
```

```asm
moveq    #16,dM     ->    swap     dN             ; Saves 36 cycles. Wrong flags, dM different
lsl.l    dM,dN            clr.w    dN
```

```asm
moveq    #17,dM     ->    add.w    dN,dN          ; Saves 34 cycles. Wrong flags, dM different
lsl.l    dM,dN            swap     dN
                          clr.w    dN
```

```asm
moveq    #18,dM     ->    add.w    dN,dN          ; Saves 32 cycles. Wrong flags, dM different
lsl.l    dM,dN            add.w    dN,dN
                          swap     dN
                          clr.w    dN
```

```asm
3 <= x <= 7
moveq    #16+x,dM   ->    lsl.w    #x,dN          ; Saves 30 cycles. dM different
lsl.l    dM,dN            swap     dN
                          clr.w    dN
```

```asm
moveq    #24,dM     ->    move.b   dN,-(sp)       ; Saves 32 cycles. dM different
lsl.l    dM,dN            move.w   (sp)+,dN
                          clr.b    dN
                          swap     dN
                          clr.w    dN
```

```asm
moveq    #25,dM     ->    move.b   dN,-(sp)       ; Saves 30 cycles. dM different
lsl.l    dM,dN            move.w   (sp)+,dN
                          clr.b    dN
                          add.w    dN,dN
                          swap     dN
                          clr.w    dN
```

```asm
2 <= x <= 7
moveq    #24+x,dM   ->    ror.w    #8-x,dN        ; Saves 4*x+22 cycles. dM different
lsl.l    dM,dN            andi.w   #~((1<<(8+x))-1),dN
                          swap     dN
                          clr.w    dN
```

```asm
0 <= x <= 31
moveq    #32+x,dM   ->    moveq    #0,dN          ; Saves 72+2*x cycles. Wrong flags, dM different
lsl.l    dM,dN
```

```asm
Logical shift right of 8 bits on a word coming from memory.
move.w  <ea>,dN      ->    clr.w   dN                ; Saves 18 cycles
lsr.w   #8,dN              move.b  <ea>,dN
Where <ea> is: disp(aN/sp), disp(aN,xN.s), symbol or memory.
Where dN is not in <ea>.
```

```asm
1 <= x <= 47
moveq    #8+x,dM    ->    clr.b    dN        ; Saves 18+2*x cycles. Wrong flags, dM different
lsr.b    dM,dN
```

```asm
2 <= x <= 6
moveq    #8+x,dM    ->    andi.w   #~((1<<(8+x))-1),dN    ; Saves 4*x-4 cycles. Wrong flags, dM different
lsr.w    dM,dN            rol.w    #8-x,dN
```

```asm
moveq    #15,dM     ->    add.w    dN,dN     ; Saves 28 cycles. Wrong flags, dM different
lsr.w    dM,dN            subx.w   dN,dN
                          neg.w    dN
```

```asm
0 <= x <= 47
moveq    #16+x,dM   ->    clr.w    dN        ; Saves 38+2*x cycles. Wrong flags, dM different
lsr.w    dM,dN
```

```asm
3 <= x <= 7
moveq    #8+x,dM    ->    andi.w   #~((1<<(8+x))-1),dN    ; Saves 4*x-8 cycles. Wrong flags, dM different
lsr.l    dM,dN            swap     dN
                          rol.l    #8-x,dN
```

```asm
moveq    #16,dM     ->    clr.w    dN        ; Saves 36 cycles. Wrong flags, dM different
lsr.l    dM,dN            swap     dN
```

```asm
1 <= x <= 7
moveq    #16+x,dM   ->    clr.w    dN        ; Saves 30 cycles. dM different
lsr.l    dM,dN            swap     dN
                          lsr.w    #x,dN
```

```asm
moveq    #24,dM     ->    swap     dN        ; Saves 36 cycles. Wrong flags, dM different
lsr.l    dM,dN            move.w   dN,-(sp)
                          moveq    #0,dN
                          move.b   (sp)+,dN
```

```asm
1 <= x <= 6
moveq    #24+x,dM   ->    clr.w    dN        ; Saves 4*x+22 cycles. dM different
lsr.l    dM,dN            swap     dN
                          andi.w   #~((1<<(8+x))-1),dN
                          rol.w    #8-x,dN
```

```asm
moveq    #31,dM     ->    add.l    dN,dN     ; Saves 58 cycles. Wrong flags, dM different
lsr.l    dM,dN            moveq    #0,dN
                          addx.w   dN,dN
```

```asm
0 <= x <= 31
moveq    #32+x,dM   ->    moveq    #0,dN     ; Saves 72+2*x cycles. Wrong flags, dM different
lsr.l    dM,dN
```

```asm
2 <= x <= 6
moveq    #8+x,dM    ->    ext.l  dN          ; Saves 4*x-6 cycles. Wrong flags, dM different. High word of dN different
asr.w    dM,dN            swap   dN
                          rol.l  #8-x,dN
```

```asm
0 <= x <= 48
moveq    #15+x,dM   ->    add.w  dN,dN       ; Saves 32+2*x cycles. Wrong flags, dM different
asr.w    dM,dM            subx.w dN,dN
```

```asm
moveq    #16,dM     ->    swap   dN          ; Saves 36 cycles. Wrong flags, dM different
asr.l    dM,dN            ext.l  dN
```

```asm
1 <= x <= 7
moveq    #16+x,dM   ->    swap   dN          ; Saves 30 cycles. dM different
asr.l    dM,dN            ext.l  dN
                          asr.w  #x,dN
```

```asm
moveq    #24,dM     ->    swap   dN          ; Saves 28 cycles. dM different
asr.l    dM,dN            ext.l  dN
                          move.w dN,-(sp)
                          move.b (sp)+,dN
                          ext.w  dN
```

```asm
moveq    #25,dM     ->    swap   dN          ; Saves 26 cycles. dM different
asr.l    dM,dN            ext.l  dN
                          moveq  #9,dM
                          asr.w  dM,dN
```

```asm
2 <= x <= 6
moveq    #24+x,dM   ->    swap   dN          ; Saves 20+4*x cycles. dM different
asr.l    dM,dN            ext.l  dN
                          swap   dN
                          rol.l  #8-x,dN
                          ext.l  dN
```

```asm
0 <= x <= 32
moveq    #31+x,dM   ->    add.l  dN,dN       ; Saves 58+2*x cycles. Wrong flags, dM different
asr.l    dM,dN            subx.l dN,dN
```


## `optimizeMultiLines_3`

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s <ea>,dN                 ->    any_instr.s <ea>,dN       ; Saves 4 cycles
... instructions not modifying dN         ...
... and not modifying CCR: N,Z,V,C        ...
... and none of bra/jmp/bsr/jsr           ...
tst.s  dN                                 bCC    label
bCC    label
```

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s  dN                      ->    any_instr.s  dN          ; Saves 4 cycles
... instructions not modifying dN          ...
... and not modifying CCR: N,Z,V,C         ...
... and none of bra/jmp/bsr/jsr            ...
tst.s  dN                                  bCC    label
bCC    label
```

```asm
Memory dereference test.
By moving the dereference memory value into a data reg intead of an address reg, we can set CC flags.
The registers can be inverted and the move instruction is moved after the bCC.
move.l     symbol_or_mem,aN    ->    move.l  symbol_or_mem,dN       ; Saves 4 cycles if bCC does actually branch.
move.[wl]  aN,dN                     bCC     label
bCC        label                     move.l  dN,aN
Ensure aN is not used after the label definition, or overwritten/cleared after the label definition.
```

```asm
Calculation of addressing offset.
neg.[wl]   dN                    ->    suba.[wl]  dN,aN             ; Saves [2,12] cycles
add.[wl]   #val,dN                     lea        val+disp(aN),aN
move.[wl]  dM,disp(aN,dN.[wl])         move.[wl]  dM,(aN)
Displacement disp is optional.
Ensure aN is not used afterwards before being overwritten or cleared.
```

```asm
Load address and offset from an address reg to another address reg.
If -32768 <= val <= 32767
move.s  aN,aP      ->    lea     val(aN,aM.l),aP         ; Saves 12 cycles.
add.s   #val,aP
add.s   aM,aP
Considers case when add.s #val,aP is replaced by a addq.s.
```

```asm
Load address and offset from an address reg to another address reg.
If -32768 <= val <= 32767
move.s  aN,aP      ->    lea     -val(aN,aM.l),aP        ; Saves 12 cycles.
sub.s   #val,aP
add.s   aM,aP
Considers case when sub.s #val,aP is replaced by a subq.s.
```

```asm
If -32767 <= val <= 32767
move.[wl]  aN,-(sp)   ->    link    aN,#val      ; Saves 12 cycles
move.[wl]  sp,aN
add.w      #val,sp
```

```asm
Read-Modify-Write with late increment pointer.
move.s     (aN),dN      ->    <instr>.s  dM,(aN)+             ; Saves [8,12] cycles. Leaves dN different.
<instr>.s  dM,dN
move.s     dN,(aN)+
Where <instr> is one of: add|sub|and|or|eor
Ensure dN is not used anymore or cleared/overwritten before use.
If s == b then ensure we are not inside a SGDK Sound a Joy related routine.
```

```asm
Read-Modify-Write with early decrement pointer.
move.s     -(aN),dN     ->    <instr>.s  dM,-(aN)             ; Saves [8,12] cycles. Leaves dN different.
<instr>.s  dM,dN
move.s     dN,(aN)
Where <instr> is one of: add|sub|and|or|eor
Ensure dN is not used anymore or cleared/overwritten before use.
If s == b then ensure we are not inside a SGDK Sound a Joy related routine.
```

```asm
Poping from SP into a data reg and consecutively modifying the same data reg with consecutive elements from SP.
move.s1       disp1(sp),dN     ->    lea           disp1(sp),aN        ; Saves 4 cycles.
<instr_2>.s2  disp2(sp),dN           move.s1       (aN)[+],dN
<instr_3>.s3  disp3(sp),dN           <instr_2>.s2  [-](aN)[+],dN
                                     <instr_2>.s3  [-](aN),dN
Where disp1/disp2/disp3 are consecutive by adding or subtracting with s1/s2/s3.
Where <instr_1>/<instr_2> are: add/sub/and/or/eor
Needs a free address register aN.
```

```asm
Testing for null (or 0).
move.l  aN,-(sp)   ->    move.l  aN,dM           ; Saves 16 cycles
addq    #4,sp            beq     label
beq     label
Needs a free data register dM.
TODO: review this pattern.
```

```asm
Writing multiple values from random memory or regs to sequential memory.
Where symbolName+P = symbolName+Q +/- 1/2/4
Where symbolName+Q = symbolName+R +/- 1/2/4
move.s  <ea_1>,symbolName+P     ->    lea symbolName+offset,aN          ; Saves 12 cycles.
move.s  <ea_2>,symbolName+Q           move.s  <ea_1>,(aN)[+]
move.s  <ea_3>,symbolName+R           move.s  <ea_2>,[-](aN)[+]
                                      move.s  <ea_3>,[-](aN)
Needs a free aN address register.
Ensure aN is not used in the <ea>.
```

```asm
Tail recursion. Replace many BSR/JSR+RTS by many PEA+BRA/JMP.
bsr/jsr subr1     ->    pea     subr2            ; Saves 20 cycles. Different stack depth
bsr/jsr subr2           bra/jmp subr1
rts
```

```asm
Consecutively push into stack a sequence of registers.
move.[wl]  xN3,-(aN)   ->   movem.[wl]  xN3/xN2/xN1,-(aN)     ; Saves 4 cycles
move.[wl]  xN2,-(aN)
move.[wl]  xN1,-(aN)
IMPORTANT: movem.l regs,-(An) starts reading reg r7 and goes down to r0.
```

```asm
Move consecutive words or longs with fixed stride but unordered target regs.
move.[wl]  disp1(aN),xN    ->   movem.[wl]  disp1(sp),<sorted_regs>      ; Saves 2 cycles.
move.[wl]  disp2(aN),xM         exg         xA,xB
move.[wl]  disp3(aN),xP
aN is address register or sp.
Where disp1 to disp3 are increasing displacements.
Where xN,xM,xP are unsorted data/address regs.
```

```asm
Load lower word of address with offset into a data reg.
lea     disp(aM),aN      ->    moveq   #disp,dN          ; Saves 8 cycles. Leaves aN different.
moveq   #0,dN                  add.w   aM,dN
move.w  aN,dN
Where aN != aM
Where -128 <= disp <= 127
Ensure aN is not used anymore or cleared/overwritten before use.
```

```asm
Calculates offset indexes for accessing arrays.
add/sub.l  dM,dN                ->    add/sub.w  dM,dN            ; Saves 4 cycles
lea        symbol_or_mem,aN           lea        symbol_or_mem,aN
move.[wl]  dP,(aN,dN.[wl])            move.[wl]  dP,(aN,dN.w)
Where:
  symbol_or_mem[.wl][+-N][.bwl]
  dM can be dN
```

```asm
Calculates offset indexes for accessing arrays.
add/sub.l  dM,dN                ->    add/sub.w  dM,dN            ; Saves 4 cycles
lea        symbol_or_mem,aN           lea        symbol_or_mem,aN
move.[wl]  d(sp),(aN,dN.[wl])         move.[wl]  d(sp),(aN,dN.w)
Where:
symbol_or_mem[.wl][-+N][.bwl]
  dM can be dN
  Displacement d in d(sp) is optional
```

```asm
Unnecessary redundant use of address register.
move.[wl]     dM,aN        ->    add/sub.[wl]  dM,dN         ; Saves [4,8] cycles. Leaves aN as a potential free register.
add/sub.[wl]  aN,dN              move.[wl]     dN,-(sp)
move.[wl]     dN,-(sp)
Ensure aN is not used anymore or cleared/overwritten before use.
Leaves aN as a potential free register.
```

```asm
Unnecessary copy.
move.l  dN,aN     ->   move.l  dN,aN             ; Saves 4 cycles
move.w  aN,dN          <any_instr> other than jcc/bcc
<any_instr> other than jcc/bcc
```

```asm
Unnecessary redundant use of data register.
move.b     (aN),dM    ->    <instr>.b  (aN),dN     ; Saves 4 cycles. Leaves dM free.
and.w      #255,dM          andi.w     #255,dN
<instr>.b  dM,dN
Where <instr> is one of next for .b accessor: or|eor|add|sub
Leaves dM free.
Ensure dM is not used before is cleared or overwritten.
```

```asm
Clean word before copying a byte.
move.b       (aN),dN    ->    moveq        #0,dN       ; Saves 4 cycles. Leaves dN different.
and.w        #255,dN          move.b       (aN),dN
<instr>[.w]  dM,dN            <instr>[.w]  dM,dN
Where <instr> is one of next for .w accessor: or|eor|add|sub|muls|mulu|divs|divu.
Leaves dN different.
Ensure dN is not used before is cleared or overwritten, or is used as word or byte before is cleared or overwritten.
```

```asm
Redundant move when preceding store sets CCR flags for BCC.
First move sets CCR flags, so next move is redundant.
move.s  aN,(aM)     ->    move.s  aN,(aM)        ; Saves 4 cycles. Leaves dN different.
move.s  aN,dN             bCC     label
bCC     label
Leaves dN with different value in upper word.
Ensure dN is not used anymore or cleared/overwritten before use.
```

```asm
Extra register move cost between data reg and adddress reg.
Optimization useful when using .w only.
move.w  (aN),aM     ->    move.w  (aN),dM        ; Saves 4 cycles. Leaves aM different.
add.w   dN,aM             add.w   dN,dM
move.w  aM,(aN)+          move.w  dM,(aN)+
Needs a free data register dM.
Leaves aM with different value.
Ensure aM is not used anymore or cleared/overwritten before use.
```

```asm
Case for a potentially new free register.
Clear higher word of data register
moveq[.l]   #0,dN     ->    swap    dM           ; Saves 0 cycles. leaves dN free.
move.w      dM,dN           clr.w   dM
move.l      dN,dM           swap    dM
Leaves dN free.
Only valid if dN is not used afterwards before it's cleared or overwritten.
Only if at last pass, so we avoid missing optimization opportunities using moveq #0,dN.
```

```asm
Clear mask: using dN as a clearing mask over dM
not.s  dN       ->    or.s   dN,dM           ; Saves 4 cycles.
and.s  dN,dM          eor.s  dN,dM
not.s  dN
```

```asm
Clearing consecutively the stack by just offseting the sp.
clr.w  -(sp)     ->    subq.l  #6,sp         ; Saves 34 cycles.
clr.w  -(sp)
clr.w  -(sp)
Also considers: move.w #0,-(sp)
This pattern is applied only if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
Clearing consecutively the stack by just offseting the sp.
clr.l  -(sp)     ->    lea     -12(sp),sp    ; Saves 58 cycles.
clr.l  -(sp)
clr.l  -(sp)
Also considers:  pea  0[.wl]
This pattern is applied only if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
Clearing consecutively the stack by pushing 0.
clr.w  -(sp)     ->    moveq   #0,xN         ; Saves [18,22] cycles.
clr.w  -(sp)           move.l  xN,-(sp)
clr.w  -(sp)           move.w  xN,-(sp)
Also considers: move.w #0,-(sp)
Needs xN free register, or a reg already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutively the stack by pushing 0.
NOTE: This is the old alternative for previous pattern.
clr.w  -(sp)     ->    pea     0.w           ; Saves 14 cycles.
clr.w  -(sp)           move.w  #0,-(sp)
clr.w  -(sp)
Also considers: move.w #0,-(sp)
```

```asm
Clearing consecutively the stack by pushing 0.
clr.l  -(sp)     ->    moveq   #0,xN         ; Saves [22,26,30,34] cycles.
clr.l  -(sp)           move.l  xN,xM
clr.l  -(sp)           move.l  xN,xP
                       movem.l xN/xM/xP,-(sp)
Also considers:  pea  0[.wl]
Needs xN/xM/xP free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutively the stack by pushing 0.
NOTE: This is the old alternative for previous pattern.
clr.l  -(sp)     ->    moveq   #0,dN         ; Saves 22 cycles.
clr.l  -(sp)           moveq   #0,dM
clr.l  -(sp)           moveq   #0,dP
                       movem.l dN/dM/dP,-(sp)
Needs 3 free data registers or already holding 0.
Also considers:  pea  0[.wl]
```

```asm
Clear consecutive memory. All same size accesor.
clr.l  symbolName+P    ->    moveq    #0,xN           ; Saves [24,28,32] cycles.
clr.l  symbolName+Q          move.l   xN,xM
clr.l  symbolName+R          move.l   xN,xP
                             movem.l  xN/xM/xP,symbolName+offset
Where symbolName+P = symbolName+Q +/- 4
Where symbolName+Q = symbolName+R +/- 4
Needs xN/xM/xP free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. Different size accesor.
clr.[bw]  symbol_or_mem+P    ->    moveq    #0,xN        ; Saves [40,44] cycles.
clr.[bw]  symbol_or_mem+Q          move.l   xN,symbol_or_mem+offset
clr.[bw]  symbol_or_mem+R
Size combinations: bbw, bwb, wbb
Where symbol_or_mem+P = symbol_or_mem+Q +/- 1/2
Where symbol_or_mem+Q = symbol_or_mem+R +/- 1/2
Needs xN free register, or a reg already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. Different size accesor.
clr.[bl]  symbol_or_mem+P    ->    moveq    #0,xN        ; Saves [30,34] cycles.
clr.[bl]  symbol_or_mem+Q          move.l   xN,symbol_or_mem+offset
clr.[bl]  symbol_or_mem+R          move.w   xN,symbol_or_mem+R
Size combinations: bbl, blb, lbb
Where symbol_or_mem+P = symbol_or_mem+Q +/- 1/4
Where symbol_or_mem+Q = symbol_or_mem+R +/- 1/4
Needs xN free register, or a reg already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. Different size accesor.
clr.[wl]  symbol_or_mem+P    ->    moveq    #0,xN        ; Saves [36,40,44] cycles.
clr.[wl]  symbol_or_mem+Q          move.l   xN,xM
clr.[wl]  symbol_or_mem+R          movem.l  xN/xM,symbol_or_mem+offset
Size combinations: wwl, wlw, lww
Where symbol_or_mem+P = symbol_or_mem+Q +/- 2/4
Where symbol_or_mem+Q = symbol_or_mem+R +/- 2/4
Needs xN/xM free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. Different size accesor.
clr.[wl]  symbol_or_mem+P    ->    moveq    #0,xN        ; Saves [20,24,28] cycles.
clr.[wl]  symbol_or_mem+Q          move.l   xN,xM
clr.[wl]  symbol_or_mem+R          movem.l  xN/xM,symbol_or_mem+offset
                                   move.w   xN,symbol_or_mem+R
Size combinations: llw, lwl, wll
Where symbol_or_mem+P = symbol_or_mem+Q +/- 2/4
Where symbol_or_mem+Q = symbol_or_mem+R +/- 2/4
Needs xN/xM free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```


## `optimizeMultiLines_4`

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s <ea>,dN                 ->    any_instr.s <ea>,dN          ; Saves 4 cycles
... instructions not modifying dN         ...
... and not modifying CCR: N,Z,V,C        ...
... and none of bra/jmp/bsr/jsr           ...
tst.s  dN                                 bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s <ea>,dN      ->    any_instr_B.s [<ea>,]dM           ; Saves 4 cycles
any_instr_B.s [<ea>,]dM          any_instr_A.s <ea>,dN
tst.s  dN                        bCC    label
bCC    label
Ensure dN is not used in the other instruction, and dM is not used in the first instruction.
```

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s  dN                      ->    any_instr.s  dN         ; Saves 4 cycles
... instructions not modifying dN          ...
... and not modifying CCR: N,Z,V,C         ...
... and none of bra/jmp/bsr/jsr            ...
tst.s  dN                                  bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s  dN         ->    any_instr_B.s  [<ea>,]dM           ; Saves 4 cycles
any_instr_B.s  [<ea>,]dM        any_instr_A.s  dN
tst.s  dN                       bCC    label
bCC    label
Ensure dN is not used in the other instruction, and dM is not used in the first instruction.
```

```asm
Null pointer or just comparison with 0 test improvement.
move.w  #val,aN                 ->    moveq   #val,dN         ; Saves [4,8,12] cycles. Leaves aN/aM different.
lea     (aN,dM.l),aM                  <move.l dN,aN>   <-- needed if aN is used before cleared/overwritten
cmp.w   #0,aM  or  move.l aM,dN       add.l   dM,dN
bCC     label                         <move.l  dN,aM>  <-- needed if aM is used before cleared/overwritten
                                      bCC     label
Where -128 <= val <= 127
If instruction cmp.w is a match then:
   It needs a free data register dN.
   Ensure dN is not used anymore or cleared/overwritten before use.
Ensure dN != dM
Some instructions are optional depending on aN/aM used before cleared/overwritten
```

```asm
Word packing.
swap[.w] dN           ->    swap    dN             ; Saves [24,32] cycles. Leaves dM different.
clr.w    dN                 move.w  dM,dN
and.l    #0xFFFF,dM
or.l     dM,dN
Leaves dM with different value in upper word.
Ensure dM is not used anymore before is cleared or overwritten, or is used as word or byte.
```

```asm
Consecutive copy of memory into a single invariant memory target.
move.s disp1(aN),(aM)      ->      move.s  (aN)+,(aM)           ; Saves [4,8] cycles
move.s disp2(aN),(aM)              move.s -(aN)+,(aM)
move.s disp3(aN),(aM)              move.s -(aN)+,(aM)
lea    val(aN),aN                  lea    val-N*s(aN),aN
Where s is w/l
```

```asm
Explicitelly sign extend multiple data regs.
move.w  disp1(Am),Dn    ->    movem.w  disp1(Am),Dn/Dm         ; Saves 8 cycles
move.w  disp2(Am),Dm          (movem does sign extension)
ext.l   Dn
ext.l   Dm
```

```asm
Explicitelly sign extend multiple data regs.
move.w  disp1(Am),Dn    ->    movem.w  disp1(Am),Dn/Dm         ; Saves 8 cycles
ext.l   Dn                    (movem does sign extension)
move.w  disp2(Am),Dm
ext.l   Dm
```

```asm
Explicitelly sign extend multiple data regs.
move.w  (Am)+,Dn      ->   movem.w  (Am)+,Dn/Dm                ; Saves 8 cycles
move.w  (Am)+,Dm           (movem does sign extension)
ext.l   Dn
ext.l   Dm
```

```asm
Explicitelly sign extend multiple data regs.
move.w  (Am)+,Dn      ->   movem.w  (Am)+,Dn/Dm                ; Saves 8 cycles
ext.l   Dn                 (movem does sign extension)
move.w  (Am)+,Dm
ext.l   Dm
```

```asm
Test if aN is in range 0xFFFF8000 <= aN <= 0x00007FFF (-32768 <= aN <= 32767).
cmp.w/l   #0x8000,aN     ->   cmpa.w   aN,aN                   ; Saves [32,24] cycles.
blt       OutOfRange          bne      OutOfRange
cmp.w/l   #0x7FFF,aN
bgt       OutOfRange
Note: we also considered the inverted order of instructions.
```

```asm
Test if dN is in range 0xFFFF8000 <= dN <= 0x00007FFF (-32768 <= dN <= 32767).
cmp.l     #0xFFFF8000,dN     ->   move.w   dN,aN               ; Saves [28,20] cycles.
blt       OutOfRange              cmpa.w   aN,aN
cmp.l     #0x00007FFF,dN          bne      OutOfRange
bgt       OutOfRange
Note: we also considered the inverted order of instructions.
Needs a free address aN register.
```

```asm
Consecutively push into stack a sequence of registers.
move.[wl]  xN4,-(aN)   ->   movem.[wl]  xN4/xN3/xN2/xN1,-(aN)          ; Saves 8 cycles
move.[wl]  xN3,-(aN)
move.[wl]  xN2,-(aN)
move.[wl]  xN1,-(aN)
IMPORTANT: movem.l regs,-(An) starts reading reg r7 and goes down to r0.
```

```asm
Consecutively pop from stack into a sequence of registers.
move.[wl]  (aN)+,xN1   ->   movem.[wl]  (aN)+,xN1/xN2/xN3/xN4          ; Saves 4 cycles
move.[wl]  (aN)+,xN2
move.[wl]  (aN)+,xN3
move.[wl]  (aN)+,xN4
```

```asm
Move consecutive words or longs with fixed stride.
move.[wl]  disp1(aN),xN    ->   movem.[wl] disp1(aN),xN/xM/xP/xQ       ; Saves 8 cycles
move.[wl]  disp2(aN),xM         (4th line here if it didn't satisfy the criteria)
move.[wl]  disp3(aN),xP
move.[wl]  disp4(aN),xQ    <- this could be whatever line
aN is address register or sp.
Where disp1 to disp4 are consecutive displacements with the correct stride: +2 for word, +4 for long.
Where xN,xM,xP,xQ are already sorted by data reg type and then address reg type, with consecutive reg index per type.
```

```asm
Move consecutive words or longs with fixed stride but unordered target regs.
move.[wl]  disp1(aN),xN    ->   movem.[wl]  disp1(sp),<sorted_regs>         ; Saves [4,10] cycles.
move.[wl]  disp2(aN),xM         exg         xA,xB
move.[wl]  disp3(aN),xP         exg         xC,xD  <-- optional, depending on regs list
move.[wl]  disp4(aN),xQ
aN is address register or sp.
Where disp1 to disp4 are increasing displacements.
Where xN,xM,xP,xQ are unsorted data/address regs.
```

```asm
Move pseudo-consecutive words or longs with fixed stride but 1, 2, or 3 wrong strides.
The gap left by the wrong stride will be filled by a free register.
move.[wl]  disp1(aN),xN    ->   (1st line here if it has wrong stride)      ; Saves [4,8,12] cycles
move.[wl]  disp2(aN),xM         movem.[wl] disp(aN),regs_list
move.[wl]  disp3(aN),xP         (4th line here if it has wrong stride)
move.[wl]  disp4(aN),xQ
aN is address register or sp.
Where disp1 to disp4 are increasing displacements with 1, 2, or 3 wrong strides.
Where xN,xM,xP,xQ are already sorted by data reg type and then address reg type, with increasing reg index per type.
Test case:
   move.w 12(%a2),%d7
   move.w 14(%a2),%a3
   move.w 18(%a2),%a5  <- here we have to find a free reg between a3 and a5
   move.w 22(%a2),%d4  <- d4 is not in order with previous regs
```

```asm
Pushing word memory values into stack with word adjustments for ABI long args compliance.
move.w     symbol_or_mem,-(sp)    ->    move.w     symbol_or_mem,-(sp)      ; Saves 4 cycles
sub*.[wl]  #2,sp                        move.w     symbol_or_mem,-4(sp)
move.w     symbol_or_mem,-(sp)          subq.[wl]  #6,sp
sub*.[wl]  #2,sp
Where:
 symbol_or_mem[.wl][+-N][.bwl]
```

```asm
Calculates offset indexes for accessing arrays.
and.l      #65535,dN         ->    add.w      dN,dN                ; Saves 20 cycles (16 cycles saved from removed and.l)
add.l      dN,dN                   lea        symbol_or_mem,aN
lea        symbol_or_mem,aN        move.[wl]  disp(sp),(aN,dN.w)
move.[wl]  disp(sp),(aN,dN.[wl])
Where:
  symbol_or_mem[.wl][+-N][.bwl]
  Displacement in disp(sp) is optional
```

```asm
This pattern comes up after applying optimization for lsr.w #8,dN.
move.w  dM,dN        ->   move.w  dM,-(sp)       ; Saves 4 cycles
move.w  dN,-(sp)          clr.w   dN
clr.w   dN                move.b  (sp)+,dN
move.b  (sp)+,dN
```

```asm
Unnecessary redundant initial move dN into aN.
move.[wl]      dN,aN       ->   add*/sub*.[wl] #val,dN      ; Saves 4 cycles
add*/sub*.[wl] #val,aN          move.[wl]      dN,d(aM)
move.[wl]      aN,disp(aM)      move.[wl]      dN,aN
move.[wl]      aN,dN
```

```asm
Unnecessary clear of data register to multiply an address register by 2.
moveq[.l]  #0,dN     ->    add.l   aN,aN         ; Saves 12 cycles. Leaves dN different.
move.w     aN,dN
move.l     dN,aN
add/sub.l  aN,aN
Leaves dN with different value.
Ensure dN is not used before cleared or overwritten.
```

```asm
Unnecessary clear of data register to multiply an address register by 2 and add/sub a constant.
move.w     aN,dN     ->   add.l      aN,aN       ; Saves 4 cycles. Leaves dN different.
lsl.l      #2,dN          add.l      aN,aN
move.l     dN,aN          add/sub.l  #val,aN
add/sub.l  #val,aN
Leaves dN with different value.
Ensure dN is not used before cleared or overwritten.
```

```asm
Clean upper word of data register to later copy it into other data register.
swap[.w] dN        ->    moveq   #0,dM           ; Saves 8 cycles. Leaves dN different.
clr.w    dN              move.w  dN,dM
swap[.w] dN
move.l   dN,dM
Leaves dN with different value in upper word.
Ensure dN is not used anymore before is cleared or overwritten, or is used as word or byte.
```

```asm
Clean upper word of data register to later be used as address.
swap[.w] dN        ->    moveq   #0,dM           ; Saves 4 cycles. Leaves dN different.
clr.w    dN              move.w  dN,dM
swap[.w] dN              move.l  dM,aN
move.l   dN,aN
Needs a free data register dM.
Leaves dN with different value in upper word.
Ensure dN is not used anymore before is cleared or overwritten, or is used as word or byte.
```

```asm
Poping from SP into a data reg and consecutively modifying the same data reg with consecutive elements from SP.
move.s1       disp1(sp),dN     ->    lea           disp1(sp),aN         ; Saves 4 cycles.
<instr_2>.s2  disp2(sp),dN           move.s1       (aN)[+],dN
<instr_3>.s3  disp3(sp),dN           <instr_2>.s2  [-](aN)[+],dN
<instr_4>.s4  disp4(sp),dN           <instr_3>.s3  [-](aN)[+],dN
                                     <instr_4>.s4  [-](aN),dN
Where disp1/disp2/disp3/disp4 are consecutive by adding or subtracting with s1/s2/s3/s4.
Where <instr_1>/<instr_2>/<instr_3> are: add/sub/and/or/eor
Needs a free address register aN.
```

```asm
Writing multiple values from random memory or regs to sequential memory.
Where symbolName+P = symbolName+Q +/- 1/2/4
Where symbolName+Q = symbolName+R +/- 1/2/4
Where symbolName+R = symbolName+S +/- 1/2/4
move.s  <ea_1>,symbolName+P     ->    lea symbolName+offset,aN          ; Saves 20 cycles.
move.s  <ea_2>,symbolName+Q           move.s  <ea_1>,(aN)[+]
move.s  <ea_3>,symbolName+R           move.s  <ea_2>,[-](aN)[+]
move.s  <ea_4>,symbolName+S           move.s  <ea_3>,[-](aN)[+]
                                      move.s  <ea_4>,[-](aN)
Needs a free aN address register.
Ensure aN is not used in the <ea>.
```

```asm
Writing multiple values from random memory or regs to sequential memory.
This particular case applies when the last consecutive memory value is a symbol.
Where symbolName+P = symbolName+Q +/- 1/2/4
lea     symbolName+P,aN         ->    lea symbolName+offset,aN          ; Saves 8 cycles.
move.s  <ea_1>,(%aN)[+]               move.s  <ea_1>,(%aN)[+]
move.s  <ea_2>,[-](aN)                move.s  <ea_2>,[-](aN)[+]
move.s  <ea_3>,symbolName+Q           move.s  <ea_3>,[-](aN)
Ensure aN is not used in any <ea>.
```

```asm
Tail recursion. Replace many BSR/JSR+RTS by many PEA+BRA/JMP.
bsr/jsr subr1     ->    pea subr3            ; Saves 16 cycles. Different stack depth
bsr/jsr subr2           pea subr2
bsr/jsr subr3           bra/jmp subr1
rts
```

```asm
Clearing consecutively the stack by just offseting the sp.
clr.w  -(sp)     ->    subq.l  #8,sp         ; Saves 48 cycles.
clr.w  -(sp)
clr.w  -(sp)
clr.w  -(sp)
Also considers: move.w #0,-(sp)
This pattern applied only if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
Clearing consecutively the stack by just offseting the sp.
clr.l  -(sp)     ->    lea     -16(sp),sp    ; Saves 80 cycles.
clr.l  -(sp)
clr.l  -(sp)
clr.l  -(sp)
Also considers:  pea  0[.wl]
This pattern applied only if USE_AGGRESSIVE_CLR_SP_OPTIMIZATION is on.
```

```asm
Clearing consecutively the stack by pushing 0.
clr.w  -(sp)     ->    moveq   #0,xN         ; Saves [24,28,32] cycles.
clr.w  -(sp)           move.l  xN,xM
clr.w  -(sp)           movem.l xN/xM,-(sp)
clr.w  -(sp)
Also considers: move.w #0,-(sp)
Needs xN/xM free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutively the stack by pushing 0.
NOTE: This is the old alternative for previous pattern.
clr.w  -(sp)     ->    pea     0.w           ; Saves 24 cycles.
clr.w  -(sp)           pea     0.w
clr.w  -(sp)
clr.w  -(sp)
Also considers: move.w #0,-(sp)
```

```asm
Clearing consecutively the stack by pushing 0.
clr.l  -(sp)     ->    moveq   #0,xN         ; Saves [32,36,40,44,48] cycles.
clr.l  -(sp)           move.l  xN,xM
clr.l  -(sp)           move.l  xN,xP
clr.l  -(sp)           move.l  xN,xQ
                       movem.l xN/xM/xP/xQ,-(sp)
Also considers:  pea  0[.wl]
Needs xN/xM/xP/xQ free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clearing consecutively the stack by pushing 0.
NOTE: This is the old alternative for previous pattern.
clr.l  -(sp)     ->    moveq   #0,dN         ; Saves 32 cycles.
clr.l  -(sp)           moveq   #0,dM
clr.l  -(sp)           moveq   #0,dP
clr.l  -(sp)           moveq   #0,dQ
                       movem.l dN/dM/dP/dQ,-(sp)
Needs 4 free data registers or already holding 0.
Also considers:  pea  0.w
```

```asm
Clear consecutive memory. All same size accesor.
clr.l  symbolName+P    ->    moveq    #0,xN           ; Saves [64,68,72,76] cycles.
clr.l  symbolName+Q          move.l   xN,xM
clr.l  symbolName+R          move.l   xN,xP
clr.l  symbolName+S          move.l   xN,xQ
                             movem.l  xN/xM/xP/xQ,symbolName+offset
Where symbolName+P = symbolName+Q +/- 4
Where symbolName+Q = symbolName+R +/- 4
Where symbolName+R = symbolName+S +/- 4
Needs xN/xM/xP/xQ free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. All same size accesor.
clr.b  symbolName+P    ->    moveq    #0,xN           ; Saves [56,60] cycles.
clr.b  symbolName+Q          move.l   xN,symbolName+offset
clr.b  symbolName+R
clr.b  symbolName+S
Where symbolName+P = symbolName+Q +/- 1
Where symbolName+Q = symbolName+R +/- 1
Where symbolName+R = symbolName+S +/- 1
Needs xN free register, or a reg already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. All same size accesor.
clr.[bwl]  symbolName+P    ->    moveq    #0,xN           ; Saves [42,46,50,54] cycles.
clr.[bwl]  symbolName+Q          move.l   xN,xM
clr.[bwl]  symbolName+R          movem.l  xN/xM,symbolName+offset
clr.[bwl]  symbolName+S          move.w   xN,symbolName+S
Size combinations: wwwl, wwlw, wlww, lwww,
                   bbwl, bblw, wbbl, lbbw, bwbl, blbw, wlbb, lwbb, wblb, lbwb
Where symbolName+P = symbolName+Q +/- 1/2/4
Where symbolName+Q = symbolName+R +/- 1/2/4
Where symbolName+R = symbolName+S +/- 1/2/4
Needs xN/xM/xP/xQ free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. All same size accesor.
clr.[wl]  symbolName+P    ->    moveq    #0,xN           ; Saves [44,48,52,56] cycles.
clr.[wl]  symbolName+Q          move.l   xN,xM
clr.[wl]  symbolName+R          move.l   xN,xP
clr.[wl]  symbolName+S          movem.l  xN/xM/xP,symbolName+offset
Size combinations: llww, lwwl, wwll, wllw, lwlw, wlwl
Where symbolName+P = symbolName+Q +/- 2/4
Where symbolName+Q = symbolName+R +/- 2/4
Where symbolName+R = symbolName+S +/- 2/4
Needs xN/xM/xP/xQ free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```

```asm
Clear consecutive memory. All same size accesor.
clr.[wl]  symbolName+P    ->    moveq    #0,xN           ; Saves [42,46,50,54] cycles.
clr.[wl]  symbolName+Q          move.l   xN,xM
clr.[wl]  symbolName+R          move.l   xN,xP
clr.[wl]  symbolName+S          movem.l  xN/xM/xP,symbolName+offset
                                move.w   xN,symbolName+S
Size combinations: lllw, llwl, lwll, wlll
Where symbolName+P = symbolName+Q +/- 2/4
Where symbolName+Q = symbolName+R +/- 2/4
Where symbolName+R = symbolName+S +/- 2/4
Needs xN/xM/xP/xQ free registers, or as much as possible regs already holding 0.
There is a penalty of 4 cycles if first free reg is an address reg due to: suba.l xN,xN
```


## `optimizeMultiLines_5`

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s <ea>,dN                 ->    any_instr.s <ea>,dN          ; Saves 4 cycles
... instructions not modifying dN         ...
... and not modifying CCR: N,Z,V,C        ...
... and none of bra/jmp/bsr/jsr           ...
tst.s  dN                                 bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s <ea>,dN      ->    any_instr_B.s [<ea>,]dM          ; Saves 4 cycles
any_instr_B.s [<ea>,]dM          any_instr_C.s [<ea>,]dP
any_instr_C.s [<ea>,]dP          any_instr_A.s <ea>,dN
tst.s  dN                        bCC    label
bCC    label
Ensure dN is not used in the other instructions, and dM/dP is not used in the first instruction.
```

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s  dN                      ->    any_instr.s  dN        ; Saves 4 cycles
... instructions not modifying dN          ...
... and not modifying CCR: N,Z,V,C         ...
... and none of bra/jmp/bsr/jsr            ...
tst.s  dN                                  bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s  dN         ->    any_instr_B.s  [<ea>,]dM          ; Saves 4 cycles
any_instr_B.s  [<ea>,]dM        any_instr_C.s  [<ea>,]dP
any_instr_C.s  [<ea>,]dP        any_instr_A.s  dN
tst.s  dN                       bCC    label
bCC    label
Ensure dN is not used in the other instruction, and dM/dP are not used in the first instruction.
```

```asm
Consecutive copy of memory into a single invariant memory target.
move.s disp1(aN),(aM)      ->      move.s  (aN)+,(aM)             ; Saves [8,12] cycles
move.s disp2(aN),(aM)              move.s -(aN)+,(aM)
move.s disp3(aN),(aM)              move.s -(aN)+,(aM)
move.s disp4(aN),(aM)              move.s -(aN)+,(aM)
lea    val(aN),aN                  lea    val-N*s(aN),aN
```

```asm
Boolean set 0 or 1 in long word.
<any_instr_set_ccr>    ->    moveq    #0,dN                 ; Saves [6,10] cycles.
sCC[.b]  dN                  <any_instr_set_ccr>
ext.w    dN                  sCC[.b]  dN
ext.l    dN                  neg.b    dN  <-- 0 or 1. Remaining bits are already 0.
neg.l    dN
Where <any_instr_set_ccr> must not use dN as source or in any indirection, neither as target.
The moveq #0,dN can be optional if it exists in previous lines and it holds up to this line.
```

```asm
Explicitelly sign extend multiple data regs after loading from memory.
lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm       ; Saves 16 cycles
move.w  disp1(Am),Dn                  (movem does sign extension)
move.w  disp2(Am),Dm
ext.l   Dn
ext.l   Dm
Note: Ensure Am is not used afterwards unless is overwritten/cleared before any usage.
```

```asm
Explicitelly sign extend multiple data regs after loading from memory.
lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm       ; Saves 16 cycles
move.w  disp1(Am),Dn                  (movem does sign extension)
ext.l   Dn
move.w  disp2(Am),Dm
ext.l   Dm
Note: Ensure Am is not used afterwards unless is overwritten/cleared before any usage.
```

```asm
Explicitelly sign extend multiple data regs after loading from memory.
lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm       ; Saves 16 cycles
move.w  (Am)+,Dn                      (movem does sign extension)
move.w  (Am)[+],Dm
ext.l   Dn
ext.l   Dm
Note: Ensure Am is not used afterwards unless is overwritten/cleared before any usage.
```

```asm
Explicitelly sign extend multiple data regs after loading from memory.
lea     label_or_val(An/pc),Am   ->   movem.w  label_or_val(An/pc),Dn/Dm       ; Saves 16 cycles
move.w  (Am)+,Dn                      (movem does sign extension)
ext.l   Dn
move.w  (Am)[+],Dm
ext.l   Dm
Note: Ensure Am is not used afterwards unless is overwritten/cleared before any usage.
```

```asm
Writing multiple values from random memory or regs to sequential memory.
Where symbolName+P = symbolName+Q +/- 1/2/4
Where symbolName+Q = symbolName+R +/- 1/2/4
Where symbolName+R = symbolName+S +/- 1/2/4
Where symbolName+S = symbolName+T +/- 1/2/4
move.s  <ea_1>,symbolName+P     ->    lea symbolName+offset,aN          ; Saves 28 cycles.
move.s  <ea_2>,symbolName+Q           move.s  <ea_1>,(aN)[+]
move.s  <ea_3>,symbolName+R           move.s  <ea_2>,[-](aN)[+]
move.s  <ea_4>,symbolName+S           move.s  <ea_3>,[-](aN)[+]
move.s  <ea_5>,symbolName+T           move.s  <ea_4>,[-](aN)[+]
                                      move.s  <ea_5>,[-](aN)
Needs a free aN address register.
Ensure aN is not used in the <ea>.
```

```asm
Writing multiple values from random memory or regs to sequential memory.
This particular case applies when the last consecutive memory value is a symbol.
Where symbolName+P = symbolName+Q +/- 1/2/4
lea     symbolName+P,aN         ->    lea symbolName+offset,aN          ; Saves 8 cycles.
move.s  <ea_1>,(%aN)[+]               move.s  <ea_1>,(%aN)[+]
move.s  <ea_2>,[-](aN)[+]             move.s  <ea_2>,[-](aN)[+]
move.s  <ea_3>,[-](aN)                move.s  <ea_3>,[-](aN)[+]
move.s  <ea_4>,symbolName+Q           move.s  <ea_4>,[-](aN)
Ensure aN is not used in any <ea>.
```

```asm
Consecutively push into stack a sequence of registers.
move.[wl]  xN5,-(aN)   ->   movem.[wl]  xN5/xN4/xN3/xN2/xN1,-(aN)       ; Saves 12 cycles
move.[wl]  xN4,-(aN)
move.[wl]  xN3,-(aN)
move.[wl]  xN2,-(aN)
move.[wl]  xN1,-(aN)
IMPORTANT: movem.l regs,-(An) starts reading reg r7 and goes down to r0
```

```asm
Consecutively pop from stack into a sequence of registers.
move.[wl]  (aN)+,xN1   ->   movem.[wl]  (aN)+,xN1/xN2/xN3/xN4/xN5       ; Saves 8 cycles
move.[wl]  (aN)+,xN2
move.[wl]  (aN)+,xN3
move.[wl]  (aN)+,xN4
move.[wl]  (aN)+,xN5
```

```asm
Move consecutive words or longs with fixed stride.
move.[wl]  disp1(aN),xN    ->   movem.[wl] disp1(aN),xN/xM/xP/xQ/xR     ; Saves 12 cycles
move.[wl]  disp2(aN),xM         (5th line here if it didn't satisfy the criteria)
move.[wl]  disp3(aN),xP
move.[wl]  disp4(aN),xQ
move.[wl]  disp5(aN),xR    <- this could be whatever line
aN is address register or sp.
Where disp1 to disp5 are consecutive displacements with the correct stride: +2 for word, +4 for long.
Where xN,xM,xP,xQ,xR are already sorted by data reg type and then address reg type, with consecutive reg index per type.
```

```asm
Move consecutive words or longs with fixed stride but unordered target regs.
move.[wl]  disp1(aN),xN    ->   movem.[wl]  disp1(sp),<sorted_regs>     ; Saves [6,12,18] cycles.
move.[wl]  disp2(aN),xM         exg         xA,xB
move.[wl]  disp3(aN),xP         exg         xC,xD  <-- optional, depending on regs list
move.[wl]  disp4(aN),xQ         exg         xE,xF  <-- optional, depending on regs list
move.[wl]  disp5(aN),xR
aN is address register or sp.
Where disp1 to disp5 are increasing displacements.
Where xN,xM,xP,xQ,xR are unsorted data/address regs.
```

```asm
Unnecessary clear of data register to load 2 word values.
moveq[.l]  #0,dN     ->   move.w  <ea>,dN            ; Saves 8 cycles
move.w     <ea>,dN        swap    dN
swap[.w]   dN             move.w  <ea>,dN
clr.w      dN
move.w     <ea>,dN
```

```asm
Unnecessary clear of data register to multiply by 4 an address register and add/sub a constant.
moveq[.l]  #0,dN     ->   add.l      aN,aN           ; Saves 8 cycles. Leaves dN with different value than expected.
move.w     aN,dN          add.l      aN,aN
lsl.l      #2,dN          add/sub.l  #val,aN
move.l     dN,aN
add/sub.l  #val,aN
```

```asm
Unnecessary clear of data register to multiply an address register by 2 and add/sub a constant.
moveq[.l]  #0,dN     ->   move.l     aN,aM           ; Saves 8 cycles. Leaves dN with different value than expected.
move.w     aN,dN          add.l      aM,aM
add.l      dN,dN          add/sub.l  #val,aM
move.l     dN,aM
add/sub.l  #val,aM
```

```asm
Calculates offset indexes for accessing arrays.
moveq[.l]  #0,dN                ->    move.w     symbol_or_mem_1,dN        ; Saves 8 cycles
move.w     symbol_or_mem_1,dN         add/sub.w  dN,dN
add/sub.l  dN,dN                      lea        symbol_or_mem_2,aN
lea        symbol_or_mem_2,aN         move.[wl]  (aN,dN.w),dP
move.[wl]  (aN,dN.[wl]),dP
Where:
  symbol_or_mem_1[.wl][-+N][.bwl]
  symbol_or_mem_2[.wl][-+N][.bwl]
  dP can be dN
```

```asm
Calculates offset indexes for accessing arrays. The offset at dN has already the correct stride.
moveq[.l]  #0,dN               ->   move.w     disp1(sp),dN           ; Saves 16 cycles
move.w     disp1(sp),dN             move.l     disp2(sp),aN
move.l     disp2(sp),aN             lea        symbol_or_mem(aN,dN.w),aN
add/sub.l  #symbol_or_mem,aN        move.[wl]  (aN),dP
move.[wl]  (aN,dN.[wl]),dP
Where:
  symbol_or_mem[.wl][-+N][.bwl]
  dP can be dN
```

```asm
Calculates jump offsets is always a word length operation.
moveq[.wl] #0,dN                 ->    move.w  symbol_or_mem,dN       ; Saves 8 cycles
move.w     symbol_or_mem,dN            add.w   dN,dN
add.[wl]   dN,dN                       move.w  label(pc,dN.w),dP
move.w     label(pc,dN.[wl]),dP        jmp     disp(pc,dP.w)
jmp        disp(pc,dP.w)
Where:
  symbol_or_mem[.wl][-+N][.bwl]
  dP can be dN
```

```asm
This pattern comes up after applying optimization for lsr.w #8,dN.
clr.w   dN           ->   move.w  dM,-(sp)       ; Saves 8 cycles
move.w  dM,dN             clr.w   dN
move.w  dN,-(sp)          move.b  (sp)+,dN
clr.w   dN
move.b  (sp)+,dN
```


## `optimizeMultiLines_6`

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s <ea>,dN                 ->    any_instr.s <ea>,dN      ; Saves 4 cycles
... instructions not modifying dN         ...
... and not modifying CCR: N,Z,V,C        ...
... and none of bra/jmp/bsr/jsr           ...
tst.s  dN                                 bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s <ea>,dN      ->    any_instr_B.s [<ea>,]dM           ; Saves 4 cycles
any_instr_B.s [<ea>,]dM          any_instr_C.s [<ea>,]dP
any_instr_C.s [<ea>,]dP          any_instr_D.s [<ea>,]dQ
any_instr_D.s [<ea>,]dQ          any_instr_A.s <ea>,dN
tst.s  dN                        bCC    label
bCC    label
Ensure dN is not used in the other instructions, and dM/dP/dQ is not used in the first instruction.
```

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s  dN                      ->    any_instr.s  dN         ; Saves 4 cycles
... instructions not modifying dN          ...
... and not modifying CCR: N,Z,V,C         ...
... and none of bra/jmp/bsr/jsr            ...
tst.s  dN                                  bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s  dN         ->    any_instr_B.s  [<ea>,]dM           ; Saves 4 cycles
any_instr_B.s  [<ea>,]dM        any_instr_C.s  [<ea>,]dP
any_instr_C.s  [<ea>,]dP        any_instr_D.s  [<ea>,]dQ
any_instr_D.s  [<ea>,]dQ        any_instr_A.s  dN
tst.s  dN                       bCC    label
bCC    label
Ensure dN is not used in the other instruction, and dM/dP/dQ are not used in the first instruction.
```

```asm
Consecutive copy of memory into a single invariant memory target.
move.s disp1(aN),(aM)      ->      move.s  (aN)+,(aM)              ; Saves [12,16] cycles
move.s disp2(aN),(aM)              move.s -(aN)+,(aM)
move.s disp3(aN),(aM)              move.s -(aN)+,(aM)
move.s disp4(aN),(aM)              move.s -(aN)+,(aM)
move.s disp5(aN),(aM)              move.s -(aN)+,(aM)
lea    val(aN),aN                  lea    val-N*s(aN),aN
Where s is w/l
```

```asm
Writing multiple values from random memory or regs to sequential memory.
Where symbolName+P = symbolName+Q +/- 1/2/4
Where symbolName+Q = symbolName+R +/- 1/2/4
Where symbolName+R = symbolName+S +/- 1/2/4
Where symbolName+S = symbolName+T +/- 1/2/4
Where symbolName+T = symbolName+U +/- 1/2/4
move.s  <ea_1>,symbolName+P     ->    lea symbolName+offset,aN          ; Saves 32 cycles.
move.s  <ea_2>,symbolName+Q           move.s  <ea_1>,(aN)[+]
move.s  <ea_3>,symbolName+R           move.s  <ea_2>,[-](aN)[+]
move.s  <ea_4>,symbolName+S           move.s  <ea_3>,[-](aN)[+]
move.s  <ea_5>,symbolName+T           move.s  <ea_4>,[-](aN)[+]
move.s  <ea_6>,symbolName+U           move.s  <ea_5>,[-](aN)[+]
                                      move.s  <ea_6>,[-](aN)
Needs a free aN address register.
Ensure aN is not used in the <ea>.
```

```asm
Writing multiple values from random memory or regs to sequential memory.
This particular case applies when the last consecutive memory value is a symbol.
Where symbolName+P = symbolName+Q +/- 1/2/4
lea     symbolName+P,aN         ->    lea symbolName+offset,aN          ; Saves 8 cycles.
move.s  <ea_1>,(%aN)[+]               move.s  <ea_1>,(%aN)[+]
move.s  <ea_2>,[-](aN)[+]             move.s  <ea_2>,[-](aN)[+]
move.s  <ea_3>,[-](aN)[+]             move.s  <ea_3>,[-](aN)[+]
move.s  <ea_4>,[-](aN)                move.s  <ea_4>,[-](aN)[+]
move.s  <ea_5>,symbolName+Q           move.s  <ea_5>,[-](aN)
Ensure aN is not used in any <ea>.
```

```asm
Consecutively push into stack a sequence of registers.
move.[wl]  xN6,-(aN)   ->   movem.[wl]  xN6/xN5/xN4/xN3/xN2/xN1,-(aN)    ; Saves 16 cycles
move.[wl]  xN5,-(aN)
move.[wl]  xN4,-(aN)
move.[wl]  xN3,-(aN)
move.[wl]  xN2,-(aN)
move.[wl]  xN1,-(aN)
IMPORTANT: movem.l regs,-(An) starts reading reg r7 and goes down to r0.
```

```asm
Consecutively pop from stack into a sequence of registers.
move.[wl]  (aN)+,xN1   ->   movem.[wl]  (aN)+,xN1/xN2/xN3/xN4/xN5/xN6    ; Saves 12 cycles
move.[wl]  (aN)+,xN2
move.[wl]  (aN)+,xN3
move.[wl]  (aN)+,xN4
move.[wl]  (aN)+,xN5
move.[wl]  (aN)+,xN6
```

```asm
Move consecutive words or longs with fixed stride.
move.[wl]  disp1(aN),xN    ->   movem.[wl] disp1(aN),xN/xM/xP/xQ/xR/xS      ; Saves 16 cycles
move.[wl]  disp2(aN),xM         (6th line here if it didn't satisfy the criteria)
move.[wl]  disp3(aN),xP
move.[wl]  disp4(aN),xQ
move.[wl]  disp5(aN),xR
move.[wl]  disp6(aN),xS    <- this could be whatever line
aN is address register or sp.
Where disp1 to disp6 are consecutive displacements with the correct stride: +2 for word, +4 for long.
Where xN,xM,xP,xQ,xR,xS are already sorted by data reg type and then address reg type, with consecutive reg index per type.
```

```asm
Move consecutive words or longs with fixed stride but unordered target regs.
move.[wl]  disp1(aN),xN    ->   movem.[wl]  disp1(sp),<sorted_regs>      ; Saves [8,14,20,28] cycles.
move.[wl]  disp2(aN),xM         exg         xA,xB
move.[wl]  disp3(aN),xP         exg         xC,xD  <-- optional, depending on regs list
move.[wl]  disp4(aN),xQ         exg         xE,xF  <-- optional, depending on regs list
move.[wl]  disp5(aN),xR         exg         xG,xH  <-- optional, depending on regs list
move.[wl]  disp6(aN),xS
aN is address register or sp.
Where disp1 to disp6 are increasing displacements.
Where xN,xM,xP,xQ,xR,xS are unsorted data/address regs.
```

```asm
Pushing word memory values into stack with word adjustments for ABI long args compliance.
move.w  symbol_or_mem[+-N],-(sp)   ->   move.w    symbol_or_mem[+-N],-(sp)     ; Saves 4 cycles
sub*.s  #2,sp                           subq.s    #2,sp
move.w  symbol_or_mem[+-M],-(sp)        move.w    symbol_or_mem[+-M],-(sp)
sub*.s  #2,sp                           move.w    symbol_or_mem[+-L],-8(sp)
move.w  symbol_or_mem[+-L],-(sp)        subq.s    #6,sp
sub*.s  #2,sp
```

```asm
This pattern comes up after applying optimization for lsr.w #8,dN.
But may apply for other similar situation.
clr.w     dN         ->   moveq   #0,dN              ; Saves 12 cycles. Leaves dN with different value than expected.
move.b    *,dN            move.b  *,dN
move.w    dN,aN           move.w  dN,aN
moveq[.l] #0,dN
move.w    aN,dN
move.l    dN,aN
```

```asm
This pattern comes up after applying optimization for lsl.w #8,dN.
clr.w   dN            ->   move.b  disp(aN),-(sp)    ; Saves 12 cycles
move.b  disp(aN),dN        move.w  (sp)+,dN
move.b  dN,-(sp)           move.b  dM,dN
move.w  (sp)+,dN
clr.b   dN
move.b  dM,dN
```

```asm
Calculates offset indexes for accessing arrays.
moveq[.l]  #0,dN              ->    move.w     disp(sp),dN       ; Saves 8 cycles
move.w     disp(sp),dN              move.w     dN,dM
move.l     dN,dM                    add/sub.w  dN,dM
add/sub.l  dN,dM                    lea        symbol_or_mem,aN
lea        symbol_or_mem,aN         move.[wl]  (aN,dM.w),dP
move.[wl]  (aN,dM.[wl]),dP
Where:
  symbol_or_mem[.wl][-+N][.bwl]
  dP can be dN
```

```asm
Calculate a long value from a word value.
moveq[.wl]   #0,dN         ->    moveq      #0,dN                ; Saves 4 cycles
move.w       aN,dN               move.w     aN,dN
move.l       dN,aN               add/sub.l  #val,dN
add*/sub*.l  #val,aN             add/sub.l  dN,dM
add/sub.l    aN,dM               move.l     dM,disp(aM)
move.l       dM,disp(aM)
Make sure dN/aN is not used before is cleared/overwitten.
```


## `optimizeMultiLines_7`

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s <ea>,dN                 ->    any_instr.s <ea>,dN       ; Saves 4 cycles
... instructions not modifying dN         ...
... and not modifying CCR: N,Z,V,C        ...
... and none of bra/jmp/bsr/jsr           ...
tst.s  dN                                 bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s <ea>,dN      ->    any_instr_B.s [<ea>,]dM            ; Saves 4 cycles
any_instr_B.s [<ea>,]dM          any_instr_C.s [<ea>,]dP
any_instr_C.s [<ea>,]dP          any_instr_D.s [<ea>,]dQ
any_instr_D.s [<ea>,]dQ          any_instr_E.s [<ea>,]dR
any_instr_E.s [<ea>,]dR          any_instr_A.s <ea>,dN
tst.s  dN                        bCC    label
bCC    label
Ensure dN is not used in the other instructions, and dM/dP/dQ/dR is not used in the first instruction.
```

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s  dN                      ->    any_instr.s  dN          ; Saves 4 cycles
... instructions not modifying dN          ...
... and not modifying CCR: N,Z,V,C         ...
... and none of bra/jmp/bsr/jsr            ...
tst.s  dN                                  bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s  dN          ->    any_instr_B.s  [<ea>,]dM           ; Saves 4 cycles
any_instr_B.s  [<ea>,]dM         any_instr_C.s  [<ea>,]dP
any_instr_C.s  [<ea>,]dP         any_instr_D.s  [<ea>,]dQ
any_instr_D.s  [<ea>,]dQ         any_instr_E.s  [<ea>,]dR
any_instr_E.s  [<ea>,]dR         any_instr_A.s  dN
tst.s  dN                        bCC    label
bCC    label
Ensure dN is not used in the other instruction, and dM/dP/dQ/dR are not used in the first instruction.
```

```asm
Consecutive copy of memory into a single invariant memory target.
move.s disp1(aN),(aM)      ->      move.s  (aN)+,(aM)               ; Saves [16,20] cycles
move.s disp2(aN),(aM)              move.s -(aN)+,(aM)
move.s disp3(aN),(aM)              move.s -(aN)+,(aM)
move.s disp4(aN),(aM)              move.s -(aN)+,(aM)
move.s disp5(aN),(aM)              move.s -(aN)+,(aM)
move.s disp6(aN),(aM)              move.s -(aN)+,(aM)
lea    val(aN),aN                  lea    val-N*s(aN),aN
Where s is w/l
```

```asm
Consecutively push into stack a sequence of registers.
move.[wl]  xN7,-(aN)   ->   movem.[wl]  xN7/xN6/xN5/xN4/xN3/xN2/xN1,-(aN)    ; Saves 20 cycles
move.[wl]  xN6,-(aN)
move.[wl]  xN5,-(aN)
move.[wl]  xN4,-(aN)
move.[wl]  xN3,-(aN)
move.[wl]  xN2,-(aN)
move.[wl]  xN1,-(aN)
IMPORTANT: movem.l regs,-(An) starts reading reg r7 and goes down to r0.
```

```asm
Consecutively pop from stack into a sequence of registers.
move.[wl]  (aN)+,xN1   ->   movem.[wl]  (aN)+,xN1/xN2/xN3/xN4/xN5/xN6/xN7    ; Saves 16 cycles
move.[wl]  (aN)+,xN2
move.[wl]  (aN)+,xN3
move.[wl]  (aN)+,xN4
move.[wl]  (aN)+,xN5
move.[wl]  (aN)+,xN6
move.[wl]  (aN)+,xN7
```

```asm
Move consecutive words or longs with fixed stride.
move.[wl]  disp1(aN),xN    ->   movem.[wl] disp1(aN),xN/xM/xP/xQ/xR/xS/xT    ; Saves 20 cycles
move.[wl]  disp2(aN),xM         (6th line here if it didn't satisfy the criteria)
move.[wl]  disp3(aN),xP
move.[wl]  disp4(aN),xQ
move.[wl]  disp5(aN),xR
move.[wl]  disp6(aN),xS
move.[wl]  disp7(aN),xT    <- this could be whatever line
aN is address register or sp.
Where disp1 to disp7 are consecutive displacements with the correct stride: +2 for word, +4 for long.
Where xN,xM,xP,xQ,xR,xS,xT are already sorted by data reg type and then address reg type, with consecutive reg index per type.
```

```asm
Move consecutive words or longs with fixed stride but unordered target regs.
move.[wl]  disp1(aN),xN    ->   movem.[wl]  disp1(sp),<sorted_regs>          ; Saves [10,16,26,32,38] cycles.
move.[wl]  disp2(aN),xM         exg         xA,xB
move.[wl]  disp3(aN),xP         exg         xC,xD  <-- optional, depending on regs list
move.[wl]  disp4(aN),xQ         exg         xE,xF  <-- optional, depending on regs list
move.[wl]  disp5(aN),xR         exg         xG,xH  <-- optional, depending on regs list
move.[wl]  disp6(aN),xS         exg         xI,xJ  <-- optional, depending on regs list
move.[wl]  disp7(aN),xT
aN is address register or sp.
Where disp1 to disp7 are increasing displacements.
Where xN,xM,xP,xQ,xR,xS,xT are unsorted data/address regs.
```


## `optimizeMultiLines_8`

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s <ea>,dN                 ->    any_instr.s <ea>,dN       ; Saves 4 cycles
... instructions not modifying dN         ...
... and not modifying CCR: N,Z,V,C        ...
... and none of bra/jmp/bsr/jsr           ...
tst.s  dN                                 bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s <ea>,dN      ->    any_instr_B.s [<ea>,]dM            ; Saves 4 cycles
any_instr_B.s [<ea>,]dM          any_instr_C.s [<ea>,]dP
any_instr_C.s [<ea>,]dP          any_instr_D.s [<ea>,]dQ
any_instr_D.s [<ea>,]dQ          any_instr_E.s [<ea>,]dR
any_instr_E.s [<ea>,]dR          any_instr_F.s [<ea>,]dS
any_instr_F.s [<ea>,]dS          any_instr_A.s <ea>,dN
tst.s  dN                        bCC    label
bCC    label
Ensure dN is not used in the other instructions, and dM/dP/dQ/dR/dS is not used in the first instruction.
```

```asm
Redundant tst instruction.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
any_instr.s  dN                      ->    any_instr.s  dN          ; Saves 4 cycles
... instructions not modifying dN          ...
... and not modifying CCR: N,Z,V,C         ...
... and none of bra/jmp/bsr/jsr            ...
tst.s  dN                                  bCC    label
bCC    label
```

```asm
Redundant tst instruction with instruction re order.
Some m68k instructions set condition codes, but GCC often generates redundant tst instructions before branches.
In this particular case we can re order the first instruction so the optimization may apply.
any_instr_A.s  dN          ->    any_instr_B.s  [<ea>,]dM           ; Saves 4 cycles
any_instr_B.s  [<ea>,]dM         any_instr_C.s  [<ea>,]dP
any_instr_C.s  [<ea>,]dP         any_instr_D.s  [<ea>,]dQ
any_instr_D.s  [<ea>,]dQ         any_instr_E.s  [<ea>,]dR
any_instr_D.s  [<ea>,]dR         any_instr_F.s  [<ea>,]dS
any_instr_E.s  [<ea>,]dS         any_instr_A.s  dN
tst.s  dN                        bCC    label
bCC    label
Ensure dN is not used in the other instruction, and dM/dP/dQ/dR/dS are not used in the first instruction.
```

```asm
Consecutive copy of memory into a single invariant memory target.
move.s disp1(aN),(aM)      ->      move.s  (aN)+,(aM)               ; Saves [20,24] cycles
move.s disp2(aN),(aM)              move.s -(aN)+,(aM)
move.s disp3(aN),(aM)              move.s -(aN)+,(aM)
move.s disp4(aN),(aM)              move.s -(aN)+,(aM)
move.s disp5(aN),(aM)              move.s -(aN)+,(aM)
move.s disp6(aN),(aM)              move.s -(aN)+,(aM)
move.s disp7(aN),(aM)              move.s -(aN)+,(aM)
lea    val(aN),aN                  lea    val-N*s(aN),aN
Where s is w/l
```


## `muls_high_word_important`

```asm
muls.w  #0,dN     ->   moveq  #0,dN     ; Saves 38 cycles
```

```asm
muls.w  #1,dN     ->   ext.l  dN        ; Saves 42 cycles
```

```asm
muls.w  #2,dN     ->   ext.l  dN        ; Saves 34 cycles
                       add.l  dN,dN
```

```asm
muls.w  #3,dN     ->   ext.l   dN       ; Saves 24 cycles
                       move.l  dN,dM
                       add.l   dN,dN
                       add.l   dM,dN
```

```asm
muls.w  #4,dN     ->   ext.l  dN        ; Saves 30 cycles
                       asl.l  #2,dN
```

```asm
muls.w  #7,dN     ->   ext.l   dN       ; Saves 20 cycles
                       move.l  dN,dM
                       asl.l   #3,dN
                       sub.l   dM,dN
```

```asm
muls.w  #8,dN     ->   ext.l  dN        ; Saves 28 cycles
                       asl.l  #3,dN
```

```asm
muls.w  #9,dN     ->   ext.l   dN       ; Saves 20 cycles
                       move.l  dN,dM
                       asl.l   #3,dN
                       add.l   dM,dN
```

```asm
muls.w  #10,dN    ->   ext.l   dN       ; Saves 14 cycles
                       move.l  dN,dM
                       asl.l   #2,dN
                       add.l   dM,dN
                       add.l   dN,dN
```

```asm
muls.w  #11,dN    ->   ext.l   dN       ; Saves 16 cycles
                       move.l  dN,dM
                       add.l   dM,dN
                       add.l   dM,dN
                       asl.l   #2,dN
                       sub.l   dM,dN
```

```asm
muls.w  #12,dN    ->   ext.l   dN       ; Saves 4 cycles
                       move.l  dN,dM
                       add.l   dM,dN
                       add.l   dM,dN
                       asl.l   #2,dN
```

```asm
muls.w  #13,dN    ->   ext.l   dN       ; Saves 8 cycles
                       move.l  dN,dM
                       add.l   dM,dN
                       add.l   dM,dN
                       asl.l   #2,dN
                       add.l   dM,dN
```

```asm
muls.w  #14,dN    ->   ext.l   dN       ; Saves 12 cycles
                       move.l  dN,dM
                       asl.l   #3,dN
                       sub.l   dM,dN
                       add.l   dN,dN
```

```asm
muls.w  #15,dN    ->   ext.l   dN       ; Saves 20 cycles
                       move.l  dN,dM
                       asl.l   #4,dN
                       sub.l   dM,dN
```

```asm
muls.w  #16,dN    ->   ext.l  dN        ; Saves 26 cycles
                       asl.l  #4,dN
```

```asm
muls.w  #17,dN    ->   ext.l   dN       ; Saves 18 cycles
                       move.l  dN,dM
                       asl.l   #4,dN
                       add.l   dM,dN
```

```asm
muls.w  #18,dN    ->   ext.l   dN       ; Saves 12 cycles
                       add.l   dN,dN
                       move.l  dN,dM
                       asl.l   #3,dN
                       add.l   dM,dN
```

```asm
muls.w  #19,dN    ->   ext.l   dN       ; Saves 6 cycles
                       move.l  dN,dM
                       asl.l   #3,dN
                       add.l   dM,dN
                       add.l   dN,dN
                       add.l   dM,dN
```

```asm
muls.w  #20,dN    ->   ext.l   dN       ; Saves 10 cycles
                       move.l  dN,dM
                       asl.l   #2,dN
                       add.l   dM,dN
                       asl.l   #2,dN
```

```asm
muls.w  #21,dN    ->   ext.l   dN       ; Saves 6 cycles
                       move.l  dN,dM
                       asl.l   #2,dN
                       add.l   dM,dN
                       asl.l   #2,dN
                       add.l   dM,dN
```

```asm
muls.w  #22,dN    ->   ext.l   dN       ; Saves 8 cycles
                       add.l   dN,dN
                       move.l  dN,dM
                       add.l   dM,dN
                       add.l   dM,dN
                       asl.l   #2,dN
                       sub.l   dM,dN
```

```asm
muls.w  #23,dN    ->   ext.l   dN       ; Saves 6 cycles
                       move.l  dN,dM
                       add.l   dM,dN
                       add.l   dM,dN
                       asl.l   #3,dN
                       sub.l   dM,dN
```

```asm
muls.w  #24,dN    ->   ext.l   dN       ; Saves 8 cycles
                       move.l  dN,dM
                       add.l   dM,dN
                       add.l   dM,dN
                       asl.l   #3,dN
```

```asm
muls.w  #25,dN    ->   ext.l   dN       ; Saves 4 cycles
                       move.l  dN,dM
                       add.l   dM,dN
                       add.l   dM,dN
                       asl.l   #3,dN
                       add.l   dM,dN
```

```asm
muls.w  #26,dN    ->   ext.l   dN       ; Saves 4 cycles
                       move.l  dN,dM
                       add.l   dM,dM
                       add.l   dM,dN
                       asl.l   #3,dN
                       add.l   dM,dN
```

```asm
muls.w  #29,dN    ->   ext.l   dN       ; Saves 4 cycles
                       move.l  dN,dM
                       asl.l   #5,dN
                       sub.l   dM,dN
                       sub.l   dM,dN
                       sub.l   dM,dN
```

```asm
muls.w  #30,dN    ->   ext.l   dN       ; Saves 10 cycles
                       move.l  dN,dM
                       asl.l   #5,dN
                       sub.l   dM,dN
                       sub.l   dM,dN
```

```asm
muls.w  #31,dN    ->   ext.l   dN       ; Saves 20 cycles
                       move.l  dN,dM
                       asl.l   #5,dN
                       sub.l   dM,dN
```

```asm
muls.w  #32,dN    ->   ext.l  dN        ; Saves 24 cycles
                       asl.l  #5,dN
```

```asm
muls.w  #33,dN    ->   ext.l   dN       ; Saves 16 cycles
                       move.l  dN,dM
                       asl.l   #5,dN
                       add.l   dM,dN
```

```asm
muls.w  #34,dN    ->   ext.l   dN       ; Saves 8 cycles
                       move.l  dN,dM
                       asl.l   #5,dN
                       add.l   dM,dN
                       add.l   dM,dN
```

```asm
muls.w  #35,dN    ->   ext.l   dN       ; Saves 2 cycles
                       move.l  dN,dM
                       asl.l   #5,dN
                       add.l   dM,dN
                       add.l   dM,dN
                       add.l   dM,dN
```

```asm
muls.w  #64,dN    ->   ext.l  dN        ; Saves 22 cycles
                       asl.l  #6,dN
```

```asm
muls.w  #128,dN    ->  ext.l  dN        ; Saves 20 cycles
                       asl.l  #7,dN
```

```asm
muls.w  #256,dN    ->  ext.l  dN        ; Saves 18 cycles
                       asl.l  #8,dN
```


## `mulu_high_word_important`

```asm
mulu.w  #0,dN     ->   moveq   #0,dN    ; Saves 38 cycles
```

```asm
mulu.w  #1,dN     ->   moveq   #0,dM    ; Saves 36 cycles
                       move.w  dN,dM
```

```asm
mulu.w  #2,dN     ->   moveq   #0,dM    ; Saves 28 cycles
                       move.w  dN,dM
                       add.l   dM,dM
```

```asm
mulu.w  #3,dN     ->   moveq   #0,dM    ; Saves 18 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       add.l   dM,dM
                       add.l   dN,dM
```

```asm
mulu.w  #4,dN     ->   moveq   #0,dM    ; Saves 24 cycles
                       move.w  dN,dM
                       lsl.l   #2,dM
```

```asm
mulu.w  #5,dN     ->   moveq   #0,dM    ; Saves 14 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #2,dM
                       add.l   dN,dM
```

```asm
mulu.w  #6,dN     ->   moveq   #0,dM    ; Saves 10 cycles
                       move.w  dN,dM
                       add.l   dM,dM
                       move.l  dM,dN
                       add.l   dM,dM
                       add.l   dN,dM
```

```asm
mulu.w  #7,dN     ->   moveq   #0,dM    ; Saves 14 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #3,dM
                       sub.l   dN,dM
```

```asm
mulu.w  #8,dN     ->   moveq   #0,dM     ; Saves 22 cycles
                       move.w  dN,dM
                       lsl.l   #3,dM
```

```asm
mulu.w  #9,dN     ->   moveq   #0,dM    ; Saves 12 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #3,dM
                       add.l   dN,dM
```

```asm
mulu.w  #10,dN    ->   moveq   #0,dM    ; Saves 6 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #2,dM
                       add.l   dN,dM
                       add.l   dM,dM
```

```asm
mulu.w  #11,dN    ->   moveq   #0,dM    ; Saves 8 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       add.l   dN,dM
                       add.l   dN,dM
                       lsl.l   #2,dM
                       sub.l   dN,dM
```

```asm
mulu.w  #14,dN    ->   moveq   #0,dM    ; Saves 6 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #3,dM
                       sub.l   dN,dM
                       add.l   dM,dM
```

```asm
mulu.w  #15,dN    ->   moveq   #0,dM    ; Saves 14 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #4,dM
                       sub.l   dN,dM
```

```asm
mulu.w  #16,dN    ->   moveq   #0,dM    ; Saves 20 cycles
                       move.w  dN,dM
                       lsl.l   #4,dM
```

```asm
mulu.w  #17,dN    ->   moveq   #0,dM    ; Saves 10 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #4,dM
                       add.l   dN,dM
```

```asm
mulu.w  #18,dN    ->   moveq   #0,dM    ; Saves 4 cycles
                       move.w  dN,dM
                       add.l   dM,dM
                       move.l  dM,dN
                       lsl.l   #3,dM
                       add.l   dN,dM
```

```asm
mulu.w  #20,dN    ->   moveq   #0,dM    ; Saves 2 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #2,dM
                       add.l   dN,dM
                       lsl.l   #2,dM
```

```asm
mulu.w  #24,dN    ->   moveq   #0,dM    ; Saves 4 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       add.l   dM,dM
                       add.l   dN,dM
                       lsl.l   #3,dM
```

```asm
mulu.w  #30,dN    ->   moveq   #0,dM    ; Saves 4 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #5,dM
                       sub.l   dN,dM
                       sub.l   dN,dM
```

```asm
mulu.w  #31,dN    ->   moveq   #0,dM    ; Saves 14 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #5,dM
                       sub.l   dN,dM
```

```asm
mulu.w  #32,dN    ->   moveq   #0,dM    ; Saves 18 cycles
                       move.w  dN,dM
                       lsl.l   #5,dM
```

```asm
mulu.w  #33,dN    ->   moveq   #0,dM    ; Saves 8 cycles
                       move.w  dN,dM
                       move.l  dM,dN
                       lsl.l   #5,dM
                       add.l   dN,dM
```

```asm
mulu.w  #64,dN    ->   moveq   #0,dM    ; Saves 16 cycles
                       move.w  dN,dM
                       lsl.l   #6,dM
```

```asm
mulu.w  #128,dN   ->   moveq   #0,dM    ; Saves 14 cycles
                       move.w  dN,dM
                       lsl.l   #7,dM
```

```asm
mulu.w  #256,dN   ->   moveq   #0,dM    ; Saves 12 cycles
                       move.w  dN,dM
                       lsl.l   #8,dM
```


## `muls_high_word_not_important`

```asm
muls.w  #0,dN   ->   moveq  #0,dN      ; Saves 38 cycles
```

```asm
muls.w  #1,dN   ->   remove line       ; Saves 38 cycles
```

```asm
muls.w  #2,dN   ->   add.w   dN,dN     ; Saves 42 cycles
```

```asm
muls.w  #3,dN   ->   move.w  dN,dM     ; Saves 36 cycles
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #4,dN   ->   add.w   dN,dN     ; Saves 38 cycles
                     add.w   dN,dN
```

```asm
muls.w  #5,dN   ->   move.w  dN,dM     ; Saves 34 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #6,dN   ->   add.w   dN,dN     ; Saves 32 cycles
                     move.w  dN,dM
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #7,dN   ->   move.w  dN,dM     ; Saves 30 cycles
                     asl.w   #3,dN
                     sub.w   dM,dN
```

```asm
muls.w  #8,dN   ->    asl.w  #3,dN     ; Saves 34 cycles
```

```asm
muls.w  #9,dN   ->   move.w  dN,dM     ; Saves 30 cycles
                     asl.w   #3,dN
                     add.w   dM,dN
```

```asm
muls.w  #10,dN  ->   move.w  dN,dM     ; Saves 30 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
```

```asm
muls.w  #11,dN  ->   move.w  dN,dM     ; Saves 28 cycles
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     sub.w   dM,dN
```

```asm
muls.w  #12,dN  ->   move.w  dN,dM     ; Saves 28 cycles
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
muls.w  #13,dN  ->   move.w  dN,dM     ; Saves 28 cycles
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #14,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     asl.w   #3,dN
                     sub.w   dM,dN
                     add.w   dN,dN
```

```asm
muls.w  #15,dN  ->   move.w  dN,dM     ; Saves 30 cycles
                     asl.w   #4,dN
                     sub.w   dM,dN
```

```asm
muls.w  #16,dN  ->   asl.w  #4,dN      ; Saves 32 cycles
```

```asm
muls.w  #17,dN  ->   move.w  dN,dM     ; Saves 28 cycles
                     asl.w   #4,dN
                     add.w   dM,dN
```

```asm
muls.w  #18,dN  ->   add.w   dN,dN     ; Saves 26 cycles
                     move.w  dN,dM
                     asl.w   #3,dN
                     add.w   dM,dN
```

```asm
muls.w  #19,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     asl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #20,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
muls.w  #21,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #22,dN  ->   add.w   dN,dN     ; Saves 24 cycles
                     move.w  dN,dM
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     sub.w   dM,dN
```

```asm
muls.w  #23,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     sub.w   dM,dN
```

```asm
muls.w  #24,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
```

```asm
muls.w  #25,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     add.w   dM,dN
```

```asm
muls.w  #26,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     add.w   dM,dM
                     add.w   dM,dN
                     asl.w   #3,dN
                     add.w   dM,dN
```

```asm
muls.w  #27,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     asl.w   #3,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     sub.w   dM,dN
```

```asm
muls.w  #28,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     asl.w   #3,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
muls.w  #29,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     asl.w   #5,dN
                     sub.w   dM,dN
                     sub.w   dM,dN
                     sub.w   dM,dN
```

```asm
muls.w  #30,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     asl.w   #5,dN
                     sub.w   dM,dN
                     sub.w   dM,dN
```

```asm
muls.w  #31,dN  ->   move.w  dN,dM     ; Saves 30 cycles
                     asl.w   #5,dN
                     sub.w   dM,dN
```

```asm
muls.w  #32,dN   ->    asl.w  #5,dN    ; Saves 30 cycles
```

```asm
muls.w  #33,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     asl.w   #5,dN
                     add.w   dM,dN
```

```asm
muls.w  #34,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     asl.w   #5,dN
                     add.w   dM,dN
                     add.w   dM,dN
```

```asm
muls.w  #35,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     asl.w   #5,dN
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dM,dN
```

```asm
muls.w  #36,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     asl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
muls.w  #37,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     asl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #38,dN  ->   add.w   dN,dN     ; Saves 20 cycles
                     move.w  dN,dM
                     asl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
muls.w  #39,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     asl.w   #3,dN
                     sub.w   dM,dN
```

```asm
muls.w  #40,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     asl.w   #3,dN
```

```asm
muls.w  #41,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     asl.w   #3,dN
                     add.w   dM,dN
```

```asm
muls.w  #42,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     add.w   dM,dM
                     add.w   dM,dN
                     add.w   dM,dN
                     asl.w   #3,dN
                     add.w   dM,dN
```

```asm
muls.w  #64,dN  ->   asl.w  #6,dN      ; Saves 28 cycles
```

```asm
muls.w  #128,dN   ->   asl.w  #7,dN    ; Saves 26 cycles
```

```asm
muls.w  #256,dN   ->   asl.w  #8,dN    ; Saves 24+2 cycles
                                       ; It can be optimized like lsl.w #8, there 2 more saved cycles
```


## `mulu_high_word_not_important`

```asm
mulu.w  #0,dN   ->   moveq  #0,dN      ; Saves 38 cycles
```

```asm
mulu.w  #1,dN   ->   remove line       ; Saves 44 cycles
```

```asm
mulu.w  #2,dN   ->   add.w   dN,dN     ; Saves 40 cycles
```

```asm
mulu.w  #3,dN   ->   move.w  dN,dM     ; Saves 34 cycles
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #4,dN   ->   add.w   dN,dN     ; Saves 36 cycles
                     add.w   dN,dN
```

```asm
mulu.w  #5,dN   ->   move.w  dN,dM     ; Saves 30 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #6,dN   ->   add.w   dN,dN     ; Saves 30 cycles
                     move.w  dN,dM
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #7,dN   ->   move.w  dN,dM     ; Saves 28 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #8,dN   ->    lsl.w  #3,dN     ; Saves 32 cycles
```

```asm
mulu.w  #9,dN   ->   move.w  dN,dM     ; Saves 26 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
```

```asm
mulu.w  #10,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #11,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #12,dN  ->   move.w  dN,dM     ; Saves 26 cycles
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #13,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #14,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #15,dN  ->   move.w  dN,dM     ; Saves 28 cycles
                     lsl.w   #4,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #16,dN  ->   lsl.w  #4,dN      ; Saves 30 cycles
```

```asm
mulu.w  #17,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     lsl.w   #4,dN
                     add.w   dM,dN
```

```asm
mulu.w  #18,dN  ->   add.w   dN,dN     ; Saves 22 cycles
                     move.w  dN,dM
                     lsl.w   #3,dN
                     add.w   dM,dN
```

```asm
mulu.w  #19,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #20,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #21,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #22,dN  ->   add.w   dN,dN     ; Saves 20 cycles
                     move.w  dN,dM
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #23,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #24,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #25,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     add.w   dM,dN
```

```asm
mulu.w  #26,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     add.w   dM,dM
                     add.w   dM,dN
                     lsl.w   #3,dN
                     add.w   dM,dN
```

```asm
mulu.w  #27,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #28,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #29,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     lsl.w   #5,dN
                     sub.w   dM,dN
                     sub.w   dM,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #30,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     lsl.w   #5,dN
                     sub.w   dM,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #31,dN  ->   move.w  dN,dM     ; Saves 28 cycles
                     lsl.w   #5,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #32,dN   ->    lsl.w  #5,dN    ; Saves 28 cycles
```

```asm
mulu.w  #33,dN  ->   move.w  dN,dM     ; Saves 22 cycles
                     lsl.w   #5,dN
                     add.w   dM,dN
```

```asm
mulu.w  #34,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     lsl.w   #5,dN
                     add.w   dM,dN
                     add.w   dM,dN
```

```asm
mulu.w  #35,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     lsl.w   #5,dN
                     add.w   dM,dN
                     add.w   dM,dN
                     add.w   dM,dN
```

```asm
mulu.w  #36,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #37,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #38,dN  ->   add.w   dN,dN     ; Saves 16 cycles
                     move.w  dN,dM
                     lsl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #39,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #40,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #41,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     add.w   dM,dN
```

```asm
mulu.w  #42,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     add.w   dM,dM
                     add.w   dM,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     add.w   dM,dN
```

```asm
mulu.w  #44,dN  ->   move.w  dN,dM     ; Saves 14 cycles
                     add.w   dM,dM
                     add.w   dM,dN
                     lsl.w   #4,dN
                     add.w   dM,dM
                     sub.w   dM,dN
```

```asm
mulu.w  #45,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     add.w   dN,dN
                     add.w   dN,dM
                     move.w  dM,dN
                     lsl.w   #4,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #46,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     add.w   dM,dM
                     add.w   dM,dN
                     lsl.w   #4,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #48,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #49,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
                     add.w   dM,dN
```

```asm
mulu.w  #56,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #60,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     lsl.w   #4,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #62,dN  ->   move.w  dN,dM     ; Saves 24 cycles
                     lsl.w   #5,dN
                     sub.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #63,dN  ->   move.w  dN,dM     ; Saves 28 cycles
                     lsl.w   #6,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #64,dN  ->   lsl.w   #6,dN     ; Saves 26 cycles
```

```asm
mulu.w  #65,dN  ->   move.w  dN,dM     ; Saves 20 cycles
                     lsl.w   #6,dN
                     add.w   dM,dN
```

```asm
mulu.w  #66,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     lsl.w   #5,dN
                     add.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #68,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     lsl.w   #4,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #72,dN  ->   move.w  dN,dM     ; Saves 14 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #80,dN  ->   move.w  dN,dM     ; Saves 16 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #84,dN  ->   move.w  dN,dM     ; Saves 12 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #92,dN  ->   move.w  dN,dM     ; Saves 14 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #96,dN  ->   move.w  dN,dM     ; Saves 18 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #5,dN
```

```asm
mulu.w  #112,dN ->   move.w  dN,dM     ; Saves 14 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #120,dN ->   move.w  dN,dM     ; Saves 16 cycles
                     lsl.w   #4,dN
                     sub.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #124,dN ->   move.w  dN,dM     ; Saves 20 cycles
                     lsl.w   #5,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #126,dN ->   move.w  dN,dM     ; Saves 24 cycles
                     lsl.w   #6,dN
                     sub.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #127,dN ->   move.w  dN,dM     ; Saves 28 cycles
                     lsl.w   #7,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #128,dN ->   lsl.w   #7,dN     ; Saves 24 cycles
```

```asm
mulu.w  #129,dN ->   move.w  dN,dM     ; Saves 18 cycles
                     lsl.w   #7,dN
                     add.w   dM,dN
```

```asm
mulu.w  #130,dN ->   move.w  dN,dM     ; Saves 16 cycles
                     lsl.w   #6,dN
                     add.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #132,dN ->   move.w  dN,dM     ; Saves 14 cycles
                     lsl.w   #5,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #136,dN ->   move.w  dN,dM     ; Saves 12 cycles
                     lsl.w   #4,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #144,dN ->   move.w  dN,dM     ; Saves 12 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #156,dN ->   move.w  dN,dM     ; Saves 14 cycles
                     add.w   dM,dM
                     add.w   dM,dM
                     add.w   dM,dN
                     lsl.w   #5,dN
                     sub.w   dM,dN
```

```asm
mulu.w  #160,dN ->   move.w  dN,dM     ; Saves 14 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #5,dN
```

```asm
mulu.w  #184,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #192,dN ->   move.w  dN,dM     ; Saves 16 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #6,dN
```

```asm
mulu.w  #196,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #200,dN ->   move.w  dN,dM     ; Saves 8 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #208,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #224,dN ->   move.w  dN,dM     ; Saves 12 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     lsl.w   #5,dN
```

```asm
mulu.w  #240,dN ->   move.w  dN,dM     ; Saves 14 cycles
                     lsl.w   #4,dN
                     sub.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #248,dN ->   move.w  dN,dM     ; Saves 16 cycles
                     lsl.w   #5,dN
                     sub.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #252,dN ->   move.w  dN,dM     ; Saves 20 cycles
                     lsl.w   #6,dN
                     sub.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #254,dN ->   move.w  dN,dM     ; Saves 24 cycles
                     lsl.w   #7,dN
                     sub.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #255,dN ->   move.w  dN,dM        ; Saves 30 cycles
                     move.b  dN,-(%sp)    ; lsl.w #8,dN replaced by these 3 (20 cycles instead of 22)
                     move.w  (%sp)+,dN
                     clr.b   dN
                     sub.w   dM,dN
```

```asm
mulu.w  #256,dN ->   move.b  dN,-(%sp)    ; Saves 22+2 cycles
                     move.w  (%sp)+,dN    ; lsl.w #8 is optimized by the replacement, there 2 more saved cycles.
                     clr.b   dN
```

```asm
mulu.w  #257,dN ->   move.w  dN,dM        ; Saves 18 cycles
                     move.b  dN,-(%sp)    ; lsl.w #8,dN replaced by these 3 (20 cycles instead of 22)
                     move.w  (%sp)+,dN
                     clr.b   dN
                     add.w   dM,dN
```

```asm
mulu.w  #258,dN ->   move.w  dN,dM     ; Saves 14 cycles
                     lsl.w   #7,dN
                     add.w   dM,dN
                     add.w   dN,dN
```

```asm
mulu.w  #260,dN ->   move.w  dN,dM     ; Saves 12 cycles
                     lsl.w   #6,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #264,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     lsl.w   #5,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #272,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     lsl.w   #4,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #288,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     lsl.w   #5,dN
```

```asm
mulu.w  #304,dN ->   move.w  dN,dM     ; Saves 6 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #320,dN ->   move.w  dN,dM     ; Saves 12 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #6,dN
```

```asm
mulu.w  #384,dN ->   move.w  dN,dM     ; Saves 14 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #7,dN
```

```asm
mulu.w  #400,dN ->   move.w  dN,dM     ; Saves 6 cycles
                     lsl.w   #3,dN
                     add.w   dN,dM
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #416,dN ->   move.w  dN,dM     ; Saves 8 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dN,dM
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #5,dN
```

```asm
mulu.w  #480,dN ->   move.w  dN,dM     ; Saves 12 cycles
                     lsl.w   #4,dN
                     sub.w   dM,dN
                     lsl.w   #5,dN
```

```asm
mulu.w  #512,dN ->   move.b  dN,-(%sp)    ; Saves 20 cycles
                     move.w  (%sp)+,dN    ; (lsl.w #8,dN replaced by the first 3 instructions)
                     clr.b   dN
                     add.w   dN,dN
```

```asm
mulu.w  #576,dN ->   move.w  dN,dM     ; Saves 8 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     lsl.w   #6,dN
```

```asm
mulu.w  #608,dN ->   move.w  dN,dM     ; Saves 4 cycles
                     lsl.w   #3,dN
                     add.w   dM,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #5,dN
```

```asm
mulu.w  #624,dN ->   move.w  dN,dM     ; Saves 4 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     lsl.w   #4,dN
```

```asm
mulu.w  #625,dN ->   move.w  dN,dM     ; Saves 2 cycles
                     lsl.w   #4,dN
                     sub.w   dN,dM
                     lsl.w   #3,dN
                     add.w   dN,dM
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
```

```asm
mulu.w  #640,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     lsl.w   #7,dN
```

```asm
mulu.w  #768,dN ->   move.w  dN,dM        ; Saves 14 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     move.b  dN,-(%sp)    ; lsl.w #8,dN replaced by these 3 (20 cycles instead of 22)
                     move.w  (%sp)+,dN
                     clr.b   dN
```

```asm
mulu.w  #896,dN ->   move.w  dN,dM     ; Saves 8 cycles
                     lsl.w   #3,dN
                     sub.w   dM,dN
                     lsl.w   #7,dN
```

```asm
mulu.w  #960,dN ->   move.w  dN,dM     ; Saves 10 cycles
                     lsl.w   #4,dN
                     sub.w   dM,dN
                     lsl.w   #6,dN
```

```asm
mulu.w  #1024,dN ->  move.b  dN,-(%sp)     ; Saves 16 cycles
                     move.w  (%sp)+,dN     ; (lsl.w #8,dN replaced by the first 3 instructions)
                     clr.b   dN
                     add.w   dN,dN
                     add.w   dN,dN
```

```asm
mulu.w  #1280,dN ->  move.w  dN,dM        ; Saves 10 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     move.b  dN,-(%sp)    ; lsl.w #8,dN replaced by these 3 (20 cycles instead of 22)
                     move.w  (%sp)+,dN
                     clr.b   dN
```

```asm
mulu.w  #1920,dN ->  move.w  dN,dM     ; Saves 8 cycles
                     lsl.w   #4,dN
                     sub.w   dM,dN
                     lsl.w   #7,dN
```

```asm
mulu.w  #2048,dN ->  move.b  dN,-(%sp)     ; Saves 12 cycles
                     move.w  (%sp)+,dN     ; (lsl.w #8,dN replaced by the first 3 instructions)
                     clr.b   dN
                     lsl.w   #3,dN
```

```asm
mulu.w  #2560,dN ->  move.w  dN,dM        ; Saves 6 cycles
                     add.w   dN,dN
                     add.w   dN,dN
                     add.w   dM,dN
                     move.b  dN,-(%sp)    ; lsl.w #8,dN replaced by these 3 (20 cycles instead of 22)
                     move.w  (%sp)+,dN
                     clr.b   dN
                     add.w   dN,dN
```

```asm
mulu.w  #3072,dN ->  move.w  dN,dM        ; Saves 6 cycles
                     add.w   dN,dN
                     add.w   dM,dN
                     move.b  dN,-(%sp)    ; lsl.w #8,dN replaced by these 3 (20 cycles instead of 22)
                     move.w  (%sp)+,dN
                     clr.b   dN
                     add.w   dN,dN
                     add.w   dN,dN
```
