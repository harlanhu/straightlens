# Upstream

Source: https://www.ipol.im/pub/art/2016/130/ldm_pq2p_io-20220510.tar.gz

SHA-256: `2ff5d24e2350979cf60d6d9c301c9a07539ffab5731b8a16e9196073919733fd`

Authors, copyright and CC BY-NC-SA 3.0 notices are retained in the original files. This application is for personal, non-commercial use.

Native tool takes 12 positional arguments (argc=13), including four image paths, six numeric settings, model/center flags, and primitives path as documented in its source. It writes `output.txt` to its working directory. A zero exit status is not sufficient: failures may return 0 without a primitives file.

Local patch: in `energy_minimization`, preserve fixed-center optimized model when opt_center=false, rather than reverting to pre-optimization tt_ldm and returning zero error; accept center-optimized result only when both coordinate shifts are within 20% and its mapping is invertible (upstream used OR). All other algorithm code is unmodified. End-to-end and synthetic mapping tests cover adapter behavior; original and patched implementation are compared during evaluation.
