import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from pharmsignal.labels import (
    api_key_from_env,
    build_url,
    cache_path,
    fetch_label,
)

FAKE_BODY = {"results": [{"warnings_and_cautions": [{"text": "Hepatotoxicity"}]}]}


class FakeOpener:
    def __init__(self, body=None, error_code=None):
        self.body = body
        self.error_code = error_code
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if self.error_code:
            raise urllib.error.HTTPError(url, self.error_code, "err", None, None)
        return json.dumps(self.body).encode("utf-8")


class LabelTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self._tmp.name) / "openfda"

    def tearDown(self):
        self._tmp.cleanup()

    def test_fetches_and_caches_with_timestamp(self):
        opener = FakeOpener(body=FAKE_BODY)
        record = fetch_label("Ibuprofen", self.cache, opener=opener)
        self.assertTrue(record["found"])
        self.assertEqual(record["response"], FAKE_BODY)
        self.assertIn("T", record["fetched_at"])
        self.assertTrue((self.cache / "ibuprofen.json").exists())

    def test_second_call_uses_cache(self):
        opener = FakeOpener(body=FAKE_BODY)
        fetch_label("Ibuprofen", self.cache, opener=opener)
        fetch_label("Ibuprofen", self.cache, opener=opener)
        self.assertEqual(len(opener.calls), 1)

    def test_refresh_refetches(self):
        opener = FakeOpener(body=FAKE_BODY)
        fetch_label("Ibuprofen", self.cache, opener=opener)
        fetch_label("Ibuprofen", self.cache, opener=opener, refresh=True)
        self.assertEqual(len(opener.calls), 2)

    def test_not_found_is_cached_as_not_found(self):
        opener = FakeOpener(error_code=404)
        record = fetch_label("Nonexistentx", self.cache, opener=opener)
        self.assertFalse(record["found"])
        self.assertIsNone(record["response"])

    def test_other_http_errors_raise(self):
        opener = FakeOpener(error_code=500)
        with self.assertRaises(urllib.error.HTTPError):
            fetch_label("Ibuprofen", self.cache, opener=opener)

    def test_api_key_sent_but_not_cached(self):
        opener = FakeOpener(body=FAKE_BODY)
        fetch_label("Ibuprofen", self.cache, api_key="SECRET123", opener=opener)
        self.assertIn("api_key=SECRET123", opener.calls[0])
        self.assertNotIn("SECRET123", (self.cache / "ibuprofen.json").read_text())

    def test_requests_up_to_twenty_labels(self):
        self.assertIn("limit=20", build_url("Ibuprofen"))

    def test_url_has_no_key_when_absent(self):
        self.assertNotIn("api_key", build_url("Ibuprofen"))

    def test_cache_path_slugs_names(self):
        self.assertEqual(cache_path(self.cache, "Co-Amoxiclav 500mg").name, "co_amoxiclav_500mg.json")

    def test_empty_drug_name_raises(self):
        with self.assertRaises(ValueError):
            cache_path(self.cache, "  ")

    def test_env_key_read_and_blank_treated_as_none(self):
        with mock.patch.dict("os.environ", {"OPENFDA_API_KEY": "  abc  "}):
            self.assertEqual(api_key_from_env(), "abc")
        with mock.patch.dict("os.environ", {"OPENFDA_API_KEY": "   "}):
            self.assertIsNone(api_key_from_env())


if __name__ == "__main__":
    unittest.main()