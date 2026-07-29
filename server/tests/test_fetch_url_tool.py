from pathlib import Path
import sys

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from tools.fetch_url_tool import FetchURLTool

def test_fetch_url():
    tool = FetchURLTool()
    result = tool.execute(url="https://api.github.com/zen")
    assert "status_code" in result or "error" in result
    print("Fetch URL Test Executed! Result:", result)

    # Test SSRF protection
    ssrf_result = tool.execute(url="http://127.0.0.1:8000/api/reset")
    assert "error" in ssrf_result
    assert "restricted" in ssrf_result["error"]
    print("SSRF Protection Test Passed! Error:", ssrf_result["error"])

if __name__ == "__main__":
    test_fetch_url()

