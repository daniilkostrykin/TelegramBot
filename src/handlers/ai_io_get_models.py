from typing import Dict, List


def get_models_by_category() -> Dict[str, List[str]]:
    """Возвращает фиксированный список моделей по категориям"""
    return {
        "deepseek": [
            "deepseek-ai/DeepSeek-R1",
            "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
        ],
        "qwen": [
            "Qwen/QwQ-32B",
            "Qwen/Qwen2-VL-7B-Instruct",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "Qwen/Qwen2.5-1.5B-Instruct"
        ],
        "mistral": [
            "mistralai/Ministral-8B-Instruct-2410",
            "mistralai/Mistral-Large-Instruct-2411"
        ],
        "llama": [
            "meta-llama/Llama-3.2-90B-Vision-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct",
            "neuralmagic/Llama-3.1-Nemotron-70B-Instruct-HF-FP8-dynamic"
        ],
        "other": [
            "databricks/dbrx-instruct",
            "netease-youdao/Confucius-o1-14B",
            "nvidia/AceMath-7B-Instruct",
            "google/gemma-2-9b-it",
            "microsoft/phi-4",
            "microsoft/Phi-3.5-mini-instruct",
            "watt-ai/watt-tool-70B",
            "bespokelabs/Bespoke-Stratos-32B",
            "NovaSky-AI/Sky-T1-32B-Preview",
            "tiiuae/Falcon3-10B-Instruct",
            "CohereForAI/c4ai-command-r-plus-08-2024",
            "THUDM/glm-4-9b-chat",
            "CohereForAI/aya-expanse-32b",
            "jinaai/ReaderLM-v2",
            "openbmb/MiniCPM3-4B",
            "ozone-ai/0x-lite",
            "ibm-granite/granite-3.1-8b-instruct"
        ]
    }


if __name__ == "__main__":
    models = get_models_by_category()
    for category, model_list in models.items():
        print(f"\n{category.upper()}:")
        for model in model_list:
            print(f"  - {model}")
