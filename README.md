# AI-ready-markdown-agent
Built an agentic preprocessing tool that converts websites and files into clean Markdown for LLM workflows. It auto-compares readable vs compressed output, estimates token savings, and provides prompt-optimization guidance.


🧹 AI-Ready Markdown Agent

> Convert messy webpages & PDFs into clean, token-efficient Markdown — ready for Claude, GPT-4o, or any LLM.

## What it does
- **Fetches** any public webpage → strips nav/ads/scripts/footers → clean Markdown
- **Parses** uploaded PDFs → structured Markdown preserving headings, tables, lists
- **Estimates** token reduction (before vs. after) with GPT-4o cost savings
- **4 output modes**: Standard, Ultra-compact, RAG chunk-ready, Claude paste mode
- **Built-in prompt tips** per mode — best techniques to get great LLM output

## ⚠️ Known Limitations
- Scanned/image-only PDFs need OCR — not supported in this version
- Paywalled or JS-rendered pages will fail gracefully with an error message
- Multi-column PDF layouts may have reading-order issues — review output before use

## Stack (all free & open-source)
| Library | Role | Version |
|---------|------|---------|
| `Gradio` | UI + HF Spaces deployment | 5.x |
| `trafilatura` | Web content extraction → Markdown | 2.x |
| `pymupdf4llm` | PDF → structured Markdown | latest |
| `tiktoken` | Token counting (cl100k_base) | 0.7+ |

Here is the link to aceess : https://huggingface.co/spaces/BalajiBaluP/ai-ready-markdown-agent
