import requests

class OllamaService:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    def get_status(self) -> dict:
        """
        Queries Ollama API and retrieves version, installed models, and active loaded models.
        Returns:
            {
                "online": bool,
                "version": str,
                "active_models": list of dicts (name, size, vram, expires_at),
                "installed_models": list of dicts (name, size, parameter_size, quantization)
            }
        """
        stats = {
            "online": False,
            "version": "N/A",
            "active_models": [],
            "installed_models": []
        }

        # 1. Health check & version
        try:
            res_version = requests.get(f"{self.base_url}/api/version", timeout=1.5)
            if res_version.status_code == 200:
                stats["online"] = True
                stats["version"] = res_version.json().get("version", "Unknown")
            else:
                # If version is not 200, check endpoint health using /api/tags
                res_tags = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
                if res_tags.status_code == 200:
                    stats["online"] = True
        except requests.RequestException:
            # Server is offline
            return stats

        # If we are online, query active and installed models
        if stats["online"]:
            # 2. Installed models
            try:
                res_tags = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
                if res_tags.status_code == 200:
                    data = res_tags.json()
                    for model in data.get("models", []):
                        details = model.get("details", {})
                        stats["installed_models"].append({
                            "name": model.get("name", "Unknown"),
                            "size": model.get("size", 0),
                            "parameter_size": details.get("parameter_size", "N/A"),
                            "quantization": details.get("quantization_level", "N/A")
                        })
            except requests.RequestException:
                pass

            # 3. Active running models (ollama ps)
            try:
                res_ps = requests.get(f"{self.base_url}/api/ps", timeout=1.5)
                if res_ps.status_code == 200:
                    data = res_ps.json()
                    for model in data.get("models", []):
                        stats["active_models"].append({
                            "name": model.get("name", "Unknown"),
                            "size": model.get("size", 0),
                            "vram": model.get("size_vram", 0),
                            "expires_at": model.get("expires_at", "N/A")
                        })
            except requests.RequestException:
                pass

        return stats
