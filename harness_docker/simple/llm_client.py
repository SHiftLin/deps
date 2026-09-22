import json
import os
import time
import httpx
import openai
import anthropic
import utils
import dotenv

dotenv.load_dotenv(utils.REPO / ".key")

_CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
_GPT_API_KEY = os.environ.get("GPT_API_KEY")
_DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

DEFAULT_BASE_URLS = {
    "anthropic": "https://api.anthropic.com",
    "responses": "https://api.openai.com/v1",
    "chat": "https://api.deepseek.com",
}

REQUEST_TIMEOUT = httpx.Timeout(connect=15.0, read=float(os.getenv("LLM_READ_TIMEOUT", 360)), write=60.0, pool=15.0)

# Max output tokens, applied to every backend
# (Anthropic streams because this exceeds its non-streaming limit).
MAX_TOKENS = 64000


def with_retry(fn, *, tries=5, base=4.0):
    """Call fn() retrying transient API errors (connection/timeout/rate-limit/5xx)
    with exponential backoff. re raises the last error if all tries fail."""
    for attempt in range(tries):
        try:
            return fn()
        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError, openai.InternalServerError, openai.ConflictError,
                anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as e:
            if attempt == tries - 1:
                raise
            wait = base * (2 ** attempt)
            print(f"  [llm] {type(e).__name__}; retry {attempt + 1}/{tries - 1} in {wait:.0f}s",
                  flush=True)
            time.sleep(wait)


class ChatLog:
    def __init__(self, log_name):
        self.log_name = log_name
        self.round = 1
        os.makedirs(os.path.dirname(log_name) or ".", exist_ok=True)
        open(log_name, 'w').close()
        self.delimiter = ''.join(["="] * 32)

    def append(self, messages):
        with open(self.log_name, 'a') as fout:
            if isinstance(messages, dict):
                messages = [messages]
            if isinstance(messages, list):
                for message in messages:
                    fout.write(f"#{self.round} {message['role']}:\n")
                    fout.write(message["content"] + '\n')
                    fout.write(self.delimiter + '\n')
                    if message["role"] == "assistant":
                        self.round += 1


class LLMClient:
    """Unified interface over Responses API, Anthropic Messages API, and Chat Completions API.

    "codex"  in model  ->  Responses API          (stateful, server-side history)
    "claude" in model  ->  Anthropic Messages API  (native SDK, streaming)
    otherwise          ->  Chat Completions API    (stateless, client-side history)
    """

    def __init__(self, model: str, system_prompt: str, tools: list | None,
                 chatlog: ChatLog, tool_executor, temperature: float | None = None,
                 base_url: str | None = None):
        """
        tool_executor: callable (name: str, args: dict) -> str
        temperature: pinned sampling temperature (None = provider default). Use 0
        for judges/deterministic checks, a low value (~0.2) for repair.
        base_url: custom API endpoint (None = the selected provider's official URL).
        """
        self.model = model
        if "codex" in model:
            self._api = "responses"
        elif "claude" in model:
            self._api = "anthropic"
        else:
            self._api = "chat"
        self.temperature = temperature
        if self.temperature is not None and self._api != "chat":
            print(f"  [llm] temperature is only applied to the chat backend; "
                  f"ignored for '{self._api}' ({model})", flush=True)
        if base_url is None:
            base_url = DEFAULT_BASE_URLS[self._api]
        if self._api == "anthropic":
            self._client = anthropic.Anthropic(base_url=base_url,
                                               api_key=_CLAUDE_API_KEY, timeout=REQUEST_TIMEOUT, max_retries=0)
        elif self._api == "responses":
            self._client = openai.OpenAI(base_url=base_url,
                                         api_key=_GPT_API_KEY, timeout=REQUEST_TIMEOUT, max_retries=0)
        else:
            self._client = openai.OpenAI(base_url=base_url, api_key=_DEEPSEEK_API_KEY,
                                         timeout=REQUEST_TIMEOUT, max_retries=0)

        if self._api == "responses":
            self._prev_id = None
            self._tools = tools
        elif self._api == "anthropic":
            # Anthropic takes the system prompt as a top-level arg, so it is not
            # prepended to the message list. Tools use "input_schema", not "parameters".
            self._messages = []
            self._tools = [{"name": t["name"],
                            "description": t["description"],
                            "input_schema": t["parameters"]} for t in tools] if tools else None
        else:
            self._messages = [{"role": "system", "content": system_prompt}]
            self._tools = [{"type": "function",
                            "function": {
                                "name": t["name"],
                                "description": t["description"],
                                "parameters": t["parameters"]
                            }} for t in tools] if tools else None

        self._system_prompt = system_prompt
        self._chatlog = chatlog
        self._chatlog.append({"role": "system", "content": system_prompt})

        self._tool_executor = tool_executor
        self._tool_outputs = []
        self._tool_log = ''

    def call_llm(self, user_msg: str) -> tuple:
        """Call LLM; return (output_text, tool_calls)."""
        self._chatlog.append(
            {"role": "user", "content": self._tool_log + user_msg})

        if self._api == "responses":
            # copy: don't mutate _tool_outputs
            input_items = list(self._tool_outputs)
            if user_msg:
                input_items.append({"role": "user", "content": user_msg})
            kwargs = dict(model=self.model, instructions=self._system_prompt,
                          input=input_items, tools=self._tools,
                          max_output_tokens=MAX_TOKENS)
            if self._prev_id:
                kwargs["previous_response_id"] = self._prev_id
            resp = with_retry(lambda: self._client.responses.create(**kwargs))
            self._prev_id = resp.id
            output_text = resp.output_text or ''
            tool_calls = [
                item for item in resp.output if item.type == "function_call"]
        elif self._api == "anthropic":
            # Feed any pending tool results back as a single user message.
            if self._tool_outputs:
                self._messages.append({"role": "user",
                                       "content": [{
                                           "type": "tool_result",
                                           "tool_use_id": o["call_id"],
                                           "content": o["output"]
                                       } for o in self._tool_outputs]})
            if user_msg:
                self._messages.append({"role": "user", "content": user_msg})

            # Stream because MAX_TOKENS exceeds the SDK's non-streaming limit.
            kwargs = dict(model=self.model, max_tokens=MAX_TOKENS,
                          system=self._system_prompt, messages=self._messages)
            if self._tools:
                kwargs["tools"] = self._tools

            def _stream():
                with self._client.messages.stream(**kwargs) as stream:
                    return stream.get_final_message()
            resp = with_retry(_stream)

            # Echo the full assistant content back for the next turn.
            self._messages.append(
                {"role": "assistant", "content": resp.content})
            output_text = "".join(
                b.text for b in resp.content if b.type == "text")
            tool_calls = [b for b in resp.content if b.type == "tool_use"]
        else:
            self._messages.extend({"role": "tool",
                                   "tool_call_id": o["call_id"],
                                   "content": o["output"]}
                                  for o in self._tool_outputs)
            if user_msg:
                self._messages.append({"role": "user", "content": user_msg})
            kw = {} if self.temperature is None else {"temperature": self.temperature}
            resp = with_retry(lambda: self._client.chat.completions.create(
                model=self.model, messages=self._messages, tools=self._tools,
                max_tokens=MAX_TOKENS, **kw))
            message = resp.choices[0].message
            self._messages.append(message)
            output_text = message.content or ''
            tool_calls = message.tool_calls or []

        assistant_log = f"[TEXT]\n{output_text}\n" if output_text else ''
        if tool_calls:
            tool_lines = []
            for tc in tool_calls:
                if self._api == "responses":
                    name, arguments = tc.name, tc.arguments
                elif self._api == "anthropic":
                    name, arguments = tc.name, json.dumps(tc.input)
                else:
                    name, arguments = tc.function.name, tc.function.arguments
                tool_lines.append(f"{name}({arguments})")
            assistant_log += "[TOOL_CALLS]\n" + "\n".join(tool_lines) + "\n"
        self._chatlog.append({"role": "assistant", "content": assistant_log})

        # Reset here so a second run of call_llm doesn't resend tool outputs
        self._tool_outputs = []
        self._tool_log = ''
        return output_text, tool_calls

    def run_tools(self, tool_calls) -> list:
        """Execute tool calls; update _tool_outputs/_tool_log; return tool_outputs."""
        log_parts = []
        for tc in tool_calls:
            if self._api == "anthropic":
                name, args, call_id = tc.name, tc.input, tc.id  # input is already a dict
            elif self._api == "responses":
                name, args, call_id = tc.name, json.loads(
                    tc.arguments), tc.call_id
            else:
                name, args, call_id = tc.function.name, json.loads(
                    tc.function.arguments), tc.id
            result = self._tool_executor(name, args)
            self._tool_outputs.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
                "name": name,
            })
            log_parts.append(f"[TOOL: {name}]\n{result}")
        self._tool_log = "\n".join(log_parts) + '\n' if log_parts else ''
        return self._tool_outputs

    # def step(self, user_msg: str = '') -> tuple:
    #     """Send user_msg; return (output_text, tool_outputs)."""
    #     output_text, tool_calls = self.call_llm(user_msg)
    #     tool_outputs = self.run_tools(tool_calls)
    #     return output_text, tool_outputs

    def mark_result(self, result: str):
        self._chatlog.append(
            {"role": "result", "content": self._tool_log + result})
        self._tool_outputs = []
        self._tool_log = ''


if __name__ == "__main__":
    # Smoke test for all three backends (anthropic / responses / chat).
    SYSTEM = "You are a helpful assistant. Use the tool when needed, then answer."
    # Tools use the Responses flat format ({"type": "function", ...}); the
    # anthropic and chat branches read name/description/parameters and ignore "type".
    TOOLS = [{
        "type": "function",
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    }]

    def handle(name, args):
        if name == "get_weather":
            return f"{args['city']}: 22°C, sunny"
        return "unknown tool"

    def tc_name(tc):
        # Tool-call objects differ per backend: anthropic/responses expose .name,
        # chat completions nests it under .function.name.
        return getattr(tc, "name", None) or tc.function.name

    def run(model):
        print(f"\n{'=' * 50}\n{model}\n{'=' * 50}")
        client = LLMClient(model, SYSTEM, TOOLS,
                           ChatLog(f"test_{model}.log"), handle)
        text, tool_calls = client.call_llm("What's the weather in Paris?")
        turn = 1
        print(
            f"--- turn {turn} ---\n{text}\ntool_calls={[tc_name(t) for t in tool_calls]}")
        while tool_calls:
            client.run_tools(tool_calls)
            turn += 1
            text, tool_calls = client.call_llm("")
            print(
                f"--- turn {turn} ---\n{text}\ntool_calls={[tc_name(t) for t in tool_calls]}")

    run("claude-opus-4-8")     # -> Anthropic Messages API
    run("gpt-5.1-codex")       # -> Responses API
    run("deepseek-v4-pro")     # -> Chat Completions API
