"""Optional local inference with the same prompts and parser as hosted models."""
from threading import Lock

from src.llm_client import ModelClientError, parse_model_response
from src.prompts import build_messages


class LocalClient:
    backend = "local"

    def __init__(self, settings):
        self.settings = settings
        self.lock = Lock()
        self.model = None
        self.tokenizer = None

    def _load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        source = self.settings.local_adapter or self.settings.local_model
        tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=False)
        model = AutoModelForCausalLM.from_pretrained(
            self.settings.local_model, trust_remote_code=False,
            torch_dtype=torch.float32 if not torch.cuda.is_available() else torch.float16,
        )
        if self.settings.local_adapter:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, self.settings.local_adapter)
        model.to("cuda" if torch.cuda.is_available() else "cpu")
        model.eval()
        self.tokenizer, self.model = tokenizer, model

    def analyze(self, request):
        with self.lock:
            try:
                import torch
                if self.model is None:
                    self._load()
                prompt = self.tokenizer.apply_chat_template(
                    build_messages(request), tokenize=False, add_generation_prompt=True,
                )
                inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(self.model.device)
                context_limit = getattr(self.model.config, "max_position_embeddings", 32768)
                if inputs.input_ids.shape[1] + self.settings.max_output_tokens > context_limit:
                    raise ModelClientError("输入与预留输出超过本地模型上下文窗口，请缩短命令。")
                with torch.inference_mode():
                    generated = self.model.generate(
                        **inputs, max_new_tokens=self.settings.max_output_tokens,
                        do_sample=False, pad_token_id=self.tokenizer.eos_token_id,
                    )
                tokens = generated[0, inputs.input_ids.shape[1]:]
                raw = self.tokenizer.decode(tokens, skip_special_tokens=True).strip()
            except ImportError:
                raise ModelClientError("本地推理依赖缺失，请安装 requirements-local.txt。") from None
            except ModelClientError:
                raise
            except Exception:
                raise ModelClientError("本地模型加载或推理失败，请检查权重、adapter 路径及可用内存。") from None
        return parse_model_response(raw)
