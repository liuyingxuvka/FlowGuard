# Real C++ source regression

`gtest-filepath.cc.txt` is the unchanged GoogleTest v1.16.0 file
[`googletest/src/gtest-filepath.cc`](https://github.com/google/googletest/blob/v1.16.0/googletest/src/gtest-filepath.cc),
Git blob `902d8c7f64b7c44d7bdfc2d6fa9420f5b796eac5`. Its copyright and
redistribution notice remain in the file. The `.txt` suffix keeps fixture data
separate from FlowGuard's own Python implementation; tests write its exact bytes
as `gtest-filepath.cc` in an isolated project and use the common source Map.

Both reference direct-initializers at lines 270–273 are valid C++. The packaged
tree-sitter-cpp grammar misreads them as erroneous function parameters. The reader
must decode their unchanged expression ranges, retain source positions and real
calls, and continue reporting genuine or uncovered syntax errors.
