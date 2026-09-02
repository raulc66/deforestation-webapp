"""MongoDB persistence for organization Stripe customers."""
from __future__ import annotations

from app.models.billing import BillingCustomer
from app.repositories.base import BaseRepository


class BillingCustomerRepository(BaseRepository[BillingCustomer]):
    collection_name = "billing_customers"
    model = BillingCustomer

    async def find_by_organization(self, organization_id: str) -> BillingCustomer | None:
        return await self.find_one({"organization_id": organization_id})

    async def find_by_stripe_customer(
        self,
        stripe_customer_id: str,
    ) -> BillingCustomer | None:
        return await self.find_one({"stripe_customer_id": stripe_customer_id})
