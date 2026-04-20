# Round 1

Round 1 focused on `BATOM_002` and targeted relation denoising without introducing fallback paths. The main changes were semantic-safe alias canonicalization in [preprocessing/processor.py](D:/crossextend_kg/preprocessing/processor.py), contextual structural-head rewriting in [preprocessing/processor.py](D:/crossextend_kg/preprocessing/processor.py), and stronger rescue logic for high-value hardware nodes plus explicit fault hints in [rules/filtering.py](D:/crossextend_kg/rules/filtering.py).

The round completed with a real `full_llm` run and improved the audited metrics from concept F1 `0.8485` to `0.8696`, anchor accuracy `0.9762` to `1.0000`, and relation F1 `0.5818` to `0.6957`. Predicted graph size also shrank from `52` concepts / `37` relations to `45` concepts / `28` relations, which confirms that noise was reduced instead of merely being re-labeled.

The main remaining risks going into Round 2 are semantic-boundary issues rather than structural clutter: `stress whitening` and `latch-window distortion` still miss their intended gold fault targets, and several grounded geometry or operating-state concepts are still under-extracted. The detailed audit artifacts for this round are stored under [artifacts/optimization_rounds/round_01](D:/crossextend_kg/artifacts/optimization_rounds/round_01).
