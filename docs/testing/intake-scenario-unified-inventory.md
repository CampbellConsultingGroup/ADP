# Unified Real-Time Inventory for Ship-from-Store and BOPIS

## Background

We operate 220 stores and 3 distribution centers. Store and DC stock positions are held in the Legacy Inventory Mainframe and synced to the e-commerce channel by an overnight batch. Online orders are managed in Manhattan Active OMS, and stores sell through Oracle Retail Xstore POS.

## Business problem

Online customers see stock that is no longer on the shelf. About 4% of online orders are cancelled because of phantom stock, and 9% of BOPIS orders are cancelled after the customer has already been told the order is ready. Stock positions are up to 18 hours stale. We estimate $14M a year in lost sales and a further $3M in avoidable markdowns because store stock cannot be offered online before it ages.

## Desired outcome

Reduce the online order cancellation rate from 4% to under 1% within two quarters of go-live. Make every store and DC stock change visible to the online channel within 60 seconds. Launch ship-from-store in 40 pilot stores within two quarters, then roll out to all stores.

## Functional requirements

1. The system must show real-time available-to-sell quantity per SKU for every store and DC.
2. The system must reserve stock for an order at checkout so the same unit cannot be sold twice.
3. Order Orchestration must route each online order to the nearest store or DC that can fulfil it complete.
4. Customers must receive a pickup-ready notification only after a store associate has physically picked the BOPIS order.
5. Store associates need a Store Associate Task Management screen that lists pick, pack and pickup tasks in priority order.
6. Returned items must go back into available stock as soon as Returns Inspection & Disposition marks them resellable.
7. Each store must hold a configurable safety-stock buffer that is never offered online.
8. Demand Forecasting and Replenishment must consume real-time stock positions instead of the overnight batch.
9. Delivery orders should use Carbon-aware delivery routing to prefer the lowest-emission fulfilment option when cost is equal.
10. All reservations must be recorded in a Real-time Stock Reservation Ledger that can be audited per order.

## Non-functional requirements

- Availability queries must return in under 300 ms at the 95th percentile.
- The inventory service must achieve 99.9% availability during peak trading periods.
- The platform must sustain a Black Friday peak of 2,000 orders per minute without degradation.
- Following Observability by Design, every order must be traceable end to end from checkout through reservation to fulfilment.
- APIs used by store devices must follow Zero Trust Security, with every call authenticated and authorized.
- Following Design for Failure, if the inventory service is unavailable the storefront must fall back to last-known stock using the Circuit Breaker Pattern rather than failing checkout.
- The new services must run on our existing Azure tenancy and respond within 300 ms.

## Constraints

- The solution must integrate with Manhattan Active OMS and Oracle Retail Xstore POS; neither may be replaced in this program.
- The Legacy Inventory Mainframe must be retired incrementally using the Strangler Fig Migration Pattern, not in a single cutover.
- All new inventory capabilities must follow API First Design, with published contracts before implementation.
- Stock change events must be published using Event-Driven Architecture so downstream systems do not poll.
- Customer data must remain in US data center regions.
- Total program budget is capped at $6M, and the pilot must not start during the November–December peak freeze.

## Out of scope

RFID shelf tags are out of scope this year. We may revisit marketplace sellers later, but nothing is planned.

## Reminder

To restate the most important point: no unit may be sold twice, so stock must be reserved at checkout.
