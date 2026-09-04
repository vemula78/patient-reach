# Provenance

This app is **Patient Reach** (`patient_reach`), written by **Frugal Scientific**
and originally hosted at `frugalscientificdev/sssim`. It is licensed **MIT**
(see `license.txt`), which permits use, modification and redistribution with
attribution retained. Authorship in `pyproject.toml` is unchanged.

## Why this copy exists

SSSIHMS operates `care.sssihms.org` on its own infrastructure and needs to be
able to rebuild the container image that runs it. Rebuilding requires every
app's source. SSSIHMS has no read access to `frugalscientificdev/sssim`, which
left the external image unbuildable and therefore unmaintainable — the deployed
`frappe-external:v1.0.0` could not be reproduced, patched or recovered
independently.

Extracted 04-Sep-2026 from
`trustcompliancedemo.azurecr.io/frappe-external:v1.0.0`, at
`/home/frappe/frappe-bench/apps/patient_reach`. That corresponds to upstream
commit **`fbe509c`** ("Add app permission function and update app configuration
uncommented add_to_apps_screen in hooks") — note this is *newer* than the
`ee9d34a` pinned in the build definition, so the deployed code was ahead of what
was recorded.

54 source files, verified complete against the image file-by-file.

## What was deliberately excluded

The app directory in the image retained a `.git` directory whose remote URL
contained a **live GitHub access token** for `frugalscientificdev/sssim`:

```
upstream  https://<token>@github.com/frugalscientificdev/sssim.git
```

`.git` was excluded from this copy so that credential is not propagated here.
`__pycache__` and `*.pyc` were also dropped. This copy has been scanned and
contains no credentials.

**That token was reported to Frugal Scientific for revocation on 04-Sep-2026.**
It was exposed beyond the VM: the image was also published to the *public* Docker
Hub repository `frugalscientific/frappe-external`, so anyone pulling it obtained
the token. Revoking the token is necessary but not sufficient — the public images
also need deleting or making private, or it remains retrievable from them.

## Relationship to upstream

This is a snapshot, not a fork tracking upstream. If Frugal Scientific continue
developing Patient Reach, changes must be brought across deliberately. If SSSIHMS
is granted read access to the original repository, referencing that directly is
preferable to maintaining a copy.

Frugal Scientific were informed that this copy was taken.
