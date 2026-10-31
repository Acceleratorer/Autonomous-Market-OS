# Terraform bootstrap contract

Terraform is the selected IaC layer for the owner-controlled runtime, while
Ansible configures the Linux host after it exists. The current module is
provider-neutral because the owner has not selected a cloud/VPS provider. It
validates and records the approved U5.5 runtime contract without inventing a
cloud account, region, network, or public address.

When a provider is selected, add a provider-specific root module that consumes
these variables and preserves the same outputs. Do not put Tailscale auth keys,
assertion secrets, backup recipients, or portfolio data in Terraform state.

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan
```
