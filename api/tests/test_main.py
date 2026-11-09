"""Tests du contrat HTTP sans accès au Parquet réel."""
import json
import subprocess
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from api.main import app, parse_estimator_output

client = TestClient(app)


class ContractTests(unittest.TestCase):
    def test_parse_json_line(self):
        payload = {"results": [{"name": "A", "estimated_wh": 0.012}]}
        output = "diagnostic\nECO_ROUTAGE_JSON:" + json.dumps(payload) + "\nfin"
        self.assertEqual(parse_estimator_output(output), payload)

    def test_parse_missing_line(self):
        with self.assertRaises(ValueError):
            parse_estimator_output("diagnostic sans résultat")

    def test_missing_dataset(self):
        with patch("api.main.COMPAREAI") as data:
            data.is_file.return_value = False
            response = client.post("/api/estimate", json={"prompt": "test"})
        self.assertEqual(response.status_code, 503)

    def test_missing_reactions_dataset(self):
        with patch("api.main.COMPAREAI") as data, patch("api.main.REACTIONS") as reactions:
            data.is_file.return_value = True
            reactions.is_file.return_value = False
            response = client.post("/api/estimate", json={"prompt": "test"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("reactions.parquet", response.json()["detail"])

    def test_empty_prompt_rejected(self):
        response = client.post("/api/estimate", json={"prompt": "   "})
        self.assertEqual(response.status_code, 422)

    def test_invalid_source_rejected(self):
        response = client.post("/api/estimate", json={"prompt": "test", "energy_source": "arbitrary"})
        self.assertEqual(response.status_code, 422)

    def test_structured_output(self):
        payload = {"results": [{"name": "Model X", "estimated_wh": 0.04}], "recommended_model": "Model X"}
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ECO_ROUTAGE_JSON:" + json.dumps(payload), stderr=""
        )
        with patch("api.main.COMPAREAI") as data, patch("api.main.REACTIONS") as reactions, patch("api.main.subprocess.run", return_value=completed) as run:
            data.is_file.return_value = True
            reactions.is_file.return_value = True
            response = client.post("/api/estimate", json={"prompt": "Bonjour"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertIn("--json-line", run.call_args.args[0])
        self.assertIn("--calibration-cache", run.call_args.args[0])

    def test_prompt_starting_with_dash_is_not_parsed_as_option(self):
        payload = {"results": [{"name": "Modèle A", "estimated_wh": 0.01}]}
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="ECO_ROUTAGE_JSON:" + json.dumps(payload), stderr=""
        )
        with patch("api.main.COMPAREAI") as data, patch("api.main.REACTIONS") as reactions, patch("api.main.subprocess.run", return_value=completed) as run:
            data.is_file.return_value = True
            reactions.is_file.return_value = True
            response = client.post("/api/estimate", json={"prompt": "--résume un texte"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("--prompt=--résume un texte", run.call_args.args[0])



if __name__ == "__main__":
    unittest.main()
