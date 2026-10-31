output "portfolio_root" {
  value = var.portfolio_root
}

output "private_access_path" {
  value = "${var.ingress} -> 127.0.0.1:3000"
}
