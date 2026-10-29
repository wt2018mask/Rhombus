# Stage R1 source preservation

Files below this directory reproduce the code SHA256 values in
`data/benchmarks/v3_static/priority7_r1_manifest_v1.json` before Option C edits.
Paths mirror the repository. These files preserve historical source bytes;
run them by restoring their relative paths in an isolated checkout of base
`93e2c420362e55a5de1ef13267d05e37ab07755f`, together with the retained Stage R1
files. Running scripts directly from this archive changes their ROOT discovery.
The original joint and analytical scripts were reconstructed from the edits
and accepted only after byte SHA256 equality with that prior manifest.
