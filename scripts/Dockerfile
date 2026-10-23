# Cross toolchain for the Gen2 (aarch64) build. Debian bookworm's glibc is 2.36, below the device's 2.39.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      g++-aarch64-linux-gnu gcc-aarch64-linux-gnu cmake ninja-build make ca-certificates \
      qemu-user-static binutils-aarch64-linux-gnu \
    && rm -rf /var/lib/apt/lists/*
