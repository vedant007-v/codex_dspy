"""CodexAgent - DSPy module wrapping OpenAI Codex SDK.

This module provides a signature-driven interface to the Codex agent SDK.
Each CodexAgent instance maintains a stateful thread that accumulates context
across multiple forward() calls.
"""

from typing import Any, Optional, Union, get_args, get_origin

from pydantic import BaseModel

import dspy
from dspy.primitives.prediction import Prediction
from dspy.signatures.signature import Signature, ensure_signature

from codex import Codex, CodexOptions, SandboxMode, ThreadOptions, TurnOptions


def _is_str_type(annotation: Any) -> bool:
    """Check if annotation is str or Optional[str].

    Args:
        annotation: Type annotation to check

    Returns:
        True if annotation is str, Optional[str], or Union[str, None]
    """
    if annotation == str:
        return True

    origin = get_origin(annotation)
    if origin is Union:
        args = get_args(annotation)
        # Check for Optional[str] which is Union[str, None]
        if len(args) == 2 and str in args and type(None) in args:
            return True

    return False


class CodexAgent(dspy.Module):
    """DSPy module for Codex SDK integration.

    Creates a stateful agent where each instance maintains one conversation thread.
    Multiple forward() calls on the same instance continue the same conversation.

    Args:
        signature: DSPy signature (must have exactly 1 input and 1 output field)
        working_directory: Directory where Codex agent will execute commands
        model: Model to use (e.g., "gpt-4", "gpt-4-turbo"). Defaults to Codex default.
        sandbox_mode: Execution sandbox level (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
        skip_git_repo_check: Allow non-git directories as working_directory
        api_key: OpenAI API key (falls back to CODEX_API_KEY env var)
        base_url: API base URL (falls back to OPENAI_BASE_URL env var)
        codex_path_override: Override path to codex binary (for testing)

    Example:
        >>> sig = dspy.Signature('message:str -> answer:str')
        >>> agent = CodexAgent(sig, working_directory=".")
        >>> result = agent(message="What files are in this directory?")
        >>> print(result.answer)  # str response
        >>> print(result.trace)   # list of items (commands, files, etc.)
        >>> print(result.usage)   # token counts

    Example with Pydantic output:
        >>> class BugReport(BaseModel):
        ...     severity: str
        ...     description: str
        >>> sig = dspy.Signature('message:str -> report:BugReport')
        >>> agent = CodexAgent(sig, working_directory=".")
        >>> result = agent(message="Analyze the bug")
        >>> print(result.report.severity)  # typed access
    """

    def __init__(
        self,
        signature: str | type[Signature],
        working_directory: str,
        model: Optional[str] = None,
        sandbox_mode: Optional[SandboxMode] = None,
        skip_git_repo_check: bool = False,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        codex_path_override: Optional[str] = None,
    ):
        super().__init__()

        # Ensure signature is valid
        self.signature = ensure_signature(signature)

        # Validate: exactly 1 input field, 1 output field
        if len(self.signature.input_fields) != 1:
            input_fields = list(self.signature.input_fields.keys())
            raise ValueError(
                f"CodexAgent requires exactly 1 input field, got {len(input_fields)}: {input_fields}\n"
                f"Example: dspy.Signature('message:str -> answer:str')"
            )

        if len(self.signature.output_fields) != 1:
            output_fields = list(self.signature.output_fields.keys())
            raise ValueError(
                f"CodexAgent requires exactly 1 output field, got {len(output_fields)}: {output_fields}\n"
                f"Example: dspy.Signature('message:str -> answer:str')"
            )

        # Extract field names and types
        self.input_field = list(self.signature.input_fields.keys())[0]
        self.output_field = list(self.signature.output_fields.keys())[0]
        self.output_field_info = self.signature.output_fields[self.output_field]
        self.output_type = self.output_field_info.annotation

        # Create Codex client
        self.client = Codex(
            options=CodexOptions(
                api_key=api_key,
                base_url=base_url,
                codex_path_override=codex_path_override,
            )
        )

        # Start thread (1 agent instance = 1 stateful thread)
        self.thread = self.client.start_thread(
            options=ThreadOptions(
                working_directory=working_directory,
                model=model,
                sandbox_mode=sandbox_mode,
                skip_git_repo_check=skip_git_repo_check,
            )
        )

    def forward(self, **kwargs) -> Prediction:
        """Execute agent with input message.

        Args:
            **kwargs: Must contain the input field specified in signature

        Returns:
            Prediction with:
                - Typed output field (name from signature)
                - trace: list[ThreadItem] - chronological items (commands, files, etc.)
                - usage: Usage - token counts (input_tokens, cached_input_tokens, output_tokens)

        Raises:
            ValueError: If Pydantic parsing fails for typed output
        """
        # 1. Extract input message
        message = kwargs[self.input_field]

        # 2. Append output field description if present (skip DSPy's default ${field_name} placeholder)
        output_desc = (self.output_field_info.json_schema_extra or {}).get("desc")
        # Skip if desc is just DSPy's default placeholder (e.g., "${answer}" for field named "answer")
        if output_desc and output_desc != f"${{{self.output_field}}}":
            message = f"{message}\n\nPlease produce the following output: {output_desc}"

        # 3. Build TurnOptions if output type is not str
        turn_options = None
        if not _is_str_type(self.output_type):
            # Get Pydantic JSON schema and ensure additionalProperties is false
            schema = self.output_type.model_json_schema()
            if "additionalProperties" not in schema:
                schema["additionalProperties"] = False
            turn_options = TurnOptions(output_schema=schema)

        # 4. Call Codex SDK
        result = self.thread.run(message, turn_options)

        # 5. Parse response
        parsed_output = result.final_response

        if not _is_str_type(self.output_type):
            # Parse as Pydantic model
            try:
                parsed_output = self.output_type.model_validate_json(result.final_response)
            except Exception as e:
                # Provide helpful error with response preview
                response_preview = result.final_response[:500]
                if len(result.final_response) > 500:
                    response_preview += "..."
                raise ValueError(
                    f"Failed to parse Codex response as {self.output_type.__name__}: {e}\n"
                    f"Response: {response_preview}"
                ) from e

        # 6. Return Prediction with typed output + trace + usage
        return Prediction(
            **{self.output_field: parsed_output},
            trace=result.items,
            usage=result.usage,
        )

    @property
    def thread_id(self) -> Optional[str]:
        """Get thread ID for this agent instance.

        The thread ID is assigned after the first forward() call.
        Useful for debugging and visibility into the conversation state.

        Returns:
            Thread ID string, or None if no forward() calls have been made yet
        """
        return self.thread.id
