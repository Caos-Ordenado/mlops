terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "4.48.0"
    }
  }
}
resource "cloudflare_zone_settings_override" "security_settings" {
  zone_id = var.cloudflare_zone_id

  settings {
    security_level        = "high"      # Alto nivel de seguridad
    always_use_https      = "on"        # Redirigir HTTP a HTTPS
    automatic_https_rewrites = "on"
    brotli                = "on"        # Mejor compresión
    min_tls_version       = "1.2"       # TLS mínimo 1.2
    opportunistic_encryption = "on"
  }
}

resource "cloudflare_firewall_rule" "challenge_suspicious" {
  zone_id     = var.cloudflare_zone_id
  description = "Desafío CAPTCHA para tráfico sospechoso"
  filter {
    expression = "(http.request.uri.path contains \"/admin\")"
  }
  action = "challenge"
  filter_id = ""
}

resource "cloudflare_firewall_rule" "block_malicious_countries" {
  zone_id     = var.cloudflare_zone_id
  description = "Bloqueo de países de alto riesgo"
  filter {
    expression = "(ip.geoip.country in {\"RU\", \"CN\"})"
  }
  action = "block"
  filter_id = ""
}

resource "cloudflare_rate_limit" "global_rate_limit" {
  zone_id = var.cloudflare_zone_id
  threshold = 1000        # Máximo de solicitudes
  period    = 60          # Por minuto

  match {
    request {
      methods = ["GET", "POST"]
      schemes = ["HTTP", "HTTPS"]
    }
  }

  action {
    mode = "simulate"     # Cambiar a "block" si quieres bloquear en producción
  }
}
