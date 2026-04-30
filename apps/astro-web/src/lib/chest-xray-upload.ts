export const CHEST_XRAY_UPLOAD_MAX_BYTES = 2 * 1024 * 1024;
export const CHEST_XRAY_UPLOAD_ACCEPTED_IMAGE_TYPES = [
  "image/png",
  "image/jpeg",
  "image/webp",
] as const;
export const CHEST_XRAY_UPLOAD_ACCEPT_ATTRIBUTE =
  ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp";

export type ChestXrayUploadDraftValidation =
  | { ok: true }
  | { ok: false; message: string };

export function validateChestXrayUploadDraft(
  file: File,
): ChestXrayUploadDraftValidation {
  if (
    !CHEST_XRAY_UPLOAD_ACCEPTED_IMAGE_TYPES.some((type) => type === file.type)
  ) {
    return { ok: false, message: "Use a PNG, JPG, or WEBP image." };
  }

  if (file.size > CHEST_XRAY_UPLOAD_MAX_BYTES) {
    return { ok: false, message: "Image exceeds 2 MB limit." };
  }

  return { ok: true };
}
