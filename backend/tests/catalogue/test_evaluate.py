from src.catalogue.evaluate import evaluate


def test_reports_wrong_badges_without_claiming_a_small_set_is_verified(config, tmp_path):
    path = tmp_path / "verified.csv"
    path.write_text(
        "netflix_id,title,year,type,expected_imdb_id\n"
        "123,Alternate Title,,,tt1\n"
        "124,Kumbalangi Nights,,,tt999\n"
        "125,Same Name,,,tt2\n",
        encoding="utf-8",
    )
    report = evaluate(path, config)
    assert report["badges"] == 3
    assert report["precision"] == 1 / 3
    assert report["errors"][0]["actual"] == "tt5"
    assert report["accepted"] is False
