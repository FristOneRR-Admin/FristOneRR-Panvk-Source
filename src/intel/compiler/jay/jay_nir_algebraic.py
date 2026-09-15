# Copyright 2024 Intel Corporation
# SPDX-License-Identifier: MIT

import argparse
import sys
from math import pi

a = 'a'
b = 'b'
c = 'c'

lower_fsign = [
    (('fsign', a), ('bcsel', ('!flt', 0, a), +1.0,
                    ('bcsel', ('!flt', a, 0), -1.0, 0.0))),
    (('fceil', a), ('fneg', ('ffloor', ('fneg', a)))),

    # inot is free on and/or/xor sources but not dests. Apply De Morgan's.
    (('inot', ('iand(is_used_once)', ('inot', a), b)), ('ior', a, ('inot', b))),
    (('inot', ('ior(is_used_once)', ('inot', a), b)), ('iand', a, ('inot', b))),
    (('inot', ('ixor(is_used_once)', ('inot', a), b)), ('ixor', a, b)),
    (('inot', ('iand(is_used_once)', a, b)), ('ior', ('inot', a), ('inot', b))),
    (('inot', ('ior(is_used_once)', a, b)), ('iand', ('inot', a), ('inot', b))),
    (('inot', ('ixor(is_used_once)', a, b)), ('ixor', ('inot', a), b)),

    # Remove the zeroing. Down-conversion is free but extracts are not.
    (('u2f32', ('extract_u8', a, 0)), ('u2f32', ('u2u8', a))),
    (('u2f32', ('extract_u16', a, 0)), ('u2f32', ('u2u16', a))),
    (('i2f32', ('extract_i8', a, 0)), ('i2f32', ('i2i8', a))),
    (('i2f32', ('extract_i16', a, 0)), ('i2f32', ('i2i16', a))),

    # Late multiplication handling
    (('iadd', ('imul_32x16(is_only_used_by_iadd)', a, b), c),
     ('imad_32x16_intel', a, b, c)),

    (('iadd', ('umul_32x16(is_only_used_by_iadd)', a, b), c),
     ('umad_32x16_intel', a, b, c)),

    (('iadd', ('imul(is_used_once)', 'a@32', '#b'), c),
     ('umad_32x16_intel', a, ('iand', b, 0xffff),
      ('umad_32x16_intel', ('iand', b, 0xffff0000), a, c))),

    (('imul', 'a@32', '#b'),
     ('umad_32x16_intel', a, ('iand', b, 0xffff),
      ('umul_32x16', ('iand', b, 0xffff0000), a))),

    (('pack_half_2x16_split', a, b),
     ('pack_32_2x16_split', ('f2f16', a), ('f2f16', b))),
]

for i in range(2, 15):
    lower_fsign.extend([
        (('iadd', ('ishl(is_only_used_by_iadd)', 'b@32', i), c),
         ('umad_32x16_intel', b, 1 << i, c)),
    ])


lower_bool = [
    # Try to use conditional modifiers more
    (('ieq', ('iand(is_used_once)', a, b), b),
     ('ieq', ('iand', ('inot', a), b), 0)),
    (('ine', ('iand(is_used_once)', a, b), b),
     ('ine', ('iand', ('inot', a), b), 0)),

    # Clean up after 1-bit phi lowering
    (('b2b32', ('b2b1', 'a@32')), a),

    # Turn boolean ops into bitwise logic to simplify the backend
    (('ine', 'a@1', 'b@1'), ('ixor', a, b)),
    (('ieq', 'a@1', 'b@1'), ('ixor', ('inot', a), b)),
    (('bcsel', 'a', 'b@1', 'c@1'), ('ior', ('iand', a, b), ('iand', ('inot', a), c))),

    # We do not support 64-bit bcsel, so lower special
    ((f'b2i64', 'a@1'), ('pack_64_2x32_split', ('bcsel', a, 1, 0), 0)),
]

for T, sizes, one in [('f', [16, 32], 1.0),
                      ('i', [8, 16, 32], 1),
                      ('b', [32], -1)]:
    for sz in sizes:
        if T in ['f', 'i']:
            lower_bool.extend([
                ((f'{T}neg', (f'b2{T}{sz}', ('inot', 'a@1'))),
                 ('bcsel', a, 0, -one)),
                ((f'{T}neg', (f'b2{T}{sz}', 'a@1')), ('bcsel', a, -one, 0)),
            ])

        lower_bool.extend([
            ((f'b2{T}{sz}', ('inot', 'a@1')), ('bcsel', a, 0, one)),
            ((f'b2{T}{sz}', 'a@1'), ('bcsel', a, one, 0)),
        ])


lower_bfloat_ops = [
    (('bfmul', a, b), ('bfmul_mixed_intel', a, ('bf2f', b))),
    (('bffma', a, b, c), ('bffma_mixed_intel', ('bf2f', a), b, c)),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--import-path', required=True)
    parser.add_argument('output')
    args = parser.parse_args()

    sys.path.insert(0, args.import_path)
    import nir_algebraic  # pylint: disable=import-error

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write('#include "jay_private.h"')

        f.write(nir_algebraic.AlgebraicPass(
            "jay_nir_lower_fsign", lower_fsign).render())
        f.write(nir_algebraic.AlgebraicPass(
            "jay_nir_lower_bool", lower_bool).render())
        f.write(nir_algebraic.AlgebraicPass(
            "jay_nir_lower_bfloat_math", lower_bfloat_ops).render())


if __name__ == '__main__':
    main()
