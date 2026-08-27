"""Data pipeline tests"""
import unittest
from scripts.prepare_data import prepare_data
from scripts.run_pipeline import run_pipeline


class TestDataPipeline(unittest.TestCase):
    def test_prepare_data(self):
        result = prepare_data(dataset_type="qa", train_size=100, val_size=30, test_size=30)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["train_samples"], 100)

    def test_run_pipeline(self):
        result = run_pipeline(dataset_type="qa", train_size=100)
        self.assertEqual(result["status"], "completed")
        self.assertIn("pipeline_run_id", result)


if __name__ == "__main__":
    unittest.main()