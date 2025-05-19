#!/usr/bin/env python
"""
Rock Band Name Checker v2.0

This enhanced application checks if user-provided rock band names are appropriate using Azure AI Content Safety.
It demonstrates comprehensive Azure AI service integration with advanced monitoring capabilities.

Features:
- Azure AI Content Safety integration for content moderation
- Azure Monitor integration with OpenTelemetry for metrics and tracing
- Azure Log Analytics integration for centralized logging
- Azure Key Vault integration for secure credential management
- Batch processing mode for checking multiple band names
- Command-line interface for automation
- CSV export of results

This application serves as an educational example for Azure AI-102 certification training.

Author: Tim Warner (TechTrainerTim.com)
Date: May 7, 2025
"""

import os
import sys
import json
import logging
import time
import platform
import subprocess
import requests
import hashlib
import hmac
import base64
import uuid
import argparse
import csv
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.monitor.opentelemetry import AzureMonitorTraceExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import get_tracer
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.azure_monitor import AzureMonitorMetricExporter
from azure.keyvault.secrets import SecretClient
from azure.identity import ClientSecretCredential, AzureCliCredential
from datetime import datetime, timedelta

# Constants
DEFAULT_SEVERITY_THRESHOLD = 0  # Block anything flagged at all
SERVICE_NAME = "RockBandNameChecker"
VERSION = "2.0.0"
WORKSPACE_ID = "7f28cf83-d621-4c01-8ab6-06f9cda63c83"
LOG_TYPE = "BandNameCheck_CL"
APP_INSIGHTS_CONNECTION_STRING = os.environ.get("APP_INSIGHTS_CONNECTION_STRING", "")
CONTENT_SAFETY_ENDPOINT = "https://twai102contentsafety1.cognitiveservices.azure.com/"

# Default categories to check
DEFAULT_CATEGORIES = ["Hate", "Violence", "SelfHarm", "Sexual"]

# Severity level descriptions
SEVERITY_DESCRIPTIONS = {
    0: "Safe - No issues detected",
    2: "Low - Minor concerns detected",
    4: "Medium - Moderate concerns detected",
    6: "High - Serious concerns detected"
}


def setup_logging() -> logging.Logger:
    """Set up logging with console output."""
    logger = logging.getLogger(SERVICE_NAME)
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    return logger


def setup_azure_monitor() -> tuple:
    """Set up Azure Monitor OpenTelemetry integration for metrics and tracing.
    
    Returns:
        tuple: (meter, tracer) for metrics and tracing
    """
    if not APP_INSIGHTS_CONNECTION_STRING:
        print("Warning: APP_INSIGHTS_CONNECTION_STRING not set. Azure Monitor integration disabled.")
        return None, None
    
    # Set up metrics
    exporter = AzureMonitorMetricExporter.from_connection_string(APP_INSIGHTS_CONNECTION_STRING)
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter(SERVICE_NAME, VERSION)
    
    # Set up tracing
    trace_exporter = AzureMonitorTraceExporter.from_connection_string(APP_INSIGHTS_CONNECTION_STRING)
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    tracer = get_tracer(SERVICE_NAME, VERSION)
    
    return meter, tracer


def get_secret_from_keyvault(secret_name: str) -> str:
    """Retrieve a secret from Azure Key Vault using managed identity or service principal.
    
    Args:
        secret_name: Name of the secret to retrieve
        
    Returns:
        The secret value as a string
    """
    key_vault_url = os.environ.get("KEY_VAULT_URL")
    if not key_vault_url:
        return None
        
    try:
        # Try using DefaultAzureCredential (works with managed identity)
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=key_vault_url, credential=credential)
        secret = client.get_secret(secret_name)
        return secret.value
    except Exception as e:
        print(f"Warning: Could not retrieve secret from Key Vault: {e}")
        return None


def create_content_safety_client() -> ContentSafetyClient:
    """Create and configure the Azure AI Content Safety client using API key authentication.
    
    Tries to get the API key from Key Vault first, then falls back to environment variables.
    """
    # Try to get API key from Key Vault
    api_key = get_secret_from_keyvault("ContentSafetyApiKey")
    
    # Fall back to environment variable
    if not api_key:
        api_key = os.environ.get("CONTENT_SAFETY_API_KEY")

    if not api_key:
        raise ValueError("Content Safety API key not found in Key Vault or environment variables")

    # Use AzureKeyCredential for authentication
    return ContentSafetyClient(CONTENT_SAFETY_ENDPOINT, AzureKeyCredential(api_key))


def analyze_band_name(client: ContentSafetyClient, band_name: str, logger: logging.Logger, 
                     categories: List[str] = None) -> list:
    """Analyze the band name using Azure AI Content Safety.
    
    Args:
        client: The Content Safety client
        band_name: The band name to analyze
        logger: Logger instance
        categories: List of categories to check (defaults to DEFAULT_CATEGORIES)
        
    Returns:
        List of category analysis results
    """
    if not categories:
        categories = DEFAULT_CATEGORIES
        
    logger.info(f"Analyzing band name: {band_name} for categories: {categories}")

    options = AnalyzeTextOptions(
        text=band_name,
        categories=categories,
        output_type="FourSeverityLevels"
    )

    try:
        response = client.analyze_text(options)
        return response.categories_analysis  # Correct property per SDK docs
    except HttpResponseError as e:
        logger.error(f"Content safety analysis failed: {e}")
        raise


def analyze_band_name_with_retries(client: ContentSafetyClient, band_name: str, logger: logging.Logger, 
                                max_retries: int = 3, categories: List[str] = None) -> list:
    """Analyze the band name with retry logic and exponential backoff.
    
    Args:
        client: The Content Safety client
        band_name: The band name to analyze
        logger: Logger instance
        max_retries: Maximum number of retry attempts
        categories: List of categories to check
        
    Returns:
        List of category analysis results
    """
    retry_delay = 1  # Initial delay in seconds

    for attempt in range(1, max_retries + 1):
        try:
            return analyze_band_name(client, band_name, logger, categories)
        except HttpResponseError as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                raise
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff


def clear_console():
    """Clear the console screen."""
    if platform.system() == "Windows":
        subprocess.call("cls", shell=True)
    else:
        subprocess.call("clear", shell=True)


def pretty_print_results(categories: list, metadata: Dict[str, Any]) -> str:
    """Pretty print the analysis results with severity levels and metadata."""
    output = []
    blocked = False

    output.append("\nAnalysis Results:")
    for category in categories:
        severity = category.severity
        severity_label = {
            0: "Safe",
            2: "Low", 
            4: "Medium", 
            6: "High"
        }.get(severity, f"Unknown({severity})")
        
        status = "❌ BLOCKED" if severity > DEFAULT_SEVERITY_THRESHOLD else "✅ ALLOWED"
        output.append(f"  • {category.category}: Severity {severity} ({severity_label}) - {status}")
        if severity > DEFAULT_SEVERITY_THRESHOLD:
            blocked = True

    verdict = "❌ BLOCKED" if blocked else "✅ ALLOWED"
    output.append(f"\nVerdict: {verdict}")
    output.append("\nMetadata:")
    for key, value in metadata.items():
        output.append(f"  {key}: {value}")

    return "\n".join(output)


def build_signature(workspace_id, shared_key, date, content_length, method, content_type, resource):
    x_headers = 'x-ms-date:' + date
    string_to_hash = f"{method}\n{str(content_length)}\n{content_type}\n{x_headers}\n{resource}"
    bytes_to_hash = bytes(string_to_hash, encoding="utf-8")
    decoded_key = base64.b64decode(shared_key)
    encoded_hash = base64.b64encode(
        hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()
    ).decode()
    return f"SharedKey {workspace_id}:{encoded_hash}"


def post_data_to_log_analytics(workspace_id, shared_key, log_type, body):
    uri = f"https://{workspace_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01"
    content_type = "application/json"
    rfc1123date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    body_json = json.dumps(body)
    content_length = len(body_json)
    signature = build_signature(
        workspace_id, shared_key, rfc1123date, content_length, "POST", content_type, "/api/logs"
    )
    headers = {
        "Content-Type": content_type,
        "Authorization": signature,
        "Log-Type": log_type,
        "x-ms-date": rfc1123date,
        "time-generated-field": "timestamp"
    }
    response = requests.post(uri, data=body_json, headers=headers)
    if 200 <= response.status_code <= 299:
        print("Log Analytics: Data posted successfully.")
    else:
        print(f"Log Analytics: Failed to post data. Status code: {response.status_code}, Response: {response.text}")


def generate_name_variants(band_name: str) -> List[str]:
    """Generate different variants of a band name for more comprehensive checking."""
    return [
        band_name,
        f"The {band_name}",
        f"{band_name} Band",
        f"{band_name} 123"
    ]


def record_metrics(meter, band_name: str, verdict: str, response_time: float, categories: list):
    """Record metrics to Azure Monitor using OpenTelemetry.
    
    Args:
        meter: The OpenTelemetry meter instance
        band_name: The band name being checked
        verdict: Whether the name was allowed or blocked
        response_time: Time taken for the API call in seconds
        categories: List of category analysis results
    """
    if not meter:
        return
        
    # Create counters and histograms
    request_counter = meter.create_counter(
        name="band_name_checks",
        description="Count of band name checks",
        unit="1"
    )
    
    response_time_histogram = meter.create_histogram(
        name="content_safety_response_time",
        description="Response time of Content Safety API",
        unit="s"
    )
    
    # Record metrics with attributes
    attributes = {
        "band_name": band_name,
        "verdict": verdict,
        "service.name": SERVICE_NAME,
        "service.version": VERSION
    }
    
    request_counter.add(1, attributes)
    response_time_histogram.record(response_time, attributes)
    
    # Record category-specific metrics
    for category in categories:
        category_counter = meter.create_counter(
            name=f"category_{category.category.lower()}_detections",
            description=f"Count of {category.category} detections",
            unit="1"
        )
        
        if category.severity > 0:
            category_counter.add(1, {
                "severity": str(category.severity),
                "band_name": band_name,
                "service.name": SERVICE_NAME
            })


def visualize_results(results: List[Dict[str, Any]], output_file: str = None) -> None:
    """Create visualizations of the analysis results.
    
    Args:
        results: List of result dictionaries
        output_file: Optional file path to save the visualization
    """
    if not results:
        print("No results to visualize.")
        return
        
    try:
        # Count verdicts
        verdicts = [r["verdict"] for r in results]
        verdict_counts = {"ALLOWED": verdicts.count("ALLOWED"), "BLOCKED": verdicts.count("BLOCKED")}
        
        # Extract categories and severities
        all_categories = {}
        for result in results:
            for cat in result["categories"]:
                category = cat["category"]
                severity = cat["severity"]
                if category not in all_categories:
                    all_categories[category] = []
                all_categories[category].append(severity)
        
        # Create a figure with subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Plot 1: Verdict pie chart
        ax1.pie(
            verdict_counts.values(), 
            labels=verdict_counts.keys(),
            autopct='%1.1f%%',
            colors=['green', 'red'],
            explode=(0, 0.1),
            shadow=True
        )
        ax1.set_title('Band Name Verdicts')
        
        # Plot 2: Category severity boxplot
        categories = []
        severity_data = []
        for category, severities in all_categories.items():
            if severities:  # Only include categories with data
                categories.append(category)
                severity_data.append(severities)
        
        if categories and severity_data:
            ax2.boxplot(severity_data)
            ax2.set_xticklabels(categories, rotation=45)
            ax2.set_title('Category Severity Distribution')
            ax2.set_ylabel('Severity Level')
            ax2.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        # Save or show
        if output_file:
            plt.savefig(output_file)
            print(f"Visualization saved to {output_file}")
        else:
            plt.show()
            
    except Exception as e:
        print(f"Error creating visualization: {e}")


def process_batch_file(file_path: str, client: ContentSafetyClient, logger: logging.Logger, meter, 
                       categories: List[str] = None, visualize: bool = True) -> None:
    """Process a batch file of band names.
    
    Args:
        file_path: Path to CSV or text file with band names
        client: Content Safety client
        logger: Logger instance
        meter: OpenTelemetry meter for metrics
    """
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return
        
    band_names = []
    
    # Determine file type and read accordingly
    if file_path.lower().endswith('.csv'):
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():  # Check if row has content
                    band_names.append(row[0].strip())
    else:  # Assume text file with one name per line
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():  # Check if line has content
                    band_names.append(line.strip())
    
    if not band_names:
        print("No band names found in the file.")
        return
        
    print(f"Processing {len(band_names)} band names from {file_path}...")
    
    # Process each band name
    results = []
    for band_name in band_names:
        try:
            start_time = time.time()
            category_results = analyze_band_name_with_retries(client, band_name, logger, categories=categories)
            response_time = time.time() - start_time
            
            blocked = any(cat.severity > DEFAULT_SEVERITY_THRESHOLD for cat in category_results)
            verdict = "BLOCKED" if blocked else "ALLOWED"
            
            # Record metrics
            record_metrics(meter, band_name, verdict, response_time, category_results)
            
            # For Log Analytics
            results.append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "band_name": band_name,
                "verdict": verdict,
                "response_time_ms": int(response_time * 1000),
                "categories": [
                    {"category": cat.category, "severity": cat.severity} for cat in category_results
                ]
            })
            
            # Print progress
            print(f"Processed: {band_name} - {verdict}")
            
        except Exception as e:
            print(f"Error processing '{band_name}': {e}")
    
    # Save results to CSV
    output_file = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Band Name', 'Verdict', 'Response Time (ms)', 'Categories'])
        for result in results:
            categories_str = '; '.join([f"{c['category']}: {c['severity']}" for c in result['categories']])
            writer.writerow([result['band_name'], result['verdict'], result['response_time_ms'], categories_str])
    
    print(f"\nResults saved to {output_file}")
    
    # Send batch to Log Analytics
    shared_key = os.environ.get("LOG_ANALYTICS_SHARED_KEY") or get_secret_from_keyvault("LogAnalyticsSharedKey")
    if shared_key:
        post_data_to_log_analytics(WORKSPACE_ID, shared_key, LOG_TYPE, results)
        print("Results sent to Azure Log Analytics.")
    
    # Print summary
    allowed_count = sum(1 for result in results if result["verdict"] == "ALLOWED")
    blocked_count = sum(1 for result in results if result["verdict"] == "BLOCKED")
    avg_response_time = sum(result["response_time_ms"] for result in results) / len(results) if results else 0
    
    print(f"\n📊 Summary Statistics:")
    print(f"  • Total band names processed: {len(results)}")
    print(f"  • Allowed names: {allowed_count}")
    print(f"  • Blocked names: {blocked_count}")
    print(f"  • Average response time: {avg_response_time/1000:.2f}s")
    
    # Create visualization if requested
    if visualize and results:
        viz_file = f"visualization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        visualize_results(results, viz_file)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Rock Band Name Checker using Azure AI Content Safety')
    parser.add_argument('--batch', '-b', type=str, help='Path to a CSV or text file with band names to check in batch mode')
    parser.add_argument('--name', '-n', type=str, help='A single band name to check')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--categories', '-c', type=str, nargs='+', choices=['Hate', 'Violence', 'SelfHarm', 'Sexual'], 
                        help='Categories to check (default: all)')
    parser.add_argument('--threshold', '-t', type=int, choices=[0, 2, 4, 6], default=DEFAULT_SEVERITY_THRESHOLD,
                        help='Severity threshold for blocking (0=any, 2=low, 4=medium, 6=high)')
    parser.add_argument('--no-viz', action='store_true', help='Disable visualization in batch mode')
    parser.add_argument('--key-vault', '-k', type=str, help='Azure Key Vault URL for retrieving secrets')
    return parser.parse_args()


def main():
    """Main application entry point."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set Key Vault URL if provided
    if args.key_vault:
        os.environ["KEY_VAULT_URL"] = args.key_vault
    
    # Setup logging and monitoring
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    # Override threshold if specified
    global DEFAULT_SEVERITY_THRESHOLD
    if args.threshold is not None:
        DEFAULT_SEVERITY_THRESHOLD = args.threshold
        logger.info(f"Using custom severity threshold: {DEFAULT_SEVERITY_THRESHOLD}")
    
    meter, tracer = setup_azure_monitor()
    logger.info(f"Starting {SERVICE_NAME} v{VERSION}")

    try:
        client = create_content_safety_client()
        
        # Batch mode
        if args.batch:
            process_batch_file(
                args.batch, 
                client, 
                logger, 
                meter, 
                categories=args.categories,
                visualize=not args.no_viz
            )
            return
            
        # Single name from command line
        if args.name:
            band_name = args.name
        else:
            # Interactive mode
            clear_console()
            print("\nWelcome to the Rock Band Name Checker! 🤘")
            band_name = input("Enter a potential rock band name: ").strip()
            
        if not band_name:
            print("No band name entered. Exiting.")
            return

        # Generate variants
        variants = generate_name_variants(band_name)
        batch_results = []
        for name in variants:
            try:
                start_time = time.time()
                categories = analyze_band_name_with_retries(client, name, logger, categories=args.categories)
                response_time = time.time() - start_time
                
                blocked = any(cat.severity > DEFAULT_SEVERITY_THRESHOLD for cat in categories)
                verdict = "BLOCKED" if blocked else "ALLOWED"
                if "hate" in name.lower():
                    verdict = "BLOCKED"
                    
                # Record metrics
                record_metrics(meter, name, verdict, response_time, categories)
                
                # For pretty print
                metadata = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), 
                    "band_name": name,
                    "response_time": f"{response_time:.2f}s"
                }
                print(pretty_print_results(categories, metadata))
                
                # For Log Analytics
                batch_results.append({
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "band_name": name,
                    "verdict": verdict,
                    "response_time_ms": int(response_time * 1000),
                    "categories": [
                        {"category": cat.category, "severity": cat.severity} for cat in categories
                    ]
                })
            except Exception as e:
                print(f"\n❌ ERROR: {e}")

        # Send batch to Log Analytics
        shared_key = os.environ.get("LOG_ANALYTICS_SHARED_KEY") or get_secret_from_keyvault("LogAnalyticsSharedKey")
        if shared_key:
            post_data_to_log_analytics(WORKSPACE_ID, shared_key, LOG_TYPE, batch_results)
        else:
            print("LOG_ANALYTICS_SHARED_KEY not set. Skipping Log Analytics upload.")
            
        # Print summary metrics
        allowed_count = sum(1 for result in batch_results if result["verdict"] == "ALLOWED")
        blocked_count = sum(1 for result in batch_results if result["verdict"] == "BLOCKED")
        avg_response_time = sum(result["response_time_ms"] for result in batch_results) / len(batch_results) if batch_results else 0
        
        print(f"\n📊 Summary Statistics:")
        print(f"  • Total variants checked: {len(batch_results)}")
        print(f"  • Allowed names: {allowed_count}")
        print(f"  • Blocked names: {blocked_count}")
        print(f"  • Average response time: {avg_response_time/1000:.2f}s")
        print(f"  • Azure Monitor integration: {'Enabled' if meter else 'Disabled'}")
        print(f"  • Log Analytics integration: {'Enabled' if shared_key else 'Disabled'}")

        print("\nExiting the Rock Band Name Checker. Goodbye! 🤘")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

    except Exception as e:
        logger.exception("Unhandled exception in main")
        print(f"\n❌ CRITICAL ERROR: {e}")
        sys.exit(1)


def print_help():
    """Print help information about the application."""
    print("\nRock Band Name Checker v2.0 - Azure AI Content Safety Integration\n")
    print("This application demonstrates:")
    print("  1. Azure AI Content Safety for content moderation")
    print("  2. Azure Monitor integration with OpenTelemetry")
    print("  3. Azure Log Analytics for centralized logging")
    print("  4. Azure Key Vault for secure credential management")
    print("\nEnvironment Variables:")
    print("  CONTENT_SAFETY_API_KEY - API key for Azure AI Content Safety")
    print("  LOG_ANALYTICS_SHARED_KEY - Shared key for Azure Log Analytics")
    print("  APP_INSIGHTS_CONNECTION_STRING - Connection string for Azure Application Insights")
    print("  KEY_VAULT_URL - URL for Azure Key Vault (alternative to environment variables)")
    print("\nUsage Examples:")
    print("  # Interactive mode")
    print("  python rock_band_name_checker.py")
    print("\n  # Check a single name")
    print("  python rock_band_name_checker.py --name 'Death Metal Kittens'")
    print("\n  # Batch processing")
    print("  python rock_band_name_checker.py --batch band_names.csv")
    print("\n  # Custom categories and threshold")
    print("  python rock_band_name_checker.py --name 'Angry Puppies' --categories Hate Violence --threshold 4")
    print("\n  # Using Key Vault for secrets")
    print("  python rock_band_name_checker.py --key-vault https://mykeyvault.vault.azure.net/")


if __name__ == "__main__":
    # Check if help is requested
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        print_help()
    else:
        main()
