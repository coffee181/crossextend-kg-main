# Round 2

Round 2 kept the scope on `BATOM_002`, but shifted from structural denoising to semantic boundary refinement. The core changes were a stronger extraction prompt in [preprocessing_extraction_om.txt](D:/crossextend_kg/config/prompts/preprocessing_extraction_om.txt) and a more selective filtering policy in [filtering.py](D:/crossextend_kg/rules/filtering.py) that rejects generic replacement-part nodes, preserves reusable geometry measurements, and stops over-rescuing weak observation artifacts.

The resulting single-document graph is much closer to the human gold than Round 1: concept F1 increased from `0.8696` to `0.9556`, relation F1 increased from `0.6957` to `0.8649`, anchor accuracy stayed at `1.0000`, and extra concepts dropped to zero. The remaining misses are narrow and interpretable, which makes Round 3 ready to test whether these rules still behave well on `CNCOM_002` and `EVMAN_002`.
