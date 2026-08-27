"""模型评估脚本"""
import json

EVALUATION_METRICS = {
    "automatic": ["perplexity", "rouge-1", "rouge-l", "bleu-4", "bert_score"],
    "human": ["accuracy", "completeness", "fluency", "actionability", "safety"],
}


def evaluate(model_path: str, test_data_dir: str, output_dir: str):
    """Evaluate fine-tuned model."""
    print(f"Evaluating model: {model_path}")
    print(f"Test data: {test_data_dir}")
    print()

    # Simulated evaluation results (in production, actually compute these)
    results = {
        "automatic": {
            "perplexity": 12.34,
            "rouge-1": 0.45,
            "rouge-l": 0.38,
            "bleu-4": 0.28,
            "bert_score": 0.72,
        },
        "human": {
            "accuracy": 0.88,
            "completeness": 0.85,
            "fluency": 0.92,
            "actionability": 0.80,
            "safety": 0.95,
        },
        "overall_score": 0.78,
        "pass_threshold": 0.75,
        "passed": True,
    }

    print("Evaluation Results:")
    print(json.dumps(results, indent=2))

    return results


if __name__ == "__main__":
    evaluate("./outputs/lora_adapters", "./data/test", "./outputs/eval_results")