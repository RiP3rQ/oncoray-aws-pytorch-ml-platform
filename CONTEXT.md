# Pytorch Model

This context covers chest X-ray classification workflows from model selection through prediction result delivery.

## Language

**Prediction**:
A public classification result returned by the API for one uploaded chest X-ray, including per-model outcome and upload persistence status.
_Avoid_: inference response, model-service response

**Model Runtime**:
A deployed classifier that can score an uploaded chest X-ray for one model slug.
_Avoid_: model-service, backend model

**Chest X-ray Upload**:
The uploaded PNG, JPG, or WEBP chest X-ray image submitted for a Prediction, before any Model Runtime scores it.
_Avoid_: image blob, uploaded image, file

**Prediction Orchestration**:
The API-owned workflow that turns one Chest X-ray Upload and one requested prediction mode into one public Prediction.
_Avoid_: model service, prediction service, inference flow

**Model Catalog**:
The API-owned read model describing available Model Runtimes and their display metadata.
_Avoid_: model service, prediction endpoint

## Relationships

- A **Prediction** is produced from exactly one uploaded chest X-ray.
- A **Prediction** may contain results from one or more **Model Runtimes**.
- A **Chest X-ray Upload** is validated before any **Model Runtime** scores it.
- **Chest X-ray Upload** validation is owned by **Prediction Orchestration** intake, not by **Model Runtimes**.
- **Prediction Orchestration** selects one or more **Model Runtimes** for exactly one **Chest X-ray Upload**.
- The **Model Catalog** is read-only metadata; it does not produce a **Prediction**.

## Example dialogue

> **Dev:** "Should the frontend type its **Prediction** from the internal runtime payload?"
> **Domain expert:** "No. The API owns the public **Prediction** contract; each **Model Runtime** only contributes one internal result."
>
> **Dev:** "Should model catalog reads live inside **Prediction Orchestration**?"
> **Domain expert:** "No. **Prediction Orchestration** only coordinates scoring and upload persistence for a requested **Prediction**."

## Flagged ambiguities

- "prediction response" was used for both public API payloads and internal runtime payloads; resolved: **Prediction** means the API-owned public contract.
- `/model/{model_id}/predict` mixed **Model Catalog** identity with **Prediction Orchestration**; resolved: public **Prediction** requests use prediction mode, not model metadata identity.
