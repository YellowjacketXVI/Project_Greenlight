"""
Greenlight Main Entry Point

Run the Greenlight application.
"""

import sys
import argparse
from pathlib import Path

from greenlight.core.logging_config import setup_logging, get_logger
from greenlight.core.config import load_config
from greenlight.core.startup import validate_environment


def main():
    """Main entry point for the Greenlight application."""
    parser = argparse.ArgumentParser(
        description="Project Greenlight - AI-Powered Cinematic Storyboard Generation"
    )

    parser.add_argument(
        "--project", "-p",
        type=str,
        help="Path to project folder to open"
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Enable verbose logging (default: True)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in headless mode (CLI only)"
    )

    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Run only the FastAPI backend (no frontend)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the API server (default: 8000)"
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip API key validation at startup"
    )

    args = parser.parse_args()

    # Setup logging
    from greenlight.core.logging_config import LogLevel
    if args.debug:
        log_level = LogLevel.DEBUG
    elif args.verbose:
        log_level = LogLevel.INFO
    else:
        log_level = LogLevel.WARNING
    setup_logging(level=log_level, verbose=args.verbose)

    logger = get_logger("main")
    logger.info("Starting Project Greenlight...")

    # Validate environment (API keys, etc.)
    if not args.skip_validation:
        validation_result = validate_environment()
        if not validation_result.valid:
            logger.error("Environment validation failed:")
            for error in validation_result.errors:
                logger.error(f"  - {error}")
            print("\nEnvironment validation failed. Missing required configuration:")
            for error in validation_result.errors:
                print(f"  ✗ {error}")
            if validation_result.warnings:
                print("\nWarnings:")
                for warning in validation_result.warnings:
                    print(f"  ⚠ {warning}")
            print("\nRun with --skip-validation to bypass (not recommended)")
            sys.exit(1)

        if validation_result.warnings:
            for warning in validation_result.warnings:
                logger.warning(warning)

    # Load configuration
    config_path = Path(args.config) if args.config else Path("config/greenlight_config.json")
    try:
        config = load_config(config_path)
        logger.info(f"Loaded configuration from {config_path}")
    except Exception as e:
        logger.warning(f"Could not load config: {e}. Using defaults.")
        config = None

    if args.cli:
        # CLI mode
        logger.info("Running in headless mode")
        run_cli(args, config)
    else:
        # Web UI mode (default)
        logger.info("Running web UI mode")
        run_web(args, config)


def run_web(args, config):
    """Run the web UI (FastAPI backend + optional Next.js frontend)."""
    import subprocess
    import webbrowser
    import threading
    import time

    logger = get_logger("main")

    print("=" * 60)
    print("  Project Greenlight - Web UI")
    print("=" * 60)
    print()

    port = args.port

    # Start the FastAPI backend
    print(f"Starting API server on http://localhost:{port}")
    logger.info(f"Starting API server on port {port}")

    if not args.api_only:
        # Start Next.js frontend in background
        web_dir = Path(__file__).parent.parent / "web"
        if web_dir.exists():
            def start_frontend():
                time.sleep(2)  # Wait for API to start
                print("Starting Next.js frontend on http://localhost:3000")
                subprocess.run(
                    ["cmd", "/c", "npm", "run", "dev"],
                    cwd=str(web_dir),
                    shell=False
                )

            frontend_thread = threading.Thread(target=start_frontend, daemon=True)
            frontend_thread.start()

            # Open browser after a delay
            def open_browser():
                time.sleep(4)
                webbrowser.open("http://localhost:3000")

            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
        else:
            print(f"Warning: Web UI directory not found at {web_dir}")
            print("Run 'npm run dev' manually in the web/ directory")

    # Start FastAPI server (blocking)
    from greenlight.api import start_server
    start_server(host="0.0.0.0", port=port, reload=args.debug)


def run_cli(args, config):
    """Run in CLI mode."""
    import asyncio
    from greenlight.omni_mind import OmniMind
    
    logger = get_logger("main")
    
    async def cli_loop():
        omni_mind = OmniMind()
        
        print("\n" + "="*60)
        print("  Project Greenlight - CLI Mode")
        print("  Type 'help' for commands, 'exit' to quit")
        print("="*60 + "\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print("Goodbye!")
                    break
                
                if user_input.lower() == 'help':
                    print_help()
                    continue
                
                # Process with Omni Mind
                response = await omni_mind.process(user_input)
                print(f"\nOmni Mind: {response.message}\n")
                
                if response.suggestions:
                    print("Suggestions:")
                    for s in response.suggestions[:3]:
                        print(f"  - {s.title}")
                    print()
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"Error: {e}")
    
    asyncio.run(cli_loop())


def print_help():
    """Print CLI help."""
    print("""
Available Commands:
  help          - Show this help message
  exit          - Exit the application
  
You can also type natural language commands like:
  - "Create a new character named Marcus"
  - "Show me the story beats for episode 1"
  - "Generate storyboard prompts for scene 3"
  - "What characters appear in season 1?"
""")


if __name__ == "__main__":
    main()

