# P5 Events and Operational Notifications

Date: 2026-06-01

## Scope

Story P5 adds an in-app operational event model for:

- halt
- credential issue
- order review
- runtime error

Events are derived from existing scoped runtime, credential, and order state. No new event persistence table or external delivery worker is introduced in this story.

## Delivery Decision

Notification delivery is in-app only for P5.

External notifications, such as Telegram, email, or mobile push, remain a later delivery layer. Future external delivery should consume the same event semantics while preserving user scope and secret redaction.

## Scope Rules

- `/api/me/overview` returns only events for the authenticated user.
- `/api/admin/users/runtime-summary` remains admin-only and may include target user operational detail.
- Admin user-specific event detail is tied to an explicit target user id from the admin runtime summary item.
- User-facing event copy avoids internal ids, API paths, source fields, and scope fields.
- Secret values are never included in event payloads.
