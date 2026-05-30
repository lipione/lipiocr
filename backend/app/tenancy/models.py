from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TenantSettings(BaseModel):
    retention_days: int = 2555
    allowed_export_profiles: List[str] = Field(default_factory=lambda: ["cbs_standard", "los_loan", "aml_case"])
    default_branch_code: Optional[str] = None
    data_region: str = "Nepal"


class TenantUser(BaseModel):
    user_id: str
    role: str
    branch_code: Optional[str] = None
    status: str = "active"


class Tenant(BaseModel):
    tenant_id: str
    name: str
    status: str = "active"
    settings: TenantSettings = Field(default_factory=TenantSettings)
    users: List[TenantUser] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TenantLifecycleEvent(BaseModel):
    tenant_id: str
    action: str
    actor: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, object] = Field(default_factory=dict)
