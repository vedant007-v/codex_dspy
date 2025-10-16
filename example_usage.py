"""Example usage of CodexAgent with string and Pydantic outputs."""

from pydantic import BaseModel, Field

import dspy
from codex import SandboxMode

from codex_agent import CodexAgent


def example_1_string_output():
    """Example 1: Simple string output - ask agent about files."""
    print("=" * 60)
    print("Example 1: String Output")
    print("=" * 60)

    # Create signature with string input and output
    sig = dspy.Signature("message:str -> answer:str")

    # Create agent (starts new thread)
    agent = CodexAgent(
        sig,
        working_directory=".",
        sandbox_mode=SandboxMode.READ_ONLY,  # Safe: no file modifications
        codex_path_override="/opt/homebrew/bin/codex",
    )

    # Call agent
    result = agent(message="What files are in this directory? List the top 5.")

    # Access results
    print(f"\nAnswer: {result.answer}")
    print(f"\nThread ID: {agent.thread_id}")
    print(f"\nUsage: {result.usage}")
    print(f"\nTrace items ({len(result.trace)}):")
    for item in result.trace:
        print(f"  - {item.type}: {item.id}")

    # Multi-turn: continue same thread
    print("\n" + "-" * 60)
    print("Continuing conversation...")
    print("-" * 60)

    result2 = agent(message="What about Python files specifically?")
    print(f"\nAnswer: {result2.answer}")
    print(f"Thread ID (same): {agent.thread_id}")


def example_2_pydantic_output():
    """Example 2: Structured Pydantic output - analyze repo."""
    print("\n" + "=" * 60)
    print("Example 2: Pydantic Typed Output")
    print("=" * 60)

    # Define Pydantic model for structured output
    class RepoAnalysis(BaseModel):
        """Analysis of a repository."""

        total_files: int = Field(description="Total number of files")
        python_files: int = Field(description="Number of Python files")
        key_files: list[str] = Field(description="Most important files (3-5)")
        summary: str = Field(description="One sentence summary")

    # Create signature with Pydantic output type
    sig = dspy.Signature("message:str -> analysis:RepoAnalysis")

    # Create agent
    agent = CodexAgent(
        sig,
        working_directory=".",
        sandbox_mode=SandboxMode.READ_ONLY,
        codex_path_override="/opt/homebrew/bin/codex",
    )

    # Call agent with structured output request
    result = agent(message="Analyze the structure of this repository")

    # Access typed results
    print(f"\nAnalysis (typed):")
    print(f"  Total files: {result.analysis.total_files}")
    print(f"  Python files: {result.analysis.python_files}")
    print(f"  Key files: {result.analysis.key_files}")
    print(f"  Summary: {result.analysis.summary}")

    print(f"\nThread ID: {agent.thread_id}")
    print(f"Usage: {result.usage}")


def example_3_with_description():
    """Example 3: Using output field description."""
    print("\n" + "=" * 60)
    print("Example 3: Output Field with Description")
    print("=" * 60)

    # Create signature with description on output field
    class AnalysisSignature(dspy.Signature):
        """Analyze repository architecture."""

        message: str = dspy.InputField()
        analysis: str = dspy.OutputField(
            desc="A detailed analysis in markdown format with sections for: "
            "1) Architecture overview, 2) Key components, 3) Dependencies"
        )

    # Create agent
    agent = CodexAgent(
        AnalysisSignature,
        working_directory=".",
        sandbox_mode=SandboxMode.READ_ONLY,
        codex_path_override="/opt/homebrew/bin/codex",
    )

    # The description will be appended to the message automatically
    result = agent(message="Analyze this codebase")

    print(f"\nAnalysis:\n{result.analysis}")
    print(f"\nThread ID: {agent.thread_id}")


if __name__ == "__main__":
    # Run all examples
    example_1_string_output()
    example_2_pydantic_output()
    example_3_with_description()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
