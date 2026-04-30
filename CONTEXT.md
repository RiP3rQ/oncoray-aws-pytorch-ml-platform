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
The uploaded chest X-ray image submitted for a Prediction, before any Model Runtime scores it.
_Avoid_: image blob, uploaded image, file

## Relationships

- A **Prediction** is produced from exactly one uploaded chest X-ray.
- A **Prediction** may contain results from one or more **Model Runtimes**.
- A **Chest X-ray Upload** is validated before any **Model Runtime** scores it.

## Example dialogue

> **Dev:** "Should the frontend type its **Prediction** from the internal runtime payload?"
> **Domain expert:** "No. The API owns the public **Prediction** contract; each **Model Runtime** only contributes one internal result."

## Flagged ambiguities

- "prediction response" was used for both public API payloads and internal runtime payloads; resolved: **Prediction** means the API-owned public contract.
