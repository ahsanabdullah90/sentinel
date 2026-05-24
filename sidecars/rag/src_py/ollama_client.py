import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger("rag.ollama_client")

class OllamaClient:
    def __init__(self):
        # Read from environment variable passed by Docker-compose, fallback to localhost
        self.base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        logger.info(f"Initialized OllamaClient pointing to: {self.base_url}")

    async def check_health(self) -> bool:
        import asyncio
        def run_health():
            try:
                url = f"{self.base_url}/api/tags"
                with urllib.request.urlopen(url, timeout=2.0) as response:
                    return response.status == 200
            except Exception:
                return False

        return await asyncio.get_running_loop().run_in_executor(None, run_health)

    async def is_model_pulled(self, model_name: str) -> bool:
        import asyncio
        def run_tags():
            try:
                url = f"{self.base_url}/api/tags"
                with urllib.request.urlopen(url, timeout=2.0) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        models = data.get("models", [])
                        return any(m.get("name") == model_name or m.get("name") == f"{model_name}:latest" for m in models)
            except Exception:
                return False
            return False

        return await asyncio.get_running_loop().run_in_executor(None, run_tags)

    async def generate(self, model: str, prompt: str, system_context: str = None) -> str:
        import asyncio
        def run_generate():
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            if system_context:
                payload["system"] = system_context

            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30.0) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        return data.get("response", "")
                    else:
                        raise RuntimeError(f"Ollama generation failed: {response.reason}")
            except Exception as e:
                logger.error(f"Ollama generate failed: {str(e)}")
                raise RuntimeError(f"Ollama generation failed: {str(e)}")

        return await asyncio.get_running_loop().run_in_executor(None, run_generate)
