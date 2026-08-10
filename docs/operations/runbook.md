# Operations Runbook

This runbook is for the person operating a private NFL Squares pool. Keep it
available during the pilot and live game.

## Ownership and Roles

- Use a superuser only for setup, legacy ownership repair, and recovery.
- Give each regular commissioner a separate staff login. Commissioners can see
  only boards they created.
- Before enabling multiple commissioners, assign `created_by` on any legacy
  boards that currently have no owner.
- Never share operator passwords or use a participant account for administration.

## Before Creating a Board

1. Confirm `/healthz/` returns HTTP 200 with database `ok`.
2. Confirm the schedule job and score job have recent successful runs.
3. Check Render logs for repeated ESPN, database, email, or HTTP 500 errors.
4. Confirm a recent database backup is visible in Render.
5. Review the game identity, start time, entry amount, payout split, and payment
   instructions before sharing the board.

The ESPN endpoint is an unofficial upstream dependency. The application's stored
scores and winner highlights are conveniences; the commissioner must compare
final payouts with an official game result before paying anyone.

## Normal Commissioner Workflow

1. Create the board at `/boards/dashboard/`.
2. Share only its tokenized link. Do not post it publicly.
3. Correct mistakes with **Release claim**; do not edit another participant's
   name into a claimed square.
4. Record confirmed payments with **Paid**. The app does not move money.
5. Reconcile the participant list and payment status before using **Assign Numbers**.
6. Assign numbers once. Locking closes claims and reveals the scoring digits.
7. Save a screenshot of the locked board before kickoff.
8. Verify every quarter result and the final total before payouts.

## Score Feed Checks and Recovery

The browser polls stored scores every 60 seconds. The scheduled job refreshes
those scores from ESPN every five minutes, so a normal display may lag the live
broadcast by several minutes.

From a Render shell, a manual refresh is:

```bash
python manage.py sync_scores
```

If the command reports no games or logs an ESPN request error:

1. Check the Render job log and service status; do not repeatedly change data
   while the upstream request is failing.
2. Verify the actual game and quarter result with an official NFL source.
3. In Django admin, open the affected NFL Game and enter the completed quarter
   line scores, total scores, period, and status. Use `final` only when the game
   is officially complete. Final totals must include every overtime period.
4. Refresh the participant board and compare the highlighted winner with the
   locked digits manually.
5. Tell participants that the display was corrected manually and record who
   made the correction and which official result was used.

If confidence is low, pause payouts. A delayed manual result is safer than a
premature or incorrect payout.

## Common Incidents

### A board link was posted publicly

Use **Regenerate Link** immediately. The old token stops working. Send the new
link directly to participants and review the board for unknown claims.

### A participant claimed the wrong square

Use **Release claim**, ask the participant to claim the intended available
square, and reconfirm payment status. Releasing also clears the paid flag.

### Two people report the same selection

The database preserves the first completed claim. Check the claim timestamps and
stored name in the dashboard; release or reassign only with both participants'
agreement.

### Invite email fails

Copy the private board URL from the dashboard and send it through the existing
group channel. Then check SMTP credentials and Render logs. Do not paste SMTP
passwords into board notes or support messages.

### `/healthz/` reports 503 or the database is unavailable

Stop board changes, check Render database/service status, and wait for database
health before retrying. If a deploy caused the issue, roll back the application.
Do not create a replacement SQLite deployment.

### A release causes errors

Redeploy the previous known-good commit from Render's deploy history. Run the
remote smoke check afterward. Avoid rolling code forward during a live game.

## Backups and Data Recovery

- Confirm Render-managed backups are enabled and recent before each event.
- Create an additional manual backup before a schema release or high-value event
  when the selected database plan supports it.
- At least quarterly, restore a backup into a separate, non-production database
  and verify boards, squares, ownership, and scores. Never test a restore by
  overwriting production.
- Record backup time, restore test time, operator, and result.

For suspected data damage, stop writes, preserve logs and timestamps, and restore
to a separate database first. Compare it with production before choosing a
recovery point. Follow Render's current backup documentation because retention
and restore options depend on the database plan.

## Privacy and Retention

The board page exposes participant names, selections, and paid/unpaid status to
anyone holding the link. Emails are commissioner-only. Treat the link as private.

After payouts and disputes are settled:

1. Wait only for the configured retention period shown on `/privacy/`.
2. Delete the completed board in Django admin; its related square claims are
   deleted with it.
3. Confirm the board token returns 404 and remove screenshots containing names
   when they are no longer needed.
4. Record the deletion date without retaining participant details.

Respond promptly to correction or deletion requests through the configured
privacy contact. Never place banking credentials, card data, access tokens, or
account passwords in participant fields or board notes.

## Post-Event Closeout

- Compare all four winners against official scores and the locked digit grid.
- Have a second person confirm payout math.
- Record payouts outside the app using the minimum detail needed.
- Resolve disputes before deleting data.
- Review error logs and note any issue that must be fixed before the next event.
- Delete the board and participant records within the stated retention period.

Operational references:

- [Render health checks](https://render.com/docs/health-checks)
- [Render PostgreSQL backups](https://render.com/docs/postgresql-backups)
- [Render deploy history and rollback](https://render.com/docs/deploys)
