# Environment Variables Setup

This document explains all the environment variables used in the Django movie recommendation app.

## Required Environment Variables

### Django Core Settings
- `DJANGO_SECRET_KEY` - Django secret key for cryptographic signing
- `DJANGO_DEBUG` - Set to `True` for development, `False` for production
- `DJANGO_ALLOWED_HOSTS` - Comma-separated list of allowed hosts

### Security Settings
- `SECURE_SSL_REDIRECT` - Redirect HTTP to HTTPS (set to `True` in production)
- `SECURE_HSTS_SECONDS` - HTTP Strict Transport Security duration
- `SECURE_HSTS_INCLUDE_SUBDOMAINS` - Include subdomains in HSTS
- `SECURE_HSTS_PRELOAD` - Enable HSTS preload
- `SECURE_BROWSER_XSS_FILTER` - Enable XSS filter
- `SECURE_CONTENT_TYPE_NOSNIFF` - Prevent MIME type sniffing
- `SESSION_COOKIE_SECURE` - Secure session cookies (set to `True` in production)
- `CSRF_COOKIE_SECURE` - Secure CSRF cookies (set to `True` in production)

### CORS Settings
- `CORS_ALLOW_ALL_ORIGINS` - Allow all origins (set to `False` in production)
- `CORS_ALLOWED_ORIGINS` - List of allowed origins for CORS

### Payment Settings
- `PAYPAL_RECEIVER_EMAIL` - Your PayPal business email
- `PAYPAL_TEST` - Use PayPal sandbox (`True`) or production (`False`)
- `STRIPE_SECRET_KEY` - Your Stripe secret key
- `STRIPE_PUBLISHABLE_KEY` - Your Stripe publishable key
- `STRIPE_WEBHOOK_SECRET` - Your Stripe webhook secret

### API Keys
- `OMDB_API_KEY` - OMDb API key for movie data

### Authentication Settings
- `LOGIN_URL` - URL for login page
- `LOGIN_REDIRECT_URL` - URL to redirect after login
- `LOGOUT_REDIRECT_URL` - URL to redirect after logout

### Database Settings (Production)
- `DATABASE_URL` - Database connection URL (e.g., PostgreSQL)

### Email Settings (Production)
- `EMAIL_BACKEND` - Email backend (smtp for production)
- `EMAIL_HOST` - SMTP server host
- `EMAIL_PORT` - SMTP server port
- `EMAIL_USE_TLS` - Use TLS for email
- `EMAIL_HOST_USER` - Email username
- `EMAIL_HOST_PASSWORD` - Email password
- `DEFAULT_FROM_EMAIL` - Default sender email

### Other Settings
- `GDPR_ENABLED` - Enable GDPR compliance features

## Development vs Production

### Development (.env)
```bash
DJANGO_DEBUG=True
CORS_ALLOW_ALL_ORIGINS=True
PAYPAL_TEST=True
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
```

### Production (.env.production)
```bash
DJANGO_DEBUG=False
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://yourdomain.com
PAYPAL_TEST=False
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## Installation

1. Copy `.env` to `.env.production` for production
2. Update all values with your actual credentials
3. Never commit `.env.production` to version control
4. Add `.env.production` to `.gitignore`

## Security Notes

- Never commit API keys or secrets to version control
- Use strong, unique secret keys in production
- Enable all security settings in production
- Use HTTPS in production
- Restrict CORS origins in production
- Use environment-specific database URLs 