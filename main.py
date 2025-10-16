"""
codex-dspy - DSPy module for OpenAI Codex SDK

For usage examples, see example_usage.py or visit:
https://github.com/darinkishore/codex_dspy
"""


def main():
    print("codex-dspy: DSPy module for OpenAI Codex SDK")
    print()
    print("Quick start:")
    print("  import dspy")
    print("  from codex_agent import CodexAgent")
    print()
    print("  sig = dspy.Signature('message:str -> answer:str')")
    print("  agent = CodexAgent(sig, working_directory='.')")
    print("  result = agent(message='Hello!')")
    print()
    print("For more examples, see example_usage.py")
    print("Documentation: https://github.com/darinkishore/codex_dspy#readme")


if __name__ == "__main__":
    main()
