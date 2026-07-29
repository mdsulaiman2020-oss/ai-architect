import json
import urllib.request
import urllib.parse
import urllib.error
from tools.base import Tool

class FetchURLTool(Tool):
    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return "Fetch content or call an API endpoint at a specified HTTP or HTTPS URL."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full HTTP or HTTPS URL to fetch (e.g., 'https://httpbin.org/get')."
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "default": "GET",
                    "description": "HTTP method to use."
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers key-value object."
                },
                "body": {
                    "type": "string",
                    "description": "Optional body text or JSON string for POST or PUT requests."
                }
            },
            "required": ["url"],
        }

    def execute(self, **args) -> dict:
        url = args.get("url", "").strip()
        method = args.get("method", "GET").upper()
        headers = args.get("headers", {}) or {}
        body = args.get("body")

        if not url:
            return {"error": "URL parameter is required."}

        # 1. Zero-Trust Security: Ensure scheme is http or https
        if not (url.startswith("http://") or url.startswith("https://")):
            return {"error": "Invalid URL scheme. Only HTTP and HTTPS are allowed."}

        # 2. SSRF Protection: Restrict loopback and metadata addresses
        disallowed_hosts = ["localhost", "127.0.0.1", "169.254.169.254", "0.0.0.0"]
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.hostname and parsed_url.hostname.lower() in disallowed_hosts:
            return {"error": "Access to local or internal metadata addresses is restricted."}

        # Prepare request
        encoded_body = body.encode("utf-8") if body else None
        req = urllib.request.Request(url, data=encoded_body, headers=headers, method=method)

        if "User-Agent" not in req.headers:
            req.add_header("User-Agent", "AIRuntime/1.0")

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                status_code = response.getcode()
                raw_bytes = response.read(100000)  # Max 100 KB limit to prevent LLM context overflow
                content_text = raw_bytes.decode("utf-8", errors="replace")

                try:
                    parsed_json = json.loads(content_text)
                    return {
                        "status_code": status_code,
                        "data": parsed_json
                    }
                except json.JSONDecodeError:
                    return {
                        "status_code": status_code,
                        "content": content_text
                    }

        except urllib.error.HTTPError as e:
            error_body = e.read(5000).decode("utf-8", errors="replace")
            return {
                "status_code": e.code,
                "error": f"HTTP Error {e.code}: {e.reason}",
                "detail": error_body
            }
        except urllib.error.URLError as e:
            return {"error": f"Network Error: {str(e.reason)}"}
        except TimeoutError:
            return {"error": "Request timed out after 8 seconds."}
        except Exception as e:
            return {"error": f"Failed to fetch URL: {str(e)}"}
