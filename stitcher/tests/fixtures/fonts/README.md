# Test fonts

Golden-image tests need a font file that is byte-identical on every machine
that runs them. Place `Inter-Bold.ttf` here (SIL Open Font License) before
running the overlay tests; `tests/test_overlays.py` skips its font-dependent
tests when the file is absent so the rest of the suite still runs.

Do not substitute a system font. Rasterization differs between builds, and the
golden PNGs are compared against a numeric RMSE threshold.
