# Copyright © 2023 Collabora
# SPDX-License-Identifier: MIT

libpankmod_lib_files = files(
  'pan_kmod.c',
)

if panfrost_kmds.contains('panfrost')
  libpankmod_lib_files += files('panfrost_kmod.c')
endif

if panfrost_kmds.contains('panthor')
  libpankmod_lib_files += files('panthor_kmod.c')
endif

if panfrost_kmds.contains('kbase')
  libpankmod_lib_files += files('kbase_kmod.c')
endif

libpankmod_lib = static_library(
  'pankmod_lib',
  [libpankmod_lib_files],
  include_directories : [inc_include, inc_src, inc_panfrost],
  c_args : [no_override_init_args],
  gnu_symbol_visibility : 'hidden',
  dependencies: [dep_libdrm, idep_mesautil, idep_pan_packers, libpanfrost_model_dep],
  build_by_default : false,
)

libpankmod_dep = declare_dependency(
  include_directories: [inc_include, inc_src],
  dependencies: [dep_libdrm],
)
