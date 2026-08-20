import pytest

from stitcher.vo_alignment import Segment
from stitcher.vo_timing import derive_captions, rescale_relative_spans


def test_derive_captions_spans_each_segment_exactly():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.2),
        Segment(name="beat2", at=6.1, duration=4.0),
    ]
    captions = derive_captions(segments, ["First line.", "Second line."])

    assert len(captions) == 2
    assert captions[0].start == 0.0
    assert captions[0].end == 5.2
    assert captions[0].text == "First line."
    assert captions[1].start == 6.1
    assert captions[1].end == pytest.approx(10.1)
    assert captions[1].text == "Second line."


def test_derive_captions_mismatched_lengths_raises():
    segments = [Segment(name="beat1", at=0.0, duration=5.2)]
    with pytest.raises(ValueError, match="must be the same length"):
        derive_captions(segments, ["a", "b"])


def test_rescale_relative_spans_maps_fractions_onto_segment_window():
    segment = Segment(name="beat1", at=10.0, duration=6.0)
    spans = [(0.0, 0.5), (0.5, 1.0)]

    result = rescale_relative_spans(spans, segment)

    assert result == pytest.approx([(10.0, 13.0), (13.0, 16.0)])


def test_rescale_relative_spans_full_span_covers_whole_segment():
    segment = Segment(name="only", at=2.0, duration=4.0)
    result = rescale_relative_spans([(0.0, 1.0)], segment)
    assert result == pytest.approx([(2.0, 6.0)])


def test_rescale_relative_spans_out_of_order_fraction_raises():
    segment = Segment(name="only", at=0.0, duration=4.0)
    with pytest.raises(ValueError, match=r"0 <= start <= end <= 1"):
        rescale_relative_spans([(0.6, 0.4)], segment)


def test_rescale_relative_spans_fraction_out_of_bounds_raises():
    segment = Segment(name="only", at=0.0, duration=4.0)
    with pytest.raises(ValueError, match=r"0 <= start <= end <= 1"):
        rescale_relative_spans([(-0.1, 0.5)], segment)
