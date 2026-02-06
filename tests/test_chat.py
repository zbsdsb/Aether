#!/usr/bin/env python3
"""
Chat Completions Test Script

模拟 AsyncOpenAI Python SDK 客户端发送请求,包含完整的请求头和请求体。

Usage:
    python test_chat.py
    python test_chat.py --stream
"""

from __future__ import annotations

import json
import sys

import requests

BASE_URL = "http://localhost:8084/v1"
API_KEY = "sk-PCr5oXZNKb9HcyzYqTIMvr8zXsIBK3WS"


def build_headers(api_key: str) -> dict[str, str]:
    """模拟 AsyncOpenAI/Python 2.14.0 客户端请求头"""
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "AsyncOpenAI/Python 2.14.0",
        "x-stainless-lang": "python",
        "x-stainless-package-version": "2.14.0",
        "x-stainless-os": "Windows",
        "x-stainless-arch": "other:amd64",
        "x-stainless-runtime": "CPython",
        "x-stainless-runtime-version": "3.12.11",
        "x-stainless-async": "async:asyncio",
        "x-stainless-retry-count": "0",
        "x-stainless-read-timeout": "120",
        "Authorization": f"Bearer {api_key}",
    }


def build_payload(stream: bool = False) -> dict:
    """构造请求体"""
    return {
        "messages": [
            {
            "role": "user",
            "content": "hi"
            }
        ],
        "model": "gpt-5.2",
        "max_tokens": 2048,
        "stream": False,
        "temperature": 0.5
    }


def send_sync(api_key: str) -> dict:
    """发送非流式请求"""
    url = f"{BASE_URL}/chat/completions"
    headers = build_headers(api_key)
    payload = build_payload(stream=False)

    print(f"[sync] POST {url}")
    print(f"[sync] model={payload['model']}")
    print("-" * 60)

    response = requests.post(url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()

    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})

    print(content)
    print("-" * 60)
    print(f"Model: {data.get('model')}")
    print(
        f"Usage: prompt={usage.get('prompt_tokens', 0)}, "
        f"completion={usage.get('completion_tokens', 0)}, "
        f"total={usage.get('total_tokens', 0)}"
    )
    return data


def send_stream(api_key: str) -> None:
    """发送流式请求"""
    url = f"{BASE_URL}/chat/completions"
    headers = build_headers(api_key)
    payload = build_payload(stream=True)

    print(f"[stream] POST {url}")
    print(f"[stream] model={payload['model']}")
    print("-" * 60)

    response = requests.post(url, headers=headers, json=payload, timeout=120, stream=True)
    response.raise_for_status()

    full_content = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data = line[len("data: "):]
        if data.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(data)
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                print(content, end="", flush=True)
                full_content += content
        except json.JSONDecodeError:
            pass

    print()
    print("-" * 60)
    print(f"Total length: {len(full_content)} chars")


def main() -> None:
    stream = "--stream" in sys.argv

    try:
        if stream:
            send_stream(API_KEY)
        else:
            send_sync(API_KEY)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        if e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
