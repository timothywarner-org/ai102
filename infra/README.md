# AI-103 infrastructure

Bicep templates for the course demo environments. Everything here is **idempotent**, so
re-running a deployment is a no-op rather than an error.

## Which template do I want?

| Template | Use it when |
| --- | --- |
| **`ai103-lesson-env.bicep`** | **Start here.** Stands up one lesson: Foundry account + project + chat model, and optionally App Insights plus the Lesson 12 image and video models. Parameterized, so any lesson can target it. |
| `ai103-l11-agents.bicep` | The L10 + L11 environment specifically. Kept because its deployment name (`l11-agents`) is quoted in both lesson runbooks. |
| `ai103-core.mvp.bicep` | The shared multi-project core (3 lesson projects, one model). Targets `rg-ai103-core`. |
| `ai103-core.bicep` | The full course build: 4 models, 18 projects. Waiting on quota. |
| `ai103-l3-observability.main.bicep` | The L3 add-on: Log Analytics + App Insights + Azure AI Search. |

## Rebuild a lesson environment from nothing

This is the path that matters when a resource group has been deleted and a recording is
scheduled. Takes about five minutes.

```powershell
az group create -n rg-ai103-mvp -l eastus2; az deployment group create -g rg-ai103-mvp -n lesson-11 -f infra/ai103-lesson-env.bicep -p userObjectId=$(az ad signed-in-user show --query id -o tsv) projectName=proj-agents baseName=ai103-l11
```

The outputs map 1:1 onto a lesson `.env` file. Read them back at any time:

```powershell
az deployment group show -g rg-ai103-mvp -n lesson-11 --query properties.outputs
```

For a lesson that needs no telemetry, add `deployObservability=false` and skip the Log
Analytics and Application Insights resources entirely.

## Share one account across lessons

Foundry **accounts** carry the model quota, and **projects** are the isolation boundary inside
them. Pass the same `accountName` on each deployment and vary only `projectName`, and every
lesson lives inside a single TPM grant:

```powershell
az deployment group create -g rg-ai103-mvp -n lesson-06 -f infra/ai103-lesson-env.bicep -p userObjectId=$(az ad signed-in-user show --query id -o tsv) accountName=YOUR-FOUNDRY-RESOURCE projectName=proj-lesson-06 baseName=ai103-l06 deployObservability=false
```

Adding a project to an existing account is non-destructive: projects already on the account keep
running throughout.

## Add the image and video models (Lesson 12)

Lesson 12 generates images and video, which means two more model deployments on the same account.
Both are **off by default**, so every other lesson deploys exactly what it always did.

```powershell
az deployment group create -g rg-ai103-mvp -n lesson-12 -f infra/ai103-lesson-env.bicep -p userObjectId=$(az ad signed-in-user show --query id -o tsv) accountName=YOUR-FOUNDRY-RESOURCE projectName=proj-lesson-12 baseName=ai103-l12 deployObservability=false deployImageModel=true deployVideoModel=true
```

| Parameter | Default | Notes |
| --- | --- | --- |
| `deployImageModel` | `false` | Set `true` to add the `gpt-image-2` deployment. |
| `imageModelName` | `gpt-image-2` | Doubles as the deployment name. |
| `imageModelVersion` | `2026-04-21` | Safe to pin. |
| `imageModelCapacity` | `2` | **Requests** per minute, not thousands of tokens. |
| `deployVideoModel` | `false` | Set `true` to add the `sora-2` deployment. Needs `eastus2` or `swedencentral`. |
| `videoModelName` | `sora-2` | Doubles as the deployment name. |
| `videoModelVersion` | `''` (empty) | **Leave it empty.** See the Sora gotcha below. |
| `videoModelCapacity` | `9` | **Requests** per minute, not thousands of tokens. |

Two more outputs come back, `foundryImageModel` and `foundryVideoModel`, and they map onto
`FOUNDRY_IMAGE_MODEL` and `FOUNDRY_VIDEO_MODEL` in the lesson `.env`. Each is an empty string when
its flag is false.

## Gotchas worth knowing before you deploy

- **Deleting an account does not free its quota.** A deleted Foundry account goes to a
  soft-deleted state where it still holds the name and can hold TPM. You have to purge it:
  ```powershell
  az cognitiveservices account list-deleted -o table; az cognitiveservices account purge --location eastus2 --resource-group <rg> --name <account>
  ```
- **The gpt-5 family requires an explicit model version.** Omit `modelVersion` and deployment
  validation fails. It is pinned with `NoAutoUpgrade` on purpose, because a model that upgrades
  itself between recording sessions changes on-screen behavior a deck already claims.
- **`sora-2` is the exact opposite: never pin its version.** `videoModelVersion` defaults to an
  empty string and has to stay that way. The Foundry model catalog **still advertises version
  `2025-10-06`, which is dead**, so a version copied out of the catalog fails the deployment with
  `ServiceModelDeprecated: The model 'Format:OpenAI,Name:sora-2,Version:2025-10-06' has been
  deprecated since 07/15/2026`. Leave the version out and the service selects its own current
  default, which resolved to `2025-12-08` on 2026-08-11. The template builds the model object two
  different ways so the `version` key is genuinely **absent** rather than sent as an empty string,
  and the video deployment rides `OnceNewDefaultVersionAvailable` rather than `NoAutoUpgrade` so
  the next deprecation cannot strand it either.
- **Model deployments on one account are created one at a time, deliberately.** Concurrent writes
  to the same Cognitive Services account conflict, so the template chains
  chat -> image -> video -> project with explicit `dependsOn`. Every link is spelled out instead
  of inherited, because ARM **drops** a `dependsOn` whose target resource has a false condition:
  with `deployImageModel=false`, a video deployment that only depended on the image deployment
  would lose its ordering and race the chat deployment. Add a fourth model on the end of the
  chain, never alongside.
- **Image and video capacity is requests per minute, not thousands of tokens.** `modelCapacity=50`
  means 50K TPM, while `imageModelCapacity=2` and `videoModelCapacity=9` mean 2 RPM and 9 RPM.
  Those are the granted quota on this subscription.
- **Region availability is narrower for these two.** `sora-2` deploys to **eastus2 and
  swedencentral only** here; `gpt-image-2` also allows westus3 and polandcentral. `location` is
  deliberately not narrowed with `@allowed`, because it governs the whole template and the other
  lessons must stay free to target any region, so a `deployVideoModel=true` run in the wrong
  region fails at the model deployment rather than at parameter validation.
- **Do not reference `gpt-image-1` or `dall-e-3`.** `gpt-image-1` retires 2026-10-23, and
  `dall-e-3` was retired 2026-03-04 with its existing deployments left non-functional.
- **`allowProjectManagement: true` is what makes it a Foundry account.** Without it there is no
  project endpoint, so `FoundryChatClient` has nothing to connect to.
- **Data-plane roles are Foundry User + Cognitive Services OpenAI User**, deliberately not Azure
  AI Developer. That role targets Azure ML / hub-based workspaces rather than hub-less Foundry
  projects, and it is the exam trap the L4 deck calls out.
- **The App Insights project connection uses `authType: 'ApiKey'`** even though every other hop
  in these lessons is keyless, because Foundry stores the connection string as the connection
  target.
- **Account names are globally unique** and double as the `*.services.ai.azure.com` subdomain.
  The default generates one from the resource group ID, so it changes on every rebuild into a
  fresh group. Copy the endpoint from the outputs rather than from an old `.env`.

## Cost posture

Model deployments are **GlobalStandard**, which is pay-per-token, and Log Analytics and
Application Insights bill on ingestion. An idle environment costs approximately nothing, so it
is reasonable to leave one provisioned between recording sessions. To tear it all down:

```powershell
az group delete -n rg-ai103-mvp --yes --no-wait
```

Then purge the soft-deleted account per the gotcha above, or the name and quota stay claimed.
