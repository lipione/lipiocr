import { apiJson } from "./api-client";
import type { AddressCandidate } from "../types/workspace";

export type AddressEvidenceRecord = {
  id: string;
  tenant_id?: string;
  visibility?: string;
  kind: string;
  province_name?: string;
  district_name?: string;
  local_level_name?: string;
  local_level_type?: string;
  ward?: string;
  name_en: string;
  name_np?: string;
  aliases_en?: string[];
  aliases_np?: string[];
  source?: string;
  confidence_weight?: number;
  disabled?: boolean;
};

export async function searchAddressEvidence(query: string) {
  return apiJson<{ query: string; results: AddressEvidenceRecord[] }>(
    `/api/reference/address-evidence?q=${encodeURIComponent(query)}`,
    { cache: "no-store" },
  );
}

export async function resolveAddressEvidence(text: string, targetField = "address") {
  return apiJson<{ candidates: AddressCandidate[] }>("/api/reference/address-evidence/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_field: targetField }),
  });
}

export async function createAddressEvidence(record: Partial<AddressEvidenceRecord>) {
  return apiJson<{ record: AddressEvidenceRecord }>("/api/reference/address-evidence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  });
}
