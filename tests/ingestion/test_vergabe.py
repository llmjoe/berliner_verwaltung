"""Tests for Vergabeplattform scraper HTML parsing."""

from berliner_verwaltung.ingestion.vergabe.scraper import FHK_PLZS, _parse_listing_page

SAMPLE_ARTICLE = """
<article class="card">
    <header class="card__header">
        <h3 class="title">Sanierung Schulgebaeude Friedrichshain</h3>
    </header>
    <div class="card__body">
        <dl class="list--horizontal">
            <dt>Verfahrensart</dt>
            <dd>Offenes Verfahren (VOB/EU)</dd>
            <dt>Ausführungsort</dt>
            <dd class="cnw_skip_translation">10247 Berlin Friedrichshain</dd>
            <dt data-flag="application_period">Ablauf der Angebotsfrist</dt>
            <dd data-flag="application_period">15.06.2026, 12:00 Uhr</dd>
        </dl>
    </div>
    <div class="card__footer">
        <div class="row leftandright center">
            <div class="left">Online seit: 28.04.2026</div>
            <div class="right">
            <button data-href="https://meinauftrag.rib.de/public/DetailsByPlatformIdAndTenderId/platformId/2/tenderId/99999">
                Details
            </button>
            </div>
        </div>
    </div>
</article>
"""


def test_parse_listing_page():
    items = _parse_listing_page(SAMPLE_ARTICLE)
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Sanierung Schulgebaeude Friedrichshain"
    assert item["procedure_type"] == "Offenes Verfahren (VOB/EU)"
    assert item["source_id"] == "berlin-99999"
    assert item["plz"] == "10247"
    assert item["is_fhk"] is True
    assert item["online_date"] == "28.04.2026"
    assert item["deadline"] == "15.06.2026"


def test_parse_non_fhk():
    html = SAMPLE_ARTICLE.replace("10247", "10115").replace("Friedrichshain", "Mitte")
    items = _parse_listing_page(html)
    assert items[0]["is_fhk"] is False
    assert items[0]["plz"] == "10115"


def test_fhk_plzs():
    assert "10247" in FHK_PLZS
    assert "10961" in FHK_PLZS
    assert "10115" not in FHK_PLZS
