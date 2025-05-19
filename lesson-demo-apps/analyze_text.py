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


def clear_terminal() -> None:
    """Clear the terminal screen."""
    command = "cls" if os.name == "nt" else "clear"
    os.system(command)


def get_content_safety_client() -> ContentSafetyClient:
    """Initialize and return the Azure Content Safety client."""
    endpoint = "https://twai102contentsafety1.cognitiveservices.azure.com/"
    api_key = os.getenv("CONTENT_SAFETY_API_KEY")

    if not api_key:
        raise EnvironmentError("Missing CONTENT_SAFETY_API_KEY environment variable.")

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
