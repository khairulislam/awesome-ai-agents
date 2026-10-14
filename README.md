# Awesome AI Agents

A curated collection of AI agent projects, each built as a self-contained, runnable example. The current series uses [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) to build a blog-writing agent, adding capabilities with each project.

## Projects

| Project | Description | Key Concepts |
| --- | --- | --- |
| [build-ai-agent-google-adk](build-ai-agent-google-adk/) | A baseline blog-writing agent that plans, drafts, and validates content without external tools. | Workflow graph, structured output, review-and-retry loops |
| [build-mcp-agent-google-adk](build-mcp-agent-google-adk/) | Extends the baseline agent with a Google Trends MCP server so posts are grounded in current search interest. | Model Context Protocol, stdio tool server, tool-augmented agents |

## Architecture

Both projects share the same workflow. A planner produces a structured outline, a writer drafts the article, and a deterministic review step validates each output, returning it for revision with specific feedback when it falls short.

```text
START → remember_topic → [trend_scout → make_brief]* → blog_planner ⇄ review_outline
                                                               ↓
                                          blog_writer ⇄ review_post → format_post

* MCP project only
```

## Getting Started

**Prerequisites:** Python 3.10 or later, and either a Google AI Studio API key or an OpenRouter API key.

```bash
git clone https://github.com/<your-username>/awesome-ai-agents.git
cd awesome-ai-agents/<project-directory>

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

adk web .
```

Each project directory contains its own README with detailed configuration and usage instructions.

## Model Configuration

Set the `MODEL` variable in each project's `.env` file:

- **Gemini (native):** a plain model name, such as `gemini-flash-latest`, with `GOOGLE_API_KEY` set.
- **OpenRouter (via LiteLLM):** a `provider/model` identifier, with `OPENROUTER_API_KEY` set. Use `REASONING_EFFORT` (`low`, `medium`, or `high`) to control reasoning depth for models that support it.

## Acknowledgements

Adapted from [smithakolan/awesome-ai-agents](https://github.com/smithakolan/awesome-ai-agents).

## License

Distributed under the terms of the [LICENSE](LICENSE) file included in this repository.
