"""ThinkAi CLI - 命令行工具"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="thinkai",
        description="ThinkAi - Enterprise-grade AI Framework CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # version
    subparsers.add_parser("version", help="Show version")

    # chat
    chat_parser = subparsers.add_parser("chat", help="Chat with AI")
    chat_parser.add_argument("message", help="Your message")
    chat_parser.add_argument("--provider", default="ollama", help="Provider name")
    chat_parser.add_argument("--model", default=None, help="Model name")
    chat_parser.add_argument("--api-key", default=None, help="API key")

    # providers
    subparsers.add_parser("providers", help="List available providers")

    # config
    subparsers.add_parser("config", help="Show configuration")

    args = parser.parse_args()

    if args.command == "version":
        from thinkai import __version__

        print(f"ThinkAi v{__version__}")

    elif args.command == "chat":
        from thinkai.sync import SyncThinkAI

        kwargs = {"provider": args.provider}
        if args.model:
            kwargs["model"] = args.model
        if args.api_key:
            kwargs["api_key"] = args.api_key

        try:
            ai = SyncThinkAI(**kwargs)
            response = ai.chat(args.message)
            print(response.content or "(no response)")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "providers":
        from thinkai.providers.registry import registry

        providers = registry.list()
        if providers:
            print("Available providers:")
            for name, cls in providers.items():
                print(f"  - {name}: {cls.__doc__ or cls.name}")
        else:
            print("No providers registered.")

    elif args.command == "config":
        from thinkai.core.config import Settings

        config = Settings()
        import json

        print(json.dumps(config.to_dict(), indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
