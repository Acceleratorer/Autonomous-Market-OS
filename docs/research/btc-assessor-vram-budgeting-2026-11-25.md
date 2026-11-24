# BTC Assessor VRAM Budgeting Options

**Checked:** 2026-11-25

**Scope:** Research only. No GPU or server was launched; no code, runtime, or firewall configuration was changed. No product decision is made here.

## Current Windows evidence

NVIDIA lists the GeForce RTX 5060 Laptop GPU with 8 GB GDDR7. That is the product specification, not a measurement of free VRAM on this workstation. The existing Windows assessor evidence reports a 2,048 MiB CUDA fit margin and explicitly marks `cuda_vram_hard_cap` false. The current checkout's 2026-11-25 health record did not start the server, so it adds no current GPU inventory or memory-use evidence. The earlier report does not record the GPU model; whether that run used this exact RTX 5060 Laptop GPU is unverified. See [NVIDIA's RTX 50 laptop specifications](https://www.nvidia.com/en-us/geforce/laptops/50-series/), the [prior Windows assessor evidence](../evidence/btc-local-assessor-windows-egress-2026-11-21.json), and the [current-checkout health evidence](../evidence/btc-local-assessor-current-checkout-health-2026-11-25.json).

The project sets `CUDA_FREE_MEMORY_MARGIN_MIB = 2048` and passes `--fit on --fit-target 2048` to llama.cpp ([assessor source](../../market_os/btc_local_assessor.py#L55), [launch arguments](../../market_os/btc_local_assessor.py#L735)). Its Windows Job Object commit limit covers host process memory; the existing evidence records no working-set limit and no CUDA VRAM hard cap.

## What llama.cpp controls

- `--fit` estimates model/context placement from currently free device memory and adjusts parameters to leave a configured margin. `--fit-target` is that margin, not a quota: it cannot reserve or enforce a fixed VRAM ceiling against other GPU users. The project's current 2,048 MiB value is therefore adaptive headroom, not a hard cap. See the upstream [`fit-params` documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/fit-params/README.md) and [server options](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
- `--gpu-layers N` limits how many model layers are placed in VRAM. This can reduce model-weight offload, but does not impose a total device-memory limit on all buffers. `--device none` fully disables GPU acceleration; `--gpu-layers 0` alone may still allow some GPU work. See [llama.cpp multi-GPU options](https://github.com/ggml-org/llama.cpp/blob/master/docs/multi-gpu.md) and [build/runtime notes](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).

For the Windows host, the reviewed NVIDIA/llama.cpp sources offer adaptive fitting, a fixed layer-offload choice, or a CPU-only mode; they do not document a Windows per-process VRAM hard quota for this configuration. The exact pinned llama.cpp build's available options and behavior still need to be checked against its locked source/build if one of these is selected.

## NVIDIA MPS and MIG

NVIDIA says CUDA MPS is supported only on Linux and QNX; the MPS server does not start on other operating systems. It is not a Windows-host option. NVIDIA's MIG supported-GPU list includes specific datacenter products and selected RTX PRO Blackwell models, but no GeForce RTX 5060 Laptop GPU. The documented bare-metal MIG deployment is Linux-only. Do not assume this laptop supports MIG. Sources: [MPS OS limitations](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html), [MIG supported products](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/supported-gpus.html), and [MIG deployment considerations](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/deployment-considerations.html).

NVIDIA's MPS v3 **memory partitioning** is the documented hard-cap candidate for Linux. It accounts for device-memory allocations across a cgroup and enforces a hard limit at allocation time; over-limit allocations fail with out-of-memory. Prerequisites are Linux, cgroup v2 mounted at `/sys/fs/cgroup`, CUDA 13.4 or newer, and a non-MIG GPU. Setting limits through `nvidia-smi` or NVML is privileged. CUDA 13.4's new features require an R615-or-later driver. With kernel 6.14+ and the DMEM cgroup controller, `dmem.max` enforces the hard limit in-kernel; NVIDIA documents a driver-accounting `misc` fallback on kernels without that controller. Sources: [MPS v3 memory partitioning](https://docs.nvidia.com/deploy/mps/latest/mpsv3-memory-partitioning.html), [CUDA 13.4 driver compatibility](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html).

The older MPS pinned-device-memory control is not interchangeable with MPS v3 cgroup memory partitioning: NVIDIA describes it as a CUDA-client allocation limit, and under MPS v3 the namespace's limit is authoritative while the client environment variable can further constrain it. See [MPS environment-variable semantics](https://docs.nvidia.com/deploy/mps/latest/appendix-environment-variables.html).

## Practical paths and unverified requirements

1. **Stay on Windows:** keep treating `--fit-target` as a safety margin, or choose a lower fixed `--gpu-layers` value to reduce placement; neither proves a total VRAM hard bound. `--device none` is the no-GPU option. The exact GPU model, free-memory baseline, pinned-build behavior, and practical performance tradeoff are unverified for the current checkout.
2. **Evaluate Linux MPS v3:** first verify a supported Linux host, NVIDIA driver/toolkit compatibility (including R615+ for CUDA 13.4 features), cgroup-v2 layout, whether the kernel exposes DMEM or uses the fallback, GPU support, privilege to set/read limits, and that the actual assessor process is inside the limited cgroup. Linux host isolation and GPU access remain unverified in the repo's existing evidence.
3. **MIG:** not a candidate for a GeForce RTX 5060 Laptop GPU according to NVIDIA's published support list. A different supported MIG product would require separate hardware and Linux deployment evidence.

This note compares available mechanisms only; it does not select a host, budget, model placement, or deployment architecture.
