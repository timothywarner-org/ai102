#!/usr/bin/env python
"""
M02 demo -- one real Foundry model deployment that makes ALL FOUR Lesson 2 decisions.

AI-103 Lesson 2 ("Set up AI solutions in Foundry") is four choices about *setting up*
infrastructure and deployments. Rather than four disconnected snippets, this builds the
ONE artifact those choices produce -- a real, running model deployment -- then tears it
back down. Everything is keyless (Microsoft Entra ID via AzureCliCredential): no API
keys anywhere, exactly the way AI-103 wants you deploying in production and in CI/CD.

We authenticate with AzureCliCredential (your `az login` identity) rather than the broader
DefaultAzureCredential on purpose: DefaultAzureCredential checks EnvironmentCredential FIRST,
so a stray AZURE_CLIENT_ID/AZURE_CLIENT_SECRET in your shell would silently sign you in as a
service principal instead of you. Pinning to the CLI identity makes the demo deterministic on
any machine. In CI/CD you swap this one line for DefaultAzureCredential and let the pipeline's
federated (OIDC) identity resolve -- still secretless (see LO4).

Each decision maps onto the lesson's own slides (and onto an exam "tell"):

  LO1  DESIGN INFRASTRUCTURE ...... connect keyless to a *hub-less Foundry project* plus
                                    its parent Foundry (Cognitive Services) account -- the
                                    default Foundry model, no AI Hub required.
  LO2  CHOOSE A DEPLOYMENT OPTION .. create the deployment with a chosen SKU (sku.name).
                                    GlobalStandard = pay-per-token shared capacity, the
                                    recommended starting point; swap to ProvisionedManaged
                                    for PTU, or GlobalBatch for async 50%-off jobs.
  LO3  CONFIGURE THE DEPLOYMENT .... pin the model version (versionUpgradeOption =
                                    NoAutoUpgrade) and attach a content-filter policy
                                    (raiPolicyName), then read both back and prove the
                                    deployment is live by calling it.
  LO4  INTEGRATE WITH CI/CD ........ the create call is an *idempotent upsert* -- re-running
                                    converges to the same desired state, just like the
                                    Bicep in ../../infra/ai103-core.bicep. DefaultAzureCredential
                                    resolves to OIDC federated identity in GitHub Actions,
                                    so the pipeline ships with zero stored secrets.

Two Azure planes are in play, and telling them apart is itself an exam skill:
  * CONTROL plane (azure-mgmt-cognitiveservices) CREATES/CONFIGURES the deployment. Needs a
    management role -- Cognitive Services Contributor (or Contributor) on the account.
  * DATA plane (azure-ai-projects) READS and CALLS it. Needs a Foundry data role -- Foundry
    User is enough. (Plain Owner/Contributor grant no data actions; that's a classic trap.)

Setup:  uv sync   (or: pip install -e .)   ;   az login   ;   copy .env.example to .env
Run:    uv run python m02_setup_demo.py            # create -> configure -> verify -> delete
        uv run python m02_setup_demo.py --dry-run  # print the exact spec, call nothing
        uv run python m02_setup_demo.py --keep      # leave the deployment standing

This file is also a VS Code notebook: the `# %%` markers open it in the Interactive Window
("Run Cell"), so it works with or without Jupyter -- no separate .ipynb to keep in sync.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

# %%
# ---- imports -------------------------------------------------------------------------
import argparse
import os
import sys

from azure.identity import AzureCliCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient  # CONTROL plane
from azure.ai.projects import AIProjectClient                              # DATA plane

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env is a convenience; real env vars work too.


# %%
# ---- small helpers -------------------------------------------------------------------
def required_env(name: str, hint: str) -> str:
    """Return env var ``name`` or exit with a friendly, copy-pasteable hint. See .env.example."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: environment variable {name} is not set.\n  -> {hint}\n  See .env.example.")
    return value


def banner(text: str) -> None:
    """Print a labeled section header so each LO is obvious on screen while recording."""
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


# %%
# ---- configuration (all keyless; nothing secret lives here) --------------------------
# Deployment shape. The DEFAULTS are deliberately the cheapest, safest teaching choice:
# GlobalStandard (pay-per-token, no reserved spend) with the smallest capacity unit.
DEPLOYMENT_NAME = os.environ.get("DEPLOY_NAME", "ai103-l2-demo")
SKU_NAME = os.environ.get("DEPLOY_SKU", "GlobalStandard")   # LO2: the deployment "shape"
SKU_CAPACITY = int(os.environ.get("DEPLOY_CAPACITY", "1"))  # tiny on purpose
# LO3 knobs -- the two settings AI-103 loves to test by name:
VERSION_UPGRADE_OPTION = os.environ.get("DEPLOY_UPGRADE_OPTION", "NoAutoUpgrade")  # = pin
CONTENT_FILTER_POLICY = os.environ.get("DEPLOY_RAI_POLICY", "Microsoft.DefaultV2")  # = filter


def parse_args() -> argparse.Namespace:
    """CLI flags that keep this safe to run live and safe to record."""
    parser = argparse.ArgumentParser(description="AI-103 L2: one Foundry deployment, four setup decisions.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the exact deployment spec and exit; make no Azure calls.")
    parser.add_argument("--keep", action="store_true",
                        help="Leave the deployment in place instead of deleting it at the end.")
    return parser.parse_args()


# %%
def build_deployment_spec() -> dict:
    """Assemble the control-plane deployment payload -- LO2 (SKU) + LO3 (pin + filter).

    We build a plain dict (not typed model classes) on purpose: it mirrors the shape you'd
    write in a Bicep/ARM template one-for-one, which is the LO4 bridge to infrastructure as
    code. Every key below has a direct Bicep equivalent in ../../infra/ai103-core.bicep.
    """
    model_name = required_env("DEPLOY_MODEL_NAME", "the base model to deploy, e.g. gpt-5-nano")
    model_format = os.environ.get("DEPLOY_MODEL_FORMAT", "OpenAI")
    # Empty lets older models pick their default version, but some families (e.g. gpt-5)
    # REQUIRE an explicit version -- which is itself the LO3 version-pinning lesson.
    model_version = os.environ.get("DEPLOY_MODEL_VERSION", "")

    model_block = {"format": model_format, "name": model_name}
    if model_version:  # pin an explicit version only if you gave one
        model_block["version"] = model_version

    return {
        # LO2 -- the deployment OPTION. sku.name is the whole "elastic vs reserved vs batch"
        # decision compressed into one string: GlobalStandard | ProvisionedManaged | GlobalBatch ...
        "sku": {"name": SKU_NAME, "capacity": SKU_CAPACITY},
        "properties": {
            "model": model_block,
            # LO3 -- CONFIGURE. NoAutoUpgrade freezes the version so a vendor update can't
            # silently change your app's behavior. This is "version pinning" on the exam.
            "versionUpgradeOption": VERSION_UPGRADE_OPTION,
            # LO3 -- CONFIGURE. The content-filter (responsible-AI) policy is attached at the
            # deployment, not the model. Microsoft.DefaultV2 is the built-in default tier.
            "raiPolicyName": CONTENT_FILTER_POLICY,
        },
    }


# %%
def main() -> None:
    """Create -> configure -> verify -> (optionally) delete one real Foundry deployment."""
    args = parse_args()

    # ---- LO1: DESIGN THE INFRASTRUCTURE (keyless, hub-less Foundry project) ----
    banner("LO1  Design infrastructure  |  keyless Entra auth, hub-less Foundry project")
    project_endpoint = required_env(
        "FOUNDRY_PROJECT_ENDPOINT",
        "https://<resource>.services.ai.azure.com/api/projects/<project>",
    )
    subscription_id = required_env("AZURE_SUBSCRIPTION_ID", "your Azure subscription GUID")
    resource_group = required_env("AZURE_RESOURCE_GROUP", "the resource group holding the Foundry account")
    account_name = required_env("FOUNDRY_ACCOUNT_NAME", "the Foundry (Cognitive Services) account name")

    # One credential, two planes. AzureCliCredential binds to your `az login` identity, so the
    # demo is deterministic even when AZURE_CLIENT_ID/SECRET env vars are set for other tools.
    # In CI/CD, swap this single line for DefaultAzureCredential() to pick up the pipeline's
    # federated (OIDC) identity -- still no secrets either way (LO4).
    credential = AzureCliCredential()
    arm = CognitiveServicesManagementClient(credential, subscription_id)  # CONTROL plane (create/config)
    project = AIProjectClient(endpoint=project_endpoint, credential=credential)  # DATA plane (read/call)
    print(f"  Foundry account (control plane) : {account_name}  (rg: {resource_group})")
    print(f"  Foundry project (data plane)    : {project_endpoint}")
    print("  Auth                            : AzureCliCredential (az login) -- no API keys")
    print("  EXAM TELL: control-plane create needs Cognitive Services Contributor; data-plane")
    print("            read/call needs Foundry User. Owner/Contributor alone grant no data actions.")

    # ---- LO2 + LO3: assemble the spec (SKU + version pin + content filter) ----
    spec = build_deployment_spec()
    banner("LO2  Choose a deployment option  +  LO3  Configure it")
    print(f"  LO2 sku.name            : {spec['sku']['name']}  (GlobalStandard = pay-per-token shared)")
    print(f"      sku.capacity        : {spec['sku']['capacity']}")
    print(f"  LO3 versionUpgradeOption: {spec['properties']['versionUpgradeOption']}  (NoAutoUpgrade = pinned)")
    print(f"      raiPolicyName       : {spec['properties']['raiPolicyName']}  (content filter policy)")
    print(f"      model               : {spec['properties']['model']}")

    if args.dry_run:
        print("\n  --dry-run: spec above is what WOULD be deployed. No Azure calls made. Done.")
        return

    # ---- LO2/LO3 executed: idempotent create-or-update (this is also the LO4 seed) ----
    print(f"\n  Deploying '{DEPLOYMENT_NAME}' ... (create-or-update; safe to re-run)")
    result = arm.deployments.begin_create_or_update(
        resource_group_name=resource_group,
        account_name=account_name,
        deployment_name=DEPLOYMENT_NAME,
        deployment=spec,
    ).result()  # blocks until the deployment reaches a terminal state
    print(f"  provisioningState       : {result.properties.provisioning_state}")

    # ---- LO3 proof: read the config BACK from the control plane ----
    banner("LO3  Verify the configuration actually stuck")
    live = arm.deployments.get(resource_group, account_name, DEPLOYMENT_NAME)
    print(f"  sku.name (read back)    : {live.sku.name}")
    print(f"  model.version (read back): {getattr(live.properties.model, 'version', '(service default)')}")
    print(f"  versionUpgradeOption    : {live.properties.version_upgrade_option}")
    print(f"  raiPolicyName           : {live.properties.rai_policy_name}")

    # ---- LO3 proof: the DATA plane can now see and CALL the same deployment ----
    try:
        seen = next((d for d in project.deployments.list() if d.name == DEPLOYMENT_NAME), None)
        if seen is not None:
            print(f"  data-plane sees it      : {seen.name}  model={seen.model_name}  "
                  f"v={seen.model_version}  type={seen.type}")
    except Exception as exc:  # data-plane listing is a nice-to-have, never fatal
        print(f"  (data-plane list skipped: {type(exc).__name__})")

    try:
        with project.get_openai_client() as openai_client:
            ping = openai_client.responses.create(
                model=DEPLOYMENT_NAME,
                input="Reply with the single word: ready.",
            )
            print(f"  live inference          : '{ping.output_text.strip()}'  (deployment is callable)")
    except Exception as exc:
        # Non-OpenAI models may not speak the Responses API; provisioningState already proved it.
        print(f"  live inference          : skipped ({type(exc).__name__}); provisioningState confirms it")

    # ---- LO4: INTEGRATE WITH CI/CD ----
    banner("LO4  Integrate with CI/CD  |  idempotent + secretless")
    print("  Re-run this script: begin_create_or_update converges to the same state -- that")
    print("  idempotency is exactly what lets it run in a pipeline. The spec dict maps 1:1 to")
    print("  the Bicep resource in ../../infra/ai103-core.bicep (sku.name, model, versionUpgradeOption,")
    print("  raiPolicyName), so 'treat AI infra as code' is literal here.")
    print("  In GitHub Actions, swap AzureCliCredential for DefaultAzureCredential: it picks up a")
    print("  federated (OIDC) identity via azure/login with id-token: write -- NO stored secret to leak.")

    # ---- teardown (default) so the demo costs nothing to leave behind ----
    if args.keep:
        print(f"\n  --keep: leaving '{DEPLOYMENT_NAME}' deployed. Delete it later to stop billing.")
    else:
        print(f"\n  Cleaning up: deleting '{DEPLOYMENT_NAME}' ...")
        arm.deployments.begin_delete(resource_group, account_name, DEPLOYMENT_NAME).result()
        print("  deleted. Nothing left running.")

    banner("One deployment, four setup decisions: infrastructure (LO1), option (LO2), "
           "configuration (LO3), CI/CD (LO4).")


# %%
if __name__ == "__main__":
    main()
