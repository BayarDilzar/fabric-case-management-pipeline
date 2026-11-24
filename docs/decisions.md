# Decisions log

Each entry records the decision, the alternatives considered and the reason.

## UK West region

- **Decision:** The Fabric capacity runs in UK West.
- **Alternatives:** UK South.
- **Reason:** UK South had no Fabric quota on a new subscription.

## F2 pay-as-you-go capacity

- **Decision:** One F2 capacity, billed pay as you go. It is resumed for work and paused afterwards.
- **Alternatives:** A Fabric trial on a Microsoft 365 trial tenant. A larger F SKU. A reserved capacity.
- **Reason:** F2 is the smallest F SKU, and pay as you go charges for compute only while the capacity runs. A trial-only tenant is limited to 30 days and its data is deleted when the trial ends. A reserved capacity is bought for a fixed term.

## One lakehouse per layer

- **Decision:** Each medallion layer has its own lakehouse: lh_bronze now, lh_silver and lh_gold later. The lh_ prefix matches the nb_ and pl_ prefixes of notebooks and pipelines.
- **Alternatives:** One lakehouse with a schema per layer.
- **Reason:** A Silver or Gold notebook writes to its own attached lakehouse, so a mistake there cannot change Bronze.
