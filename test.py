import base64
import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ── 配置 ──────────────────────────────────────────────
IMAGE_PATH = Path(__file__).parent / "cat.jpg"
API_URL    = "http://localhost:8000/v1/chat/completions"
API_KEY    = "han1234"
MODEL      = "gemini-3.1-flash-image-landscape"
PROMPT     = "将这张图片变成水彩画风格"
OUTPUT     = Path(__file__).parent / "cat_watercolor.jpg"
# ───────────────────────────────────────────────────────


def read_image_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def call_api(b64_image: str) -> str:
    """发送请求，收集所有 SSE chunk，返回拼接后的完整 content。"""
    payload = json.dumps({
        "model": MODEL,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }
        ]
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    content = ""
    reasoning = ""
    with urllib.request.urlopen(req, timeout=300) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # 检查错误
            if "error" in chunk:
                raise RuntimeError(chunk["error"].get("message", str(chunk["error"])))

            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if delta.get("reasoning_content"):
                r = delta["reasoning_content"]
                reasoning += r
                print(r, end="", flush=True)
            if delta.get("content"):
                content += delta["content"]

    print()  # 换行
    return content


def extract_image_url(content: str) -> Optional[str]:
    """从 markdown 或纯文本中提取图片 URL。"""
    # ![...](url) 或直接 URL
    patterns = [
        r"!\[.*?\]\((https?://\S+?)\)",
        r"(https?://\S+\.(?:jpg|jpeg|png|webp|gif)(?:\?\S*)?)",
        r"(https?://\S+)",
    ]
    for pat in patterns:
        m = re.search(pat, content)
        if m:
            return m.group(1)
    return None


def download_image(url: str, dest: Path):
    print(f"📥 下载图片: {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"✅ 已保存到: {dest}")


def main():
    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f"找不到输入图片: {IMAGE_PATH}")

    print(f"📷 读取图片: {IMAGE_PATH}")
    b64 = read_image_base64(IMAGE_PATH)

    print(f"🚀 发送请求到 {API_URL} ...")
    print("-" * 50)
    content = call_api(b64)
    print("-" * 50)

    if not content:
        print("⚠️  响应 content 为空，可能图片已在 reasoning_content 中描述，请查看上方日志。")
        return

    print(f"\n📝 响应内容:\n{content}\n")

    url = extract_image_url(content)
    if url:
        download_image(url, OUTPUT)
    else:
        # 尝试 base64 内嵌
        b64_match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
        if b64_match:
            img_data = base64.b64decode(b64_match.group(1))
            OUTPUT.write_bytes(img_data)
            print(f"✅ base64 图片已保存到: {OUTPUT}")
        else:
            print("⚠️  未能从响应中提取图片 URL，请手动查看上方 content。")


if __name__ == "__main__":
    main()
