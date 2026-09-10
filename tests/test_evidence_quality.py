from evidence_quality import credibility_prior, deduplicate_evidence, normalize_url, source_tier


def test_url_normalization_removes_tracking_and_www():
    assert normalize_url('HTTPS://www.example.com/story/?utm_source=test') == 'https://example.com/story'


def test_unknown_domain_has_explicit_neutral_prior():
    assert source_tier('unknown.example') == 'unknown'
    assert credibility_prior('unknown.example') == 0.5


def test_duplicate_urls_and_passages_are_not_independent_sources():
    items = [
        {'url': 'https://example.com/a', 'title': 'Report', 'snippet': 'The same report text.'},
        {'url': 'https://www.example.com/a/', 'title': 'Copy', 'snippet': 'Different URL spelling.'},
        {'url': 'https://other.example/copy', 'title': 'Syndicated', 'snippet': 'The same report text.'},
    ]

    assert len(deduplicate_evidence(items)) == 1