import os
import subprocess
import sys

try:
    from azure.ai.contentsafety import ContentSafetyClient
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.contentsafety.models import AnalyzeTextOptions
except ImportError:
    print("Required package not found. Installing azure-ai-contentsafety...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "azure-ai-contentsafety"])
    from azure.ai.contentsafety import ContentSafetyClient
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.contentsafety.models import AnalyzeTextOptions

try:
    from dotenv import load_dotenv
except ImportError:
    print("Required package not found. Installing python-dotenv...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv

# Read CONTENT_SAFETY_ENDPOINT and CONTENT_SAFETY_API_KEY from the .env file next to this script.
# Copy .env.example to .env and fill in your values; never hardcode keys in code.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def clear_terminal() -> None:
    """Clear the terminal screen."""
    command = "cls" if os.name == "nt" else "clear"
    os.system(command)


def get_content_safety_client() -> ContentSafetyClient:
    """Initialize and return the Azure Content Safety client."""
    endpoint = os.getenv("CONTENT_SAFETY_ENDPOINT", "")
    api_key = os.getenv("CONTENT_SAFETY_API_KEY")

    if not api_key or not endpoint:
        raise EnvironmentError(
            "Set CONTENT_SAFETY_ENDPOINT and CONTENT_SAFETY_API_KEY environment variables."
        )

    return ContentSafetyClient(endpoint, AzureKeyCredential(api_key))


def display_severity_legend() -> None:
    """Display a legend explaining severity score meanings."""
    print("\nSeverity Legend:")
    print("  0 = Safe")
    print("  2 = Low (mild concern)")
    print("  4 = Medium (moderate concern)")
    print("  6 = High (severe concern)")


def analyze_text(input_text: str) -> None:
    """Analyze the given text for content safety issues and print results."""
    client = get_content_safety_client()
    options = AnalyzeTextOptions(text=input_text)
    response = client.analyze_text(options)

    clear_terminal()

    print("\nInput Text:")
    print(f"\"{input_text}\"\n")

    print("Analysis Results:")
    for result in response.categories_analysis:
        print(f"- {result.category}: Severity {result.severity}")

    display_severity_legend()


def main() -> None:
    """Entry point for the script."""
    sample_text = "I hate you. I want to hurt someone."
    analyze_text(sample_text)


if __name__ == "__main__":
    main()
