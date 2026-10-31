# Ansible host configuration

Ansible is the selected host-configuration layer. It installs the owner-run
systemd units, creates private directories, applies restrictive permissions,
and leaves Tailscale identity and secrets as explicit operator steps.

Copy `inventory.example.ini` to a private inventory and provide secret values
through Ansible Vault or an external secret manager. Never commit the real
inventory, SSH private key, `operator.env`, or backup recipient.

```bash
ansible-playbook -i inventory.ini site.yml --ask-become-pass
```

The playbook does not open a public listener, configure a public reverse proxy,
enable mutations, or install provider credentials. Apply the Tailscale ACL and
Serve command from `deploy/u5-5/` only after the owner has reviewed the host.
