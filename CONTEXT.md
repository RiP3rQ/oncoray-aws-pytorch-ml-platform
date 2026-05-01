# Pytorch Model

This context covers chest X-ray classification workflows from model selection through prediction result delivery.

## Language

**Prediction**:
A public classification result returned by the API for one uploaded chest X-ray, including per-model outcome and upload persistence status.
_Avoid_: inference response, model-service response

**Model Runtime**:
A deployed classifier that can score an uploaded chest X-ray for one model slug.
_Avoid_: model-service, backend model

**Model Runtime Prediction**:
The internal classification payload returned by one Model Runtime for one Chest X-ray Upload.
_Avoid_: prediction response, model-service response, inference response

**Model Artifact**:
The trained weights file loaded by one Model Runtime before it can score Chest X-ray Uploads.
_Avoid_: model blob, checkpoint file, Hugging Face model

**Model Runtime Definition**:
The deploy-time recipe that binds one Model Runtime to its Model Artifact source, class labels, architecture, and load policy.
_Avoid_: model-service config, runtime settings bundle

**Chest X-ray Upload**:
The uploaded PNG, JPG, or WEBP chest X-ray image submitted for a Prediction, before any Model Runtime scores it.
_Avoid_: image blob, uploaded image, file

**Prediction Orchestration**:
The API-owned workflow that turns one Chest X-ray Upload and one requested prediction mode into one public Prediction.
_Avoid_: model service, prediction service, inference flow

**Model Catalog**:
The API-owned read model describing available Model Runtimes and their display metadata.
_Avoid_: model service, prediction endpoint

**Prediction Workflow**:
The frontend-owned user flow for selecting a prediction mode, preparing one Chest X-ray Upload, running a Prediction request, and presenting the latest Prediction.
_Avoid_: prediction orchestration, inference flow

**Production Deployment Contract**:
The authoritative resolved production deployment facts for one environment, excluding operator-provided secret values.
_Avoid_: runtime contract, infra contract, deployment config

## Relationships

- A **Prediction** is produced from exactly one uploaded chest X-ray.
- A **Prediction** may contain results from one or more **Model Runtimes**.
- A **Prediction** can be partially successful: one **Model Runtime** may fail while another contributes a successful result.
- A **Model Runtime Prediction** belongs to exactly one **Model Runtime** and one **Chest X-ray Upload**.
- A **Model Runtime Definition** defines exactly one deployable **Model Runtime**.
- A **Model Runtime Definition** names exactly one **Model Artifact** source for its **Model Runtime**.
- A **Model Runtime** must load exactly one **Model Artifact** before it can produce a **Model Runtime Prediction**.
- **Prediction Orchestration** turns one or more **Model Runtime Predictions** into one public **Prediction**.
- A **Prediction** can succeed even when **Chest X-ray Upload** persistence fails; upload persistence is best-effort status.
- A **Chest X-ray Upload** is validated before any **Model Runtime** scores it.
- **Chest X-ray Upload** validation is owned by **Prediction Orchestration** intake, not by **Model Runtimes**.
- **Prediction Orchestration** selects one or more **Model Runtimes** for exactly one **Chest X-ray Upload**.
- The **Model Catalog** is read-only metadata; it does not produce a **Prediction**.
- A **Prediction Workflow** calls **Prediction Orchestration**; it does not score **Chest X-ray Uploads** itself.
- A **Production Deployment Contract** is produced for one environment and consumed by production deployment tooling.
- A **Production Deployment Contract** includes generated or derived deployment facts; it names expected secret locations but does not contain secret values.
- A **Production Deployment Contract** includes the resolved image repositories and image tags used for one release.
- A **Production Deployment Contract** identifies **Model Runtime** deployment facts by model slug, not by deployment tool resource name.
- A **Production Deployment Contract** may be retained as a release artifact for audit and deployment debugging.

## Example dialogue

> **Dev:** "Should the frontend type its **Prediction** from the internal runtime payload?"
> **Domain expert:** "No. The API owns the public **Prediction** contract; each **Model Runtime** only contributes one **Model Runtime Prediction**."
>
> **Dev:** "Should model catalog reads live inside **Prediction Orchestration**?"
> **Domain expert:** "No. **Prediction Orchestration** only coordinates scoring and upload persistence for a requested **Prediction**."

## Flagged ambiguities

- "prediction response" was used for both public API payloads and internal runtime payloads; resolved: **Prediction** means the API-owned public contract, while **Model Runtime Prediction** means the internal runtime payload.
- `/model/{model_id}/predict` mixed **Model Catalog** identity with **Prediction Orchestration**; resolved: public **Prediction** requests use prediction mode, not model metadata identity.
- "runtime contract" conflicts with **Model Runtime**; resolved: deployment facts shared across Terraform, Helm, and release scripts are the **Production Deployment Contract**.
