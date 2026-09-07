import os
from typing import Any

from llm import (
    LLMSettings,
    apply_settings_to_env,
    build_client,
    format_ollama_error,
    is_connection_error,
    load_settings,
    validate_settings,
)
from run_limits import MAX_AI_HISTORY_MESSAGES


def _base_socratiq_prompt() -> str:
    return """You are SocratiQ, a programming tutor in BaseLayer.

Your job is to help the learner understand the current exercise and solve it
themselves — never hand over the finished answer. Lessons in BaseLayer are
verified by automated tests, but those test files are NOT part of your context:
never reconstruct, quote, or hint at their assertions or expected values. Ground
every answer only in the exercise instructions and in the learner's own code and
messages.

Use the conversation history for continuity: remember the hints you already gave
and build on them instead of repeating yourself. When the learner shares an
error, first ask what the traceback or message tells them before jumping in."""


def _style_instruction(style: str) -> str:
    style = (style or "solveit").lower()
    guidance = {
        "solveit": """## Tutor style: Solveit
Guide the learner through the Solve It method, one small verified step at a time:
- S - State the problem: ask the learner to restate the task, inputs, outputs, and constraints.
- O - Outline the logic: sketch the flow or pseudocode before writing code.
- L - Locate the tools: identify which constructs (loops, conditionals, data structures) are needed.
- V - Verify & execute: have the learner run tiny experiments and inspect the output on small toy data (3-5 items).
- E - Evaluate: ask why the code works and how it could be improved.
Keep each step to 1-3 logical lines. Never write the complete solution. End with exactly one Socratic question.""",
        "socratic": """## Tutor style: Socratic
Guide through pointed questions before revealing any answer. Break the problem
into atomic micro-lessons: do not move to concept B until the learner shows
mastery of concept A. When the learner shares an error, do not fix it — ask what
the traceback tells them. Never give the full solution. End with exactly one
probing question to keep the learner in the driver's seat.""",
        "direct": """## Tutor style: Direct
Be clear and direct. Give concise, correct explanations and name the exact
theoretical rule the learner is missing, with minimal preamble. Small unrelated
syntax examples are fine, but never write the learner's solution for them —
always leave the final step to the learner.""",
        "blooms": """## Tutor style: Bloom's taxonomy
Structure guidance through Bloom's levels: remember, understand, apply, analyze,
evaluate, and create. Anchor on the learner's current code and move them up one
level at a time instead of revealing the finished solution.""",
    }
    return guidance.get(style, guidance["solveit"])


def _understanding_level_instruction(level: str) -> str:
    level = (level or "intermediate").lower()
    guidance = {
        "beginner": (
            "The learner is at a beginner level: focus on foundational concepts, "
            "definitions, and straightforward applications. Assume little to no prior knowledge."
        ),
        "intermediate": (
            "The learner is at an intermediate level: emphasize problem-solving, "
            "system design, and practical implementation on top of core concepts."
        ),
        "advanced": (
            "The learner is at an advanced level: challenge them to analyze, optimize, "
            "and innovate rather than re-explain fundamentals."
        ),
    }
    return guidance.get(level, guidance["intermediate"])


def _explanation_length_instruction(length: str) -> str:
    length = (length or "short").lower()
    if length == "thorough":
        return (
            "Give thorough explanations: context, why it matters, and analogies "
            "before moving into practice."
        )
    return (
        "Keep explanations concise: the essential rule in a few sentences, then "
        "transition quickly to practice."
    )


def build_system_prompt(profile: dict[str, Any] | None = None, style: str | None = None) -> str:
    """Build the stable SocratiQ system prompt for a learner profile.

    ``profile`` is the parsed structure returned by
    ``learner_profile.get_or_create_profile`` (i.e. ``{"frontmatter": {...}, ...}``).
    The profile's ``tutor_style`` is the single source of truth for tutoring
    style; ``style`` may override it for an individual request.
    """
    frontmatter = (profile or {}).get("frontmatter") or {}
    effective_style = style or frontmatter.get("tutor_style") or "solveit"

    sections = [
        _base_socratiq_prompt(),
        _style_instruction(effective_style),
        _understanding_level_instruction(frontmatter.get("understanding_level") or "intermediate"),
        _explanation_length_instruction(frontmatter.get("explanation_length") or "short"),
    ]
    return "\n\n".join(sections)


class AIService:
    def __init__(self):
        self.client = None
        self.settings: LLMSettings = load_settings()
        if self.settings.is_configured:
            self._connect(self.settings)
        else:
            print("AI is optional: no LLM provider configured.")

    def _connect(self, settings: LLMSettings) -> None:
        self.settings = settings
        apply_settings_to_env(settings)
        try:
            self.client = build_client(settings)
        except Exception as exc:
            print(f"Warning: could not create LLM client: {exc}")
            self.client = None

    def check_connection(self, settings: LLMSettings | None = None) -> tuple[bool, str]:
        target = settings or self.settings
        if target.provider == "ollama":
            base = (target.effective_base() or "http://localhost:11434/v1").rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            if not base:
                base = "http://localhost:11434"
            try:
                import requests

                res = requests.get(f"{base}/", timeout=3.0)
                if res.status_code == 200:
                    return True, f"Successfully reached Ollama at {base}."
            except Exception as exc:
                return False, format_ollama_error(exc, base)
            return (
                False,
                f"Could not reach Ollama at {base}. Make sure Ollama is running (`ollama serve`).",
            )

        return True, f"Provider {target.provider} is configured."

    def configure(
        self,
        provider: str,
        api_key: str = "",
        model: str | None = None,
        api_base: str | None = None,
    ) -> LLMSettings:
        settings = validate_settings(provider, api_key=api_key, model=model, api_base=api_base)
        self._connect(settings)
        return settings

    def configure_key(self, api_key: str):
        """Backward-compatible helper: treat a bare key as Gemini (AI Studio)."""
        provider = self.settings.provider or "gemini"
        self.configure(provider=provider, api_key=api_key, model=self.settings.model or None)

    @property
    def is_configured(self) -> bool:
        return self.client is not None and self.settings.is_configured

    @property
    def has_key(self) -> bool:
        return self.settings.has_key or bool(
            os.environ.get("LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )

    def complete(self, prompt: str) -> str:
        if not self.is_configured:
            raise RuntimeError("AI service not configured")
        return self._chat_complete([{"role": "user", "content": prompt}])

    def _chat_complete(self, messages: list[dict[str, Any]]) -> str:
        """Send an OpenAI-compatible ``messages`` payload to the configured model."""
        if not self.is_configured:
            raise RuntimeError("AI service not configured")
        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            if self.settings.provider == "ollama" and is_connection_error(exc):
                raise RuntimeError(
                    format_ollama_error(exc, self.settings.effective_base())
                ) from exc
            raise

    def _complete_multimodal(self, prompt: str, images: list[tuple[bytes, str]]) -> str:
        import base64 as b64

        if not self.is_configured:
            raise RuntimeError("AI service not configured")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for data, mime in images:
            encoded = b64.b64encode(data).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                }
            )

        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=[{"role": "user", "content": content}],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            if self.settings.provider == "ollama" and is_connection_error(exc):
                raise RuntimeError(
                    format_ollama_error(exc, self.settings.effective_base())
                ) from exc
            raise

    def run_agentic_course_builder(
        self,
        topic: str,
        materials: str = "",
        username: str = "",
        courses_dir: Any = None,
    ) -> Any:
        from agentic_workflow import AgenticCourseWorkflow

        workflow = AgenticCourseWorkflow(
            generate_text=self.complete if self.is_configured else None,
            courses_dir=courses_dir,
        )
        return workflow.execute(topic=topic, materials=materials, username=username)

    def chat(
        self,
        history: list[dict[str, Any]] | None = None,
        context: str = "",
        profile: dict[str, Any] | None = None,
        style: str | None = None,
    ) -> str:
        """Have a multi-turn conversation with SocratiQ.

        ``history`` is an ordered list of ``{"role": ..., "content": ...}`` turns
        (roles ``user``/``assistant``). The system prompt is built server-side from
        the learner's profile (tutor style + understanding level + explanation
        length); ``context`` is the current exercise context for this turn. The
        history is trimmed to the last ``MAX_AI_HISTORY_MESSAGES`` turns so token
        limits stay bounded.
        """
        if not self.is_configured:
            return "AI service not configured."

        system_prompt = build_system_prompt(profile, style)
        if context and context.strip():
            system_prompt = (
                f"{system_prompt}\n\n---\n\n### Current exercise context "
                f"(this changes each turn)\n{context.strip()}"
            )

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for turn in (history or [])[-MAX_AI_HISTORY_MESSAGES:]:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        if not any(m["role"] in ("user", "assistant") for m in messages):
            messages.append({"role": "user", "content": "Hello."})

        try:
            return self._chat_complete(messages)
        except Exception as e:
            if self.settings.provider == "ollama" and is_connection_error(e):
                return format_ollama_error(e, self.settings.effective_base())
            return f"Error communicating with AI: {str(e)}"

    def evaluate_drawing(
        self,
        instructions: str,
        question_img_bytes: bytes,
        sketch_img_bytes: bytes,
        solution_img_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            return {"error": "AI service not configured"}

        solution_ref_text = ""
        if solution_img_bytes:
            solution_ref_text = (
                "\n3. Look at the THIRD image provided (the 'solution.png' reference answer)."
            )

        prompt = f"""
        You are an expert tutor grading a visual exercise.

        **Instructions for the student:**
        {instructions}

        **Your Task:**
        1. Look at the FIRST image provided (the background diagram 'question.png').
        2. Look at the SECOND image provided (the student's drawing 'sketch.png').{solution_ref_text}
        3. Evaluate if the student correctly followed the instructions, then grade them
           against a short, structured rubric so the learner knows exactly what to fix.
        4. **Flexibility is Key**: If the student demonstrates the correct *idea* or *intent*,
           even if the drawing is imperfect, the intent check should PASS.
        5. Focus on the core concept being taught. Minor aesthetic issues or slight inaccuracies
           that don't compromise the understanding of the concept should be ignored.
        6. {"If a solution image was provided, ensure the student's sketch matches the intent of the solution." if solution_img_bytes else ""}

        Produce 3 rubric checks that map to the exercise:
        - "intent": does the drawing show the intended concept/structure (correct layers, labels, order)?
        - "missing": are required edges/elements/labels absent or incorrect?
        - "extra": are there irrelevant or wrong extra marks that obscure the answer?
        Adapt the labels to the specific exercise (e.g. name the required layers/parts).

        Provide the result in raw JSON format (no markdown) with EXACTLY this shape:
        {{
            "passed": boolean,
            "score": float (0.0 to 1.0),
            "message": "One or two sentence overall feedback for the student",
            "checks": [
                {{"label": "Intent matches the instructions", "passed": boolean, "feedback": "short actionable note"}},
                {{"label": "No missing required elements", "passed": boolean, "feedback": "short actionable note"}},
                {{"label": "No extra or confusing marks", "passed": boolean, "feedback": "short actionable note"}}
            ]
        }}
        "passed" must be true only when every check passed.
        """

        try:
            images = [
                (question_img_bytes, "image/png"),
                (sketch_img_bytes, "image/png"),
            ]
            if solution_img_bytes:
                images.append((solution_img_bytes, "image/png"))

            text = self._complete_multimodal(prompt, images)
            return self._parse_drawing_result(text)
        except Exception as e:
            print(f"Error in evaluate_drawing: {e}")
            if self.settings.provider == "ollama" and is_connection_error(e):
                return {"error": format_ollama_error(e, self.settings.effective_base())}
            return {"error": f"AI evaluation failed: {str(e)}"}

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value or "").strip().lower() == "true"

    def _parse_drawing_result(self, text: str) -> dict[str, Any]:
        """Parse the model's JSON into a stable drawing-grading result dict."""
        parsed = self._extract_json_object(text)
        if not isinstance(parsed, dict):
            return {
                "passed": "pass" in text.lower() or "correct" in text.lower(),
                "score": 1.0 if "pass" in text.lower() else 0.0,
                "message": text,
                "checks": [],
            }

        checks = parsed.get("checks")
        checks_list: list[dict[str, Any]] = []
        if isinstance(checks, list):
            for item in checks:
                if not isinstance(item, dict):
                    continue
                checks_list.append(
                    {
                        "label": str(item.get("label", "Rubric check")),
                        "passed": self._coerce_bool(item.get("passed")),
                        "feedback": str(item.get("feedback", "")),
                    }
                )
        checks_list = checks_list[:5]
        passed = (
            all(c["passed"] for c in checks_list)
            if checks_list
            else self._coerce_bool(parsed.get("passed"))
        )

        score = parsed.get("score")
        if isinstance(score, bool):
            score = 1.0 if score else 0.0
        if not isinstance(score, (int, float)):
            score = 1.0 if passed else 0.0
        message = str(parsed.get("message") or text).strip()

        return {
            "passed": passed,
            "score": float(score),
            "message": message,
            "checks": checks_list,
        }

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        """Locate and parse the first balanced top-level JSON object in ``text``."""
        import json as json_lib

        decoder = json_lib.JSONDecoder()
        for i, char in enumerate(text):
            if char != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(text[i:])
            except json_lib.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
        return None


ai_service = AIService()
