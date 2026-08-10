# Release Checklist

Use this as a go/no-go gate for the 10–12 participant pilot. A checked box means
it was verified against the exact commit and deployed environment being shared.

## Local Build Gate

- [ ] `npm ci` completes.
- [ ] `npm run build:css` completes and generates local HTMX/CSS assets.
- [ ] `python manage.py makemigrations --check --dry-run` reports no changes.
- [ ] The full Django test suite passes.
- [ ] `python manage.py check --deploy` passes with production-like environment
  values. During the initial HSTS burn-in, only `security.W005` and
  `security.W021` are expected; do not enable subdomain coverage or preload
  until every affected hostname is HTTPS-only and the domain is stable.
- [ ] Python and Node dependency audits report no known high-risk findings.
- [ ] The Docker image builds and `/healthz/` passes against PostgreSQL.
- [ ] `git diff --check` reports no whitespace errors.
- [ ] `git status` contains no database, `.env`, credential, log, or participant
  data files intended for commit.

## Hosting and Access Gate

- [ ] The source repository's public/private visibility is intentional.
- [ ] Render uses a paid web plan and managed PostgreSQL, not ephemeral SQLite.
- [ ] Production `DEBUG` is false and HTTPS redirect/cookies are enabled.
- [ ] SMTP delivery succeeds to a real test recipient.
- [ ] `ADMIN_EMAILS` receives a deliberate test error notification or the team
  has another confirmed log-alert path.
- [ ] Only intended commissioner emails/domains are in OAuth allowlists.
- [ ] Every legacy board has a `created_by` commissioner before adding more
  non-superuser staff accounts.
- [ ] The Google callback uses the production HTTPS hostname, if enabled.

## Data and Recovery Gate

- [ ] The managed database shows a recent successful backup.
- [ ] The operator knows how to restore into a separate database for a drill.
- [ ] `PRIVACY_CONTACT_EMAIL` and the retention period are correct.
- [ ] The operator has scheduled deletion of completed boards and participant
  data after the stated retention period.
- [ ] Payment notes contain only a payment handle/instructions—never bank login,
  card, OAuth, or SMTP credentials.
- [ ] The commissioner has confirmed the pool is permitted under applicable
  workplace rules and local law. This repository does not provide legal clearance.

## Pilot and Game-Day Gate

- [ ] The private pilot checks in `docs/deployment/staged-deployment.md` pass on
  at least two devices and two networks.
- [ ] The real game, entry amount, payout percentages, and payment instructions
  were reviewed by a second person.
- [ ] The board link was rotated after testing and is shared only with participants.
- [ ] All intended claims and payment flags are reconciled before assigning numbers.
- [ ] The commissioner saved a screenshot/export of the locked board and scoring
  digits before kickoff.
- [ ] The manual score fallback in `docs/operations/runbook.md` is open and available.
- [ ] One named commissioner is responsible for corrections and final payout review.

## Go / No-Go

Release only when every required item above is checked. Any failure involving
score correctness, concurrent claims, HTTPS, database backups, or operator
access is a no-go. Cosmetic issues may be deferred only when written down and
accepted before the link is shared.
