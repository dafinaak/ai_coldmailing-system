from pipeline.website import _sichtbarer_text

def test_extrahiert_sichtbaren_text():
    html = "<html><head><script>x=1</script></head><body><h1>Wir sind Firma</h1><p>Wir bauen Rohre.</p></body></html>"
    text = _sichtbarer_text(html)
    assert "Wir bauen Rohre." in text and "x=1" not in text
