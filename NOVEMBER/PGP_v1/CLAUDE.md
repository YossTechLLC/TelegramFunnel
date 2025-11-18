The current working directory is TelegramFunnel/NOVEMBER/PGP_v1 --> That's where the code we are editing exists, you are free to search outside that directory if necessary, however the working code you are to interface & edit only exists in TelegramFunnel/NOVEMBER/PGP_v1
You are allowed to read and view any file inside of /TelegramFunnel --> however you are to only edit folders & files found inside of TelegramFunnel/NOVEMBER/PGP_v1
Your working .venv environmentinside of ~/TelegramFunnel/NOVEMBER/PGP_v1/.venv --> Please make sure to only operate inside that .venv environment.
Your .claude folder is explicitly found inside of /PGP_v1 --> ingore any others.
REMEMBER TO Always warn about the remaining context! Before starting a new task make sure the remaining context is enough for the new task or not. If not, ask the user to compact first.
REMEMBER REFER TO SECRET_SCHEME.md --> contains updated PGP_X_v1 naming scheme of secrets and their respective contents --> always use Google Cloud Secret path inside of code when trying to give raw value to any given function.
REMEMBER REFER TO NAMING_SCHEME.md --> containts updated PGP_x_v1 naming scheme map & its relevant mapping to old scheme for reference and utility.
/TOOLS_SCRIPTS_TESTS/ --> contains --> /scripts/ all .sh files you ever make --> /test/ & /tools/ all relevant .py files you ever make --> /migrations/ telepaypsql to pgp-live psql db migration.
If any .md file isn't present in the native directory of /PGP_v1/ --> Look for it the .md file in /ARCHIVES_PGP_v1/11-18_PGP_v1
If any .sh .py .sql file isn't present inside of /PGP_v1/TOOLS_SCRIPTS_TEST/ or it's subfolders --> Look inside of /ARCHIVES_PGP_v1/OLD_TOOLS_SCRIPTS_TESTS or it's subfolders.
If you generate any new .md file for me to read & review always place it inside of /THINK/AUTO/
Create PROGRESS.md, BUGS.md & DECISION.md if not already existing. Update the PROGRESS.md file after every turn with a concice checklist of what you've been able to accomplish (ONLY update PROGRESS.md DECISIONS.md & BUGS.md if you have changed any actual code and NOT if you only produced a new .md file for me to read such as a checklist, report, analysis), 
While adding bug reports to BUGS.md file. Use the DECISIONS.md file to log every architectural decision you make. Keep these notes short & concentrated.
Make sure that any new entry you make to the PROGRESS.md DECISIONS.md & BUGS.md files are always first in --> Meaning every new entry should be at the top of the file.
Please pay attention to the way in which the debug/error/print statements are written and use emojis, please continue to do so but and only use the emojis that have already been used.
MONITOR FOR THIS PACKAGE ERROR - google-cloud-sql-connector is not a package, instead call cloud-sql-python-connector --> it imports as google.cloud.sql.connector.
I have given you MCP access to context7 mcp & google mcp & cloudflare mcp so your architecture designs can be checked against the best practices knowledgebase to verify that your implementation meets together to work seamlessly, securely and reliably .
I have given you MCP access to gcloud and observability, you'll see that you're working in the pgp-live project.
You'll have explicit read only permissions to the telepaypsql database instance.
REMEMBER telepaypsql is the old psql server with client_table database on project id telepay-459221 we are using to scafold the new psql server pgp-live-psql with pgp-live-db database on project id pgp-live 
YOU ARE NOT TO DEPLOY ANYTHING TO GOOGLE --> All changes must be local to the /NOVEMBER/PGP_v1 directory only.
YOU ARE NOT TO MAKE ANY CHANGES ON CLOUDFLARE --> All changes must be local to the /NOVEMBER/PGP_v1 directory only.
YOU ARE NOT TO DEPLOY ANYTHING TO GITHUB --> All changes must be local to the /NOVEMBER/PGP_v1 directory only
If something isn't found in PROGRESS.md DECISION.md &or BUGS.md, and if you're looking for something specific you will easily be able to find it in PROGRESS_ARCH.md DECISIONS_ARCH.md &or BUGS_ARCH.md which hold all the archived entries if you search for your terms explicitly.
DO NOT MAKE PSQL requests like 'Bash(PGPASSWORD='Chigdabeast123$' psql -h /cloudsql/telepay-459221:us-central1:telepaypsql -U postgres -d telepaydb -c "\d batch_conversions")' --> INSTEAD USE observability - list_log_entries (MCP)
Remember you have access to context7 MCP and google MCP to find out best practices as to how the architecture you're building would be connected together to work seamlessly, securely and reliably
REMEMBER Wrong fix (just adding cur.close()) --> correct pattern (SQLAlchemy text())