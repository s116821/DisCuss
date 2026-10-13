# Verification

55 offline tests pass; dedicated evaluation test verifies eight offered streams conserve four accepted/four rejected and distinct member counts while metadata results contain no transcript. Ruff/format/ty, actual analyzer13 cases and uv wheel/sdist build pass.

Real pinned small-model CPU/int8/two-thread Windows suite completed with625MiB peakRSS and zero inference subprocesses. It reported recognition failures honestly: short0/1, repeated1/3, direct34s stress case3/20, silence0. Shared attributed streams preserved member identity; deliberate overload never exceeded four queued chunks, dropped four of eight offered streams, and accepted work had zero processing failures. Measured aggregate decoding was1.65–1.75audio seconds per compute second, not a sustainable multi-listener claim. Results/provenance are committed; no human recordings or transcripts were collected.

Both OS CI explicitly prepares the pinned model in disposable temporary state and uploads metrics only. Remote suite results are pending this PR. Two artificial US-English voices, a34-second direct decoder case and burst load cannot qualify accents, GPU, sustained soak, actual conversation or live DAVE. DEG-26 remains partial evidence; functional release is still gated on independent qualification and calibration.
