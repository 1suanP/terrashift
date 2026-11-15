"""Property 10: OPeNDAP URL extraction. Validates Requirements 9.1, 9.2, 9.3, 9.4."""
from hypothesis import given, strategies as st

from modules.data_discovery import get_opendap_urls
from tests.conftest import make_granule

path = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_.", min_size=1, max_size=20)
plain_desc = st.sampled_from(["Download file", "HTTPS link", "Browse image", "Documentation"])
opendap_desc = st.sampled_from(["OPeNDAP request URL", "opendap link", "OPENDAP", "Use OPeNDAP here"])

granule_spec = st.lists(
    st.tuples(path, st.one_of(plain_desc, opendap_desc)), min_size=0, max_size=4
)


@given(st.lists(granule_spec, max_size=15))
def test_extraction_matches_expected(specs):
    granules = [make_granule(*[(f"https://host.example/{p}", d) for p, d in spec]) for spec in specs]
    expected = []
    for spec in specs:
        for p, d in spec:
            if "OPENDAP" in d.upper():
                expected.append(f"dap4://host.example/{p}")
                break
    urls = get_opendap_urls(granules)
    assert urls == expected
    assert all(u.startswith("dap4://") for u in urls)
    assert len(urls) <= len(granules)


@given(st.just([]))
def test_empty_input_gives_empty_output(empty):
    assert get_opendap_urls(empty) == []
