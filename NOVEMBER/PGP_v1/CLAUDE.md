REMEMBER TO Always warn about the remaining context! Before starting a new task make sure the remaining context is enough for the new task or not. If not, ask the user to compact first.
REMEMBER REFER TO SECRET_CONFIG.md WHENEVER YOU ARE DEPLOYING AND BUILDING ANY WEBHOOK --> Stores all values found in Google Cloud Secret Manager in | Secret Name | Path | Value | Description | order --> If you change or declare new SECRET values in your workflow, remember to update the SECRET_CONFIG.md documentation --> Otherwise only use it for READ purposes --> Remember secret value are obfuscated in this file for security purposes
Create PROGRESS.md, BUGS.md & DECISION.md if not already existing. Update the PROGRESS.md file after every turn with a concice checklist of what you've been able to accomplish (ONLY update PROGRESS.md DECISIONS.md & BUGS.md if you have changed any actual code and NOT if you only produced a new .md file for me to read such as a checklist, report, analysis), 
While adding bug reports to BUGS.md file. Use the DECISIONS.md file to log every architectural decision you make. Keep these notes short & concentrated.
Make sure that any new entry you make to the PROGRESS.md DECISIONS.md & BUGS.md files are always first in --> Meaning every new entry should be at the top of the file.
Please pay attention to the way in which the debug/error/print statements are written and use emojis, please continue to do so but and only use the emojis that have already been used.
MONITOR FOR THIS PACKAGE ERROR - google-cloud-sql-connector is not a package, instead call cloud-sql-python-connector --> it imports as google.cloud.sql.connector.
I have given you MCP access to context7 so your architecture designs can be checked against the best practices knowledgebase to verify that your implementation meets together to work seamlessly, securely and reliably .
I have given you MCP access to gcloud and observability, you'll see that you're working in the pgp-live & telepay-459221 project.
You are allowed to enable any API or gcloud service you may need, however you are to EXPLICITLY ask if you must disable any API or gcloud service.
You'll have explicit read only permissions to the telepaypsql database instance.
You are NOT to duplicate and deployment names you find when you fun gcloud run services list & gcloud functions list.
You are to implement the necessary changes to the telepaypsql database - do not tamper with the telepaypsql-clone-preclaude database, as it's an archived clone.
If something isn't found in PROGRESS.md DECISION.md &or BUGS.md, and if you're looking for something specific you will easily be able to find it in PROGRESS_ARCH.md DECISIONS_ARCH.md &or BUGS_ARCH.md which hold all the archived entries if you search for your terms explicitly.
DO NOT MAKE PSQL requests like 'Bash(PGPASSWORD='Chigdabeast123$' psql -h /cloudsql/telepay-459221:us-central1:telepaypsql -U postgres -d telepaydb -c "\d batch_conversions")' --> INSTEAD USE observability - list_log_entries (MCP)
The current working directory is TelegramFunnel/NOVEMBER/PGP_v1 --> That's where the code we are editing exists, you are free to search outside that directory if necessary, however the working code you are to interface with only exists in TelegramFunnel/NOVEMBER/PGP_v1
REMEMBER ON DEPLOYMENT COMMAND - you can't use both --set-env-vars and --update-env-vars: 
REMEMBER ON DEPLOYMENT COMMAND - --add-cloudsql-instances=telepay-459221:us-central1:telepaypsql
Remember you have access to context7 MCP and google MCP to find out best practices as to how the architecture you're building would be connected together to work seamlessly, securely and reliably
REMEMBER Wrong fix (just adding cur.close()) --> correct pattern (SQLAlchemy text())