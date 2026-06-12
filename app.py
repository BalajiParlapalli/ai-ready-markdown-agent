import os
import re
import gradio as gr
import tiktoken
import trafilatura
from markitdown import MarkItDown

converter = MarkItDown()


def count_tokens(text):
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text or ""))
    except:
        return len((text or "")) // 4


def compact_markdown(text):
    text = re.sub(r'```[\w-]*\n', '', text)
    text = text.replace("```", "")
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\|', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|', ' - ', text)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def warning_block():
    return """
### ⚠️ Important Notes

- **Auto mode** means the agent evaluates Standard vs Compact and chooses the best for your file.
- **Manual Compact** is available if you want to force maximum compression after reviewing the auto output.
- Markdown conversion preserves **meaning**, but some formatting details may change in Compact mode.
- Complex PDFs, spreadsheets, tables, and multi-column layouts may need manual review.
- For accuracy-sensitive tasks, always review the Markdown before sending it to an LLM.
"""


def prompt_notes():
    return """
### ✅ Prompt Notes

- Define the role clearly.
- State one exact objective.
- Add useful context from the document.
- List requirements as bullets.
- Specify output format.
- Mention the audience.
- Add constraints: what to avoid, length, style.
- Ask the model to use only the provided Markdown when accuracy matters.
- For long content, ask it to focus on specific sections.
- For code files: ask for purpose, dependencies, risks, and improvements.
- For CSV/data files: ask for trends, anomalies, missing values, and insights.
- Ask for citations or section references when factual accuracy matters.
"""


def prompt_template():
    return """
### 🧩 Reusable Prompt Template

**Role:**
You are a [role].

**Objective:**
[What needs to be accomplished]

**Context:**
[Background information]

**Requirements:**
- Requirement 1
- Requirement 2
- Requirement 3

**Output Format:**
[Desired format]

**Audience:**
[Who will read it]

**Constraints:**
- What to avoid
- Length limits
- Style requirements
- Use only the provided Markdown/context
"""


def detect_input_type(url, file):
    if file is not None:
        ext = os.path.splitext(file.name)[1].lower()
        return f"Uploaded file ({ext})"
    if url.strip():
        return "Website URL"
    return "No input"


def extract_from_url(url):
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return "", "", "Could not fetch website URL."
    markdown = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_tables=True,
        include_links=True
    )
    if not markdown:
        return "", "", "Could not extract webpage content."
    return downloaded, markdown, ""


def extract_from_file(file):
    result = converter.convert(file.name)
    markdown = result.text_content if hasattr(result, "text_content") else str(result)
    if not markdown.strip():
        return "", "", "Could not extract file content."
    return markdown, markdown, ""


def score_markdown(text):
    score = 0
    reasons = []

    if len(text.strip()) > 200:
        score += 25
        reasons.append("Good content length")
    else:
        reasons.append("Very short output")

    if "\n#" in text or text.startswith("#"):
        score += 20
        reasons.append("Heading structure present")
    else:
        reasons.append("No heading structure")

    if "\n-" in text or "\n1." in text:
        score += 15
        reasons.append("List structure present")
    else:
        reasons.append("No list structure")

    if "```" in text or "`" in text:
        score += 10
        reasons.append("Code content preserved")

    if count_tokens(text) > 50:
        score += 15
        reasons.append("Non-trivial token content")

    blank_ratio = text.count("\n\n") / max(len(text.splitlines()), 1)
    if blank_ratio < 0.4:
        score += 15
        reasons.append("Reasonable content density")
    else:
        reasons.append("Too many blank lines")

    return min(score, 100), reasons


def build_stats(before_text, after_text, mode_label):
    before_tokens = count_tokens(before_text)
    after_tokens = count_tokens(after_text)
    saved = max(before_tokens - after_tokens, 0)
    reduction = round((saved / before_tokens) * 100, 1) if before_tokens else 0

    if saved == 0 and mode_label == "Standard (Auto)":
        note = "Tip: Try Manual Compact mode below if you want to force token compression."
    elif saved == 0:
        note = "This file was already minimal, so savings are limited."
    else:
        note = "Compact mode removed formatting overhead for better token efficiency."

    return (
        f"Mode applied: {mode_label}\n"
        f"Before tokens: {before_tokens}\n"
        f"After tokens:  {after_tokens}\n"
        f"Tokens saved:  {saved}\n"
        f"Reduction:     {reduction}%\n"
        f"\n{note}"
    )


def agent_decide(markdown):
    std_score, std_reasons = score_markdown(markdown)
    compact = compact_markdown(markdown)
    cmp_score, cmp_reasons = score_markdown(compact)

    std_tokens = count_tokens(markdown)
    cmp_tokens = count_tokens(compact)
    saved = max(std_tokens - cmp_tokens, 0)
    reduction = round((saved / std_tokens) * 100, 1) if std_tokens else 0

    if cmp_score >= std_score - 10 and cmp_tokens < std_tokens:
        chosen = "Compact"
        final_text = compact
        final_score = cmp_score
        decision_reasons = cmp_reasons
    else:
        chosen = "Standard"
        final_text = markdown
        final_score = std_score
        decision_reasons = std_reasons

    report = (
        f"=== Agent Auto-Evaluation ===\n\n"
        f"Standard Markdown:\n"
        f"  Tokens : {std_tokens}\n"
        f"  Score  : {std_score}/100\n"
        f"  Reason : {', '.join(std_reasons)}\n\n"
        f"Compact Markdown:\n"
        f"  Tokens : {cmp_tokens}\n"
        f"  Score  : {cmp_score}/100\n"
        f"  Saving : {saved} tokens ({reduction}%)\n"
        f"  Reason : {', '.join(cmp_reasons)}\n\n"
        f"Agent chose: {chosen}\n"
        f"Final score: {final_score}/100\n\n"
        f"Why: {', '.join(decision_reasons)}\n\n"
        f"Note: You can still switch to Manual Compact below if needed."
    )

    return final_text, markdown, compact, chosen, report


def run_agent(url, file):
    input_type = detect_input_type(url, file)

    if file is not None:
        raw_text, markdown, error = extract_from_file(file)
    elif url.strip():
        raw_text, markdown, error = extract_from_url(url.strip())
    else:
        return (
            "Enter a website URL or upload a file.",
            "", "", "",
            warning_block(), prompt_notes(), prompt_template()
        )

    if error:
        return (
            error,
            f"Input detected: {input_type}\nExtraction failed: {error}",
            "", "",
            warning_block(), prompt_notes(), prompt_template()
        )

    final_text, std_text, cmp_text, chosen_mode, report = agent_decide(markdown)
    mode_label = f"{chosen_mode} (Auto)"
    stats = build_stats(markdown, final_text, mode_label)
    llm_copy = f"[Source: {url.strip() or 'Uploaded file'}]\n[Mode: {mode_label}]\n\n---\n{final_text}\n---"
    full_report = f"Input type: {input_type}\n\n{report}"

    return (
        final_text,
        stats,
        full_report,
        llm_copy,
        warning_block(), prompt_notes(), prompt_template()
    )


def run_manual_compact(url, file):
    input_type = detect_input_type(url, file)

    if file is not None:
        raw_text, markdown, error = extract_from_file(file)
    elif url.strip():
        raw_text, markdown, error = extract_from_url(url.strip())
    else:
        return (
            "Run the agent first.",
            "", "", "",
            warning_block(), prompt_notes(), prompt_template()
        )

    if error:
        return (
            error,
            "", "", "",
            warning_block(), prompt_notes(), prompt_template()
        )

    compact = compact_markdown(markdown)
    stats = build_stats(markdown, compact, "Manual Compact (User Override)")
    llm_copy = f"[Source: {url.strip() or 'Uploaded file'}]\n[Mode: Manual Compact]\n\n---\n{compact}\n---"
    report = (
        f"Input type: {input_type}\n"
        f"Mode: Manual Compact selected by user.\n"
        f"The agent suggested a different mode, but you chose to override it.\n"
        f"Review the output carefully."
    )

    return (
        compact,
        stats,
        report,
        llm_copy,
        warning_block(), prompt_notes(), prompt_template()
    )


with gr.Blocks() as demo:
    gr.Markdown("# AI-Ready Markdown Agent")
    gr.Markdown(
        "Upload a file or paste a URL to generate AI-ready Markdown. "
        "This will Smartly converts websites and files into LLM-ready Markdown, compares Standard vs Compact output, and recommends the best version automatically."
    )

    with gr.Row():
        url = gr.Textbox(
            label="Website URL",
            placeholder="https://example.com/article-or-docs-page"
        )
        file = gr.File(
            label="Upload file (.pdf .docx .pptx .xlsx .csv .txt .md .json .html .py .js)",
            file_types=[
                ".pdf", ".docx", ".pptx", ".xlsx", ".csv",
                ".txt", ".md", ".json", ".html", ".xml", ".py", ".js"
            ]
        )

    with gr.Row():
        auto_btn = gr.Button("Run Agent (Auto Mode)", variant="primary")
        compact_btn = gr.Button("Force Manual Compact", variant="secondary")

    gr.Markdown("---")

    markdown_out = gr.Textbox(label="Best Output Chosen by Agent", lines=18)
    stats_out = gr.Textbox(label="Before vs After Optimization", lines=8)
    report_out = gr.Textbox(label="Why the Agent Chose This", lines=12)
    llm_out = gr.Textbox(label="Copy for LLM (Claude / GPT / Any)", lines=12)

    warning_out = gr.Markdown(value=warning_block())

    with gr.Row():
        notes_out = gr.Markdown(value=prompt_notes())
        template_out = gr.Markdown(value=prompt_template())

    outputs = [markdown_out, stats_out, report_out, llm_out, warning_out, notes_out, template_out]

    auto_btn.click(fn=run_agent, inputs=[url, file], outputs=outputs)
    compact_btn.click(fn=run_manual_compact, inputs=[url, file], outputs=outputs)

demo.launch()
