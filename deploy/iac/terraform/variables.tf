variable "runtime" {
  type    = string
  default = "private-linux-vm"
}

variable "supervisor" {
  type    = string
  default = "systemd"
}

variable "ingress" {
  type    = string
  default = "tailscale-serve"
}

variable "allowed_subject" {
  type    = string
  default = "owner-only"
}

variable "allowed_portfolio_id" {
  type    = string
  default = "paper-main"
}

variable "portfolio_root" {
  type    = string
  default = "/var/lib/autonomous-market-os/portfolios"
}

variable "session_expiry_seconds" {
  type    = number
  default = 900
}

variable "clock_tolerance_seconds" {
  type    = number
  default = 60
}

variable "mutation_enabled" {
  type    = bool
  default = false
}

variable "public_listener" {
  type    = bool
  default = false
}
