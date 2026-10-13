# Design

Windows System.Speech David/Zira generate neutral original phrases, stored as synthetic WAV fixtures with provenance. PyAV decodes/resamples, pinned local faster-whisper small CPU/int8/two-thread backend runs all cases. Direct recognition handles short/repeated/long/silent inputs; member-attributed pipeline receives simultaneous input chunks and a deliberate queue burst. Record expected/actual counts, latency, RSS and drop/admission limits, never transcripts. Sharing one thread models bounded work, not unlimited realtime listener capacity. Synthetic American-English voices and a one-minute passage cannot qualify different accents, real conversational overlap, GPU or long-duration soak; those remain explicit acceptance limits.

CI explicitly downloads the pinned model into runner temporary state and uploads metrics only. Normal unit/quality jobs remain fast and offline. Benchmark quality reports observed inaccuracies rather than forcing word-count expectations to pass.
