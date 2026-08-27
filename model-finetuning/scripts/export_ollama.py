"""导出为 vLLM 可用模型"""
import os
import shutil


def export_vllm(model_name: str, base_model: str, lora_path: str, output_dir: str):
    """Create vLLM Modelfile and export model."""
    os.makedirs(output_dir, exist_ok=True)

    modelfile_content = f"""FROM {base_model}
# LoRA adapter (if supported by vLLM)
# ADAPTER {lora_path}/adapter_model.bin

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 4096

SYSTEM \"\"\"你是运维智能客服助手。请根据知识库内容，用简洁、专业的语言回答用户问题。
如果问题超出你的知识范围，请诚实告知并建议用户联系人工客服。
回答时请包含具体操作步骤和注意事项。\"\"\"
"""

    modelfile_path = os.path.join(output_dir, "Modelfile")
    with open(modelfile_path, "w") as f:
        f.write(modelfile_content)

    print(f"vLLM Modelfile created at: {modelfile_path}")
    print(f"To serve the model, run:")
    print(f"  vllm serve {model_name} --port 8000")
    print()
    print("NOTE: This is a framework script. In production, after creating the vLLM model:")
    print("  1. Configure Orchestrator for A/B testing")
    print("  2. Route 10% traffic to new model")
    print("  3. Monitor metrics for 7 days")
    print("  4. If satisfaction improves, switch to 100%")

    return {"status": "framework_ready", "modelfile_path": modelfile_path, "model_name": model_name}


if __name__ == "__main__":
    export_vllm("ops-agent:v2.1-lora", "qwen2.5:7b-instruct", "./outputs/lora_adapters", "./outputs")