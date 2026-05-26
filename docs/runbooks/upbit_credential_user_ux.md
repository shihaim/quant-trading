# Upbit Credential UX Expectations

Last updated: 2026-05-26

## Scope

- User credential operations use authenticated `/api/me/*` identity only.
- A user can read or update only their own Upbit credential status.
- Admin credential reads must stay under `/api/admin/users/{user_id}/*` and include an explicit target user id.

## User Status Model

- `connected`: credentials exist and can be decrypted by the active credential key configuration.
- `missing`: no Upbit credentials are stored for the authenticated user.
- `needs_attention`: credentials exist, but the service cannot read them. The usual recovery action is saving a fresh Upbit key pair.

## Secret Handling

- The API accepts `access_key` and `secret_key` only on credential save.
- Responses must never include raw `access_key` or `secret_key`.
- The UI may show only a masked access key and save timestamp.
- After a successful save, the form clears both inputs and does not redisplay the secret.
- Audit metadata records status and exchange context, not raw secrets.

## User Actions

- `missing`: open the Upbit authentication screen and register a key pair.
- `needs_attention`: open the same screen and save a fresh key pair.
- `connected`: no action is required unless the user wants to rotate or replace keys.
