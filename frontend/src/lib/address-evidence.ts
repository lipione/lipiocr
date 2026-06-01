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
  legacy_aliases?: string[];
  source?: string;
  confidence_weight?: number;
  disabled?: boolean;
};

export type AddressEvidenceSearchFilters = {
  district?: string;
  localLevel?: string;
  ward?: string;
  limit?: number;
};

export async function searchAddressEvidence(query: string, filters: AddressEvidenceSearchFilters = {}) {
  const params = new URLSearchParams();
  params.set("q", query);
  if (filters.district) params.set("district", filters.district);
  if (filters.localLevel) params.set("local_level", filters.localLevel);
  if (filters.ward) params.set("ward", filters.ward);
  if (filters.limit) params.set("limit", String(filters.limit));
  return apiJson<{ query: string; results: AddressEvidenceRecord[] }>(
    `/api/reference/address-evidence?${params.toString()}`,
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

export async function importAddressEvidence(records: Partial<AddressEvidenceRecord>[]) {
  return apiJson<{ records: AddressEvidenceRecord[]; count: number }>("/api/reference/address-evidence/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ records }),
  });
}

export async function updateAddressEvidence(id: string, record: Partial<AddressEvidenceRecord>) {
  return apiJson<{ record: AddressEvidenceRecord }>(`/api/reference/address-evidence/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  });
}

export async function deleteAddressEvidence(id: string) {
  return apiJson<{ id: string; status: string; deleted: boolean }>(
    `/api/reference/address-evidence/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
}
