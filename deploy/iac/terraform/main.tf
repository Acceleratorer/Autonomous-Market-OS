terraform {
  required_version = ">= 1.5.0"
}

resource "terraform_data" "u55_runtime_contract" {
  input = {
    runtime               = var.runtime
    supervisor            = var.supervisor
    ingress               = var.ingress
    allowed_subject       = var.allowed_subject
    allowed_portfolio_id  = var.allowed_portfolio_id
    portfolio_root        = var.portfolio_root
    session_expiry        = var.session_expiry_seconds
    clock_tolerance       = var.clock_tolerance_seconds
    mutation_enabled      = var.mutation_enabled
    public_listener       = var.public_listener
  }

  lifecycle {
    precondition {
      condition     = var.runtime == "private-linux-vm"
      error_message = "U5.5 runtime must remain the owner-controlled private Linux VM."
    }
    precondition {
      condition     = var.supervisor == "systemd" && var.ingress == "tailscale-serve"
      error_message = "U5.5 supervisor/ingress contract is systemd + Tailscale Serve."
    }
    precondition {
      condition     = var.allowed_portfolio_id == "paper-main" && var.mutation_enabled == false && var.public_listener == false
      error_message = "U5.5 must remain paper-main-only, mutation-disabled, and private."
    }
  }
}

output "u55_runtime_contract" {
  value = terraform_data.u55_runtime_contract.output
}
