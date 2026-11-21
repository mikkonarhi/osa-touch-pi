# Local patches for linux-gpib

`install.sh` applies every `*.patch` here to the linux-gpib source before building it:

- `kernel/*.patch` to the `linux-gpib-kernel` tree
- `user/*.patch` to the `linux-gpib-user` tree

Patches must be in `-p1` form relative to the root of that tree (as produced by
`diff -ru a/ b/` or `git diff`). Each one is applied once; a patch that doesn't apply stops the
install with an error.

linux-gpib 4.3.7 (the installer default) already has the compatibility changes for recent
kernels, so normally this folder is empty. If a future Raspberry Pi kernel breaks the build, put
the fix here (or try `sudo ./install.sh --gpib-git` to build the latest linux-gpib from git).
