# Staged Deployment

The initial production target is one Render web service, one managed PostgreSQL
database, and two scheduled jobs defined in `render.yaml`. For a 10–12 person
private pilot, promotion means validating the deployed service first and only
then sharing tokenized board links.

## Architecture

```text
participant browser
        |
        v
Render HTTPS web service ----> Render PostgreSQL
        ^                            ^
        |                            |
score and schedule jobs ------------+
        |
        v
unofficial ESPN scoreboard feed
```

The app does not process money. Payment instructions are informational and the
commissioner records only whether a payment was confirmed.

## Before the First Deployment

1. Run every item in `docs/release-checklist.md`.
2. Decide whether the source repository should remain public. Never commit a
   `.env` file, database export, OAuth secret, SMTP password, or participant data.
3. Connect the repository in Render and create a Blueprint from `render.yaml`.
4. Supply every environment value marked `sync: false` in the Render dashboard:
   - SMTP username, app password, sender addresses, and alert recipient
   - privacy contact address
   - Google OAuth client and commissioner allowlists, if Google login is enabled
5. Keep the generated `SECRET_KEY`; do not copy a development key into production.

The Blueprint derives the allowed hostname, CSRF origin, and default site URL
from Render's public hostname. If a custom domain is added later, explicitly set
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `SITE_URL` to that domain before
switching DNS.

## First Deployment

1. Create the Blueprint and wait for the database, web deploy, and pre-deploy
   migration to succeed.
2. Confirm the service reports `Live` and open `/healthz/`. The response must be:

   ```json
   {"status": "ok", "database": "ok"}
   ```

3. Open a Render shell for the web service and create the first operator:

   ```bash
   python manage.py createsuperuser
   ```

4. Import the current schedule:

   ```bash
   python manage.py sync_schedule --all-weeks
   python manage.py sync_scores
   ```

5. If Google login is enabled, add this exact authorized redirect URI in the
   Google OAuth client:

   ```text
   https://YOUR-HOST/accounts/google/login/callback/
   ```

6. Run the automated remote smoke check:

   ```bash
   bash script/deployment_smoke_check.sh https://YOUR-HOST
   ```

## Private Pilot Gate

Do not send the link to all participants yet. Use the deployed service with a
disposable test board and verify:

- one commissioner can create a board, copy its link, and send an invite;
- a second commissioner cannot see or change the first commissioner's board;
- two browsers can attempt the same square without overwriting the first claim;
- claims work from both Wi-Fi and cellular data;
- names and payment status appear on the shared board, but email addresses do not;
- releasing a claim, marking paid/unpaid, assigning numbers, and rotating the
  board link all work;
- a zero score renders as `0`, quarter winners wait for completed periods, and
  the final winner uses the official overtime-inclusive total;
- the privacy page and error pages render on a phone-sized screen;
- score and schedule jobs show successful runs in Render.

After the test, delete the disposable board and its participant records. The
same deployment can then be promoted simply by creating the real board and
sharing its private token link with the 10–12 participants.

## Subsequent Releases

`autoDeployTrigger: checksPass` allows Render to deploy only after the linked
commit's checks pass. For each release:

1. Run the release checklist locally.
2. Merge the exact reviewed commit.
3. Confirm CI passes and Render deploys that commit.
4. Run the remote smoke check and one commissioner write-path check.
5. Record the commit SHA and deploy time in the event notes.

Avoid schema or dependency releases during a live game.

## Rollback

For an application regression, use Render's deploy history to redeploy the last
known-good commit, then rerun the smoke check. A code rollback does not reverse a
database migration or restore deleted data. If data is damaged, stop writes and
follow the database recovery section in `docs/operations/runbook.md`.

Render references:

- [Blueprint specification](https://render.com/docs/blueprint-spec)
- [Deploying Django](https://render.com/docs/deploy-django)
- [Deploy rollback and history](https://render.com/docs/deploys)
- [Cron jobs](https://render.com/docs/cronjobs)
- [PostgreSQL backups](https://render.com/docs/postgresql-backups)
