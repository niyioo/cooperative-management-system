# Office installation

The whole system on one computer in the society's office. Officials and members
open it in a web browser on any laptop or phone connected to the office Wi-Fi.
No hosting, web address or internet subscription is needed for daily work.

```
 office laptops / phones ──Wi-Fi──▶  office computer (Docker)
   browser: http://<computer-name>      web      nginx: the app, and /api passed on
                                        backend  Django + gunicorn
                                        db       PostgreSQL (not reachable from the network)
```

Everything lives in Docker volumes on that computer; `backup.ps1` copies it to an
external drive every evening.

## What the computer needs

- Windows 10/11 Pro, 8–16 GB memory, an SSD with 50 GB free. A laptop is best: its
  battery carries it through power cuts.
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free for a
  society of this size). In its settings tick **Start Docker Desktop when you sign in**.
- Two external drives for backups.
- BitLocker switched on (Settings → Privacy & security → Device encryption), so
  the records are unreadable if the computer is stolen.
- A Windows account used only for this system, set to sign in automatically or
  signed in each morning: Docker Desktop runs only while someone is signed in.

## Install

Copy this project folder to the computer (for example `C:\EMDI`), then in
PowerShell:

```powershell
cd C:\EMDI\deploy\office
powershell -ExecutionPolicy Bypass -File setup.ps1
```

`setup.ps1` writes `.env` (new passwords and this computer's network name), builds
the system and starts it. The first build takes 5–15 minutes. It then prints the
address to use, such as `http://emdi-office`. Add `-Port 8080` if something else
already uses port 80.

It also puts an **EMDI Cooperative** icon on the desktop, which opens the system
in its own window like an installed app.

Allow Docker through Windows Firewall when asked (private networks only), so
other devices on the Wi-Fi can reach it.

### Desktop icons on the officials' laptops

Copy this folder (or just `add-shortcut.ps1` and `emdi.ico`) to each laptop and run,
with the office computer's name that setup printed:

```powershell
powershell -ExecutionPolicy Bypass -File add-shortcut.ps1 -Server emdi-office
```

On phones, open the address in Chrome and choose **Add to Home screen**.

### Bring in the society's records

On the developer's computer, export them (a script kept with the real records,
not in this project) and carry the files on an encrypted drive. Then:

```powershell
powershell -ExecutionPolicy Bypass -File restore.ps1 -Dump E:\emdi_live_2026-11-03_1000.dump
```

Add `-Media E:\media_….tgz` if there are uploaded documents. The officials'
existing logins come across with the records. Delete the export files afterwards.

### Or start empty

```powershell
docker compose exec backend python manage.py createsuperuser
```

### Nightly backups

Set `BACKUP_DIR` in `.env` to the external drive (for example `D:\EMDI-backups`), then:

```powershell
powershell -ExecutionPolicy Bypass -File schedule-backup.ps1
powershell -ExecutionPolicy Bypass -File backup.ps1      # one now, to check
```

Every evening at 19:00 (or at the next sign-in if the computer was off) it saves
the database and documents and keeps the last 30. `backup-log.txt` on the drive
records each run. Once a week the Treasurer copies the newest pair of files to
the second drive and takes it home.

Test a restore with the officials once, so everyone knows it works.

## Sign-in emails (optional)

The system emails members a link to set their password. To send them, create a
Gmail account for the society, turn on 2-step verification, create an **app
password**, and put the address and app password in `.env` as `EMAIL_HOST_USER`
and `EMAIL_HOST_PASSWORD`. Then `docker compose up -d`. Emails go out whenever the
computer has internet; without it, officials can set members' passwords for them.

## Day to day

| Task | Command (in this folder) |
| --- | --- |
| Is it running? | `docker compose ps` |
| Restart it | `docker compose restart` |
| See what went wrong | `docker compose logs --tail 100 backend` |
| Back up now | `powershell -ExecutionPolicy Bypass -File backup.ps1` |
| Restore a backup | `powershell -ExecutionPolicy Bypass -File restore.ps1 -Dump <file> [-Media <file>]` |
| Install a new version | copy the new files over this folder (keep `.env`), then `powershell -ExecutionPolicy Bypass -File update.ps1` |

The system starts by itself when Docker Desktop starts.

If a command sits at "Starting" for more than a minute, Docker Desktop is being
slow to start a new container: press Ctrl+C, then run `docker compose start` (or
the same command again).

## Moving online later

Take a backup, restore it on the hosting server with the production settings
(`config.settings.prod`, behind https), and point the web address at it. No
records are typed in again.

## Security notes

- The office network carries the system over plain http, so use it only on the
  society's own password-protected Wi-Fi, never a public one.
- `.env` holds the database password and secret key: never share or email it.
- The database is not exposed to the network; only the web port is.
